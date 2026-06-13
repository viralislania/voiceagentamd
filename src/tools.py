"""Tool registry — HTTP wrappers over the mock Open Banking backend.

Each function maps 1-to-1 with a FastAPI endpoint and returns the parsed JSON.
"""
from __future__ import annotations

import requests

from src.config import settings
import logging
logger = logging.getLogger(__name__)
def _get(path: str, **params) -> dict:
    r = requests.get(
        f"{settings.backend_url}{path}",
        params={k: v for k, v in params.items() if v is not None},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{settings.backend_url}{path}", json=body, timeout=10)
    r.raise_for_status()
    return r.json()


# ── AIS ──────────────────────────────────────────────────────────────────────

def get_accounts(customer_id: str)                          -> dict: return _get("/accounts", customer_id=customer_id)
def get_balance(account_id: str)                            -> dict: return _get(f"/accounts/{account_id}/balances")
def explain_failure(txn_id: str)                            -> dict: return _get(f"/transactions/{txn_id}/failure")

def get_statement(
    account_id: str,
    from_date: str | None = None,
    to_date:   str | None = None,
    category:  str | None = None,
    rail:      str | None = None,
    detailed:  bool = False,
) -> dict:
    logger.info(f"get_statement: account_id={account_id}, from_date={from_date}, to_date={to_date}, category={category}, rail={rail}, detailed={detailed}")
    return _post("/accounts/transactions/query", {
        "account_id": account_id, "from_date": from_date,
        "to_date": to_date, "category": category,
        "rail": rail, "detailed": detailed,
    })


# ── Deposits ─────────────────────────────────────────────────────────────────

def list_deposit_products(kind: str | None = None)          -> dict: return _get("/deposit-products", kind=kind)
def confirm_deposit(booking_id: str)                        -> dict: return _post(f"/deposit-bookings/{booking_id}/confirm", {})

def book_deposit(customer_id: str, product_id: str, amount: float, tenure_months: int) -> dict:
    return _post("/deposit-bookings", {
        "customer_id": customer_id, "product_id": product_id,
        "amount": amount, "tenure_months": tenure_months,
    })


# ── PIS ───────────────────────────────────────────────────────────────────────

def list_payees(customer_id: str)                           -> dict: return _get("/payees", customer_id=customer_id)
def execute_payment(consent_id: str, otp: str)              -> dict: return _post("/payments", {"consent_id": consent_id, "otp": otp})

def create_payment_consent(
    customer_id: str, from_account: str, payee_id: str,
    amount: float, rail: str, reason: str | None = None,
) -> dict:
    return _post("/payment-consents", {
        "customer_id": customer_id, "from_account": from_account,
        "payee_id": payee_id, "amount": amount, "rail": rail, "reason": reason,
    })


# ── Complaints ────────────────────────────────────────────────────────────────

def raise_complaint(
    customer_id: str, category: str, description: str,
    txn_id: str | None = None, topics: list[str] | None = None,
    sentiment: str | None = None,
) -> dict:
    return _post("/complaints", {
        "customer_id": customer_id, "category": category,
        "description": description, "txn_id": txn_id,
        "topics": topics or [], "sentiment": sentiment,
    })


# ── RAG ───────────────────────────────────────────────────────────────────────

def search_help_docs(query: str) -> list[dict]:
    from src.rag import retrieve
    return retrieve(query)


# ── Registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, callable] = {
    "get_accounts":            get_accounts,
    "get_balance":             get_balance,
    "get_statement":           get_statement,
    "explain_failure":         explain_failure,
    "list_deposit_products":   list_deposit_products,
    "book_deposit":            book_deposit,
    "confirm_deposit":         confirm_deposit,
    "list_payees":             list_payees,
    "create_payment_consent":  create_payment_consent,
    "execute_payment":         execute_payment,
    "raise_complaint":         raise_complaint,
    "search_help_docs":        search_help_docs,
}
