"""Mock Open-Banking FastAPI backend — port 8000.

Run: uvicorn src.backend.app:app --reload --port 8000

Reset DB: rm src/backend/bank.db && python -m src.backend.seed
"""
import json
import logging
import os
import random
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.backend.failure_codes import FAILURE_CODES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("banking_api")

app = FastAPI(title="Mock Open Banking", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
V = "/open-banking/v1"

_DEFAULT_DB = str(os.path.join(os.path.dirname(__file__), "bank.db"))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start  = time.perf_counter()
    method = request.method
    path   = request.url.path
    query  = ("?" + str(request.url.query)) if request.url.query else ""
    logger.info("→ %s %s%s", method, path, query)
    try:
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info("← %s %s%s %s (%.0fms)", method, path, query, response.status_code, ms)
        return response
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        logger.error("✗ %s %s%s ERROR (%.0fms): %s", method, path, query, ms, exc, exc_info=True)
        raise


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTP %s on %s %s — %s", exc.status_code, request.method, request.url.path, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def _db() -> str:
    return os.getenv("DB_PATH", _DEFAULT_DB)


def q(sql: str, args: tuple = (), one: bool = False) -> list | dict | None:
    con = sqlite3.connect(_db())
    con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    con.commit(); con.close()
    return (rows[0] if rows else None) if one else rows


def envelope(data) -> dict:
    return {"Data": data, "Meta": {"TotalRecords": len(data) if isinstance(data, list) else 1}}


@app.get("/health")
def health():
    return {"status": "ok", "db": _db()}


# ── Customers ─────────────────────────────────────────────────────────────────

@app.get(f"{V}/customers/{{customer_id}}")
def get_customer(customer_id: str):
    cust = q("SELECT customer_id, name, phone, kyc_verified FROM customers WHERE customer_id=?",
             (customer_id,), one=True)
    if not cust:
        raise HTTPException(404, "customer not found")
    parts = (cust["name"] or "").split()
    cust["avatar_initials"] = "".join(p[0].upper() for p in parts[:2]) if parts else "??"
    return envelope(cust)


# ── AIS ───────────────────────────────────────────────────────────────────────

@app.get(f"{V}/accounts")
def get_accounts(customer_id: str):
    rows = q("SELECT account_id, customer_id, account_type, nickname, account_number, balance, currency, opened_on "
             "FROM accounts WHERE customer_id=?", (customer_id,))
    for r in rows:
        acct = r.get("account_number") or r["account_id"]
        r["masked_number"] = f"••{acct[-4:]}"
    return envelope(rows)


@app.get(f"{V}/accounts/{{account_id}}/balances")
def get_balance(account_id: str):
    acc = q("SELECT account_id, account_type, nickname, account_number, balance, currency "
            "FROM accounts WHERE account_id=?", (account_id,), one=True)
    if not acc:
        raise HTTPException(404, "account not found")
    acct = acc.get("account_number") or account_id
    acc["masked_number"] = f"••{acct[-4:]}"
    return envelope(acc)


class StatementQuery(BaseModel):
    account_id: str
    from_date:  Optional[str] = None
    to_date:    Optional[str] = None
    category:   Optional[str] = None
    rail:       Optional[str] = None
    detailed:   bool = False


@app.post(f"{V}/accounts/transactions/query")
def get_statement(req: StatementQuery):
    sql  = "SELECT * FROM transactions WHERE account_id=?"
    args: list = [req.account_id]
    if req.from_date: sql += " AND created_at>=?"; args.append(req.from_date)
    if req.to_date:   sql += " AND created_at<=?"; args.append(req.to_date)
    if req.category:  sql += " AND category=?";   args.append(req.category)
    if req.rail:      sql += " AND rail=?";        args.append(req.rail)
    sql += " ORDER BY created_at DESC"
    txns = q(sql, tuple(args))

    spent    = sum(t["amount"] for t in txns if t["direction"] == "debit"  and t["status"] == "success")
    received = sum(t["amount"] for t in txns if t["direction"] == "credit" and t["status"] == "success")

    # Previous-period comparison (same duration, shifted back)
    prev_spent:    Optional[float] = None
    pct_change:    Optional[int]   = None
    if req.from_date and req.to_date:
        try:
            fd = datetime.fromisoformat(req.from_date)
            td = datetime.fromisoformat(req.to_date)
            dur = td - fd
            prev_from = (fd - dur).isoformat()
            prev_to   = req.from_date
            prev_sql  = "SELECT * FROM transactions WHERE account_id=? AND created_at>=? AND created_at<=?"
            prev_args: list = [req.account_id, prev_from, prev_to]
            if req.category: prev_sql += " AND category=?"; prev_args.append(req.category)
            if req.rail:     prev_sql += " AND rail=?";     prev_args.append(req.rail)
            prev_txns  = q(prev_sql, tuple(prev_args))
            prev_spent = sum(t["amount"] for t in prev_txns  # type: ignore[union-attr]
                             if t["direction"] == "debit" and t["status"] == "success")
            if prev_spent and prev_spent > 0:
                pct_change = round((spent - prev_spent) / prev_spent * 100)
        except Exception as exc:
            logger.warning("prev-period calc failed: %s", exc)

    return envelope({
        "total_spent":    spent,
        "total_received": received,
        "count":          len(txns),
        "from_date":      req.from_date,
        "to_date":        req.to_date,
        "category":       req.category,
        "rail":           req.rail,
        "prev_period_spent": prev_spent,
        "pct_change":        pct_change,
        "transactions":   txns if req.detailed else [],
    })


@app.get(f"{V}/transactions/{{txn_id}}/failure")
def explain_failure(txn_id: str):
    t = q("SELECT * FROM transactions WHERE txn_id=?", (txn_id,), one=True)
    if not t: raise HTTPException(404, "transaction not found")
    if t["status"] != "failed":
        return envelope({"txn_id": txn_id, "status": t["status"], "explanation": None})
    info = FAILURE_CODES.get(t["failure_code"], {})
    return envelope({"txn_id": txn_id, "status": "failed",
                     "failure_code": t["failure_code"], **info})


# ── Deposits ──────────────────────────────────────────────────────────────────

@app.get(f"{V}/deposit-products")
def list_deposit_products(kind: Optional[str] = None):
    if kind:
        return envelope(q("SELECT * FROM deposit_products WHERE kind=? ORDER BY tenure_months", (kind,)))
    return envelope(q("SELECT * FROM deposit_products ORDER BY kind,tenure_months"))


class DepositBooking(BaseModel):
    customer_id:   str
    product_id:    str
    amount:        float
    tenure_months: int


@app.post(f"{V}/deposit-bookings")
def book_deposit(req: DepositBooking):
    p = q("SELECT * FROM deposit_products WHERE product_id=?", (req.product_id,), one=True)
    if not p: raise HTTPException(404, "product not found")
    if not (p["min_amount"] <= req.amount <= p["max_amount"]):
        raise HTTPException(400, f"amount must be {p['min_amount']}–{p['max_amount']}")
    bid      = "DEP" + uuid.uuid4().hex[:8]
    maturity = round(req.amount * (1 + p["interest_rate"] / 100 * req.tenure_months / 12), 2)
    q("INSERT INTO deposit_bookings VALUES (?,?,?,?,?,?,?)",
      (bid, req.customer_id, req.product_id, req.amount,
       req.tenure_months, "created", datetime.utcnow().isoformat()))
    return envelope({"booking_id": bid, "status": "created", "product": p["name"],
                     "kind": p["kind"], "amount": req.amount,
                     "tenure_months": req.tenure_months,
                     "interest_rate": p["interest_rate"], "maturity_value": maturity})


@app.post(f"{V}/deposit-bookings/{{booking_id}}/confirm")
def confirm_deposit(booking_id: str):
    b = q("SELECT * FROM deposit_bookings WHERE booking_id=?", (booking_id,), one=True)
    if not b: raise HTTPException(404, "booking not found")
    q("UPDATE deposit_bookings SET status='confirmed' WHERE booking_id=?", (booking_id,))
    return envelope({"booking_id": booking_id, "status": "confirmed"})


# ── PIS ───────────────────────────────────────────────────────────────────────

@app.get(f"{V}/payees")
def list_payees(customer_id: str):
    return envelope(q("SELECT * FROM payees WHERE customer_id=?", (customer_id,)))


class PaymentConsent(BaseModel):
    customer_id:  str
    from_account: str
    payee_id:     str
    amount:       float
    rail:         str
    reason:       Optional[str] = None


@app.post(f"{V}/payment-consents")
def create_payment_consent(req: PaymentConsent):
    payee = q("SELECT * FROM payees WHERE payee_id=?", (req.payee_id,), one=True)
    if not payee: raise HTTPException(404, "payee not found")
    cid = "PCN" + uuid.uuid4().hex[:8]
    otp = f"{random.randint(0, 999999):06d}"
    q("INSERT INTO payment_consents VALUES (?,?,?,?,?,?,?,?,?,?)",
      (cid, req.customer_id, req.from_account, req.payee_id, req.amount,
       req.rail, req.reason, "awaiting_authorisation", otp, datetime.utcnow().isoformat()))
    return envelope({"consent_id": cid, "status": "awaiting_authorisation",
                     "from_account": req.from_account, "payee": payee,
                     "amount": req.amount, "rail": req.rail,
                     "reason": req.reason, "_demo_otp": otp})


class Authorisation(BaseModel):
    consent_id: str
    otp:        str


@app.post(f"{V}/payments")
def execute_payment(req: Authorisation):
    c = q("SELECT * FROM payment_consents WHERE consent_id=?", (req.consent_id,), one=True)
    if not c: raise HTTPException(404, "consent not found")
    if c["status"] != "awaiting_authorisation":
        raise HTTPException(409, f"consent is {c['status']}")
    if req.otp != c["otp"]:
        raise HTTPException(401, "invalid OTP")
    q("UPDATE payment_consents SET status='consumed' WHERE consent_id=?", (req.consent_id,))
    pid = "PAY" + uuid.uuid4().hex[:8]
    q("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
      (pid, c["from_account"], c["amount"], "debit", c["rail"],
       "transfer", "success", None, c["payee_id"], pid, datetime.utcnow().isoformat()))
    q("UPDATE accounts SET balance=balance-? WHERE account_id=?",
      (c["amount"], c["from_account"]))
    return envelope({"payment_id": pid, "status": "success",
                     "rail": c["rail"], "amount": c["amount"]})


# ── Complaints ────────────────────────────────────────────────────────────────

class Complaint(BaseModel):
    customer_id: str
    txn_id:      Optional[str] = None
    category:    str
    description: str
    topics:      list[str] = []
    sentiment:   Optional[str] = None


@app.post(f"{V}/complaints")
def raise_complaint(req: Complaint):
    tid = "CMP" + uuid.uuid4().hex[:8]
    q("INSERT INTO complaints VALUES (?,?,?,?,?,?,?,?,?)",
      (tid, req.customer_id, req.txn_id, req.category, req.description,
       json.dumps(req.topics), req.sentiment, "open", datetime.utcnow().isoformat()))
    return envelope({"ticket_id": tid, "status": "open", "sla_hours": 48,
                     "topics": req.topics, "sentiment": req.sentiment})


@app.get(f"{V}/complaints")
def list_complaints(customer_id: str):
    rows = q("SELECT * FROM complaints WHERE customer_id=?", (customer_id,))
    for r in rows:
        if isinstance(r.get("topics"), str):
            try: r["topics"] = json.loads(r["topics"])
            except Exception: pass
    return envelope(rows)
