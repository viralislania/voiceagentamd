# Banking Voice/Text Agent — POC Build Plan

A platform-style conversational banking agent inspired by the CVS Health tiered-model blueprint, adapted for an Indian-context (English / Hindi / Hinglish) POC on a **single AMD MI300X**.

This document doubles as the **design-team input brief**: every use case below is written as a *journey* with the GenUI cards/screens it produces, and Section 6 + the companion `design_system_component_catalog.md` define the reusable component catalog the design team builds visual designs from. The developer-facing tokens/specs live in `developer_handoff.md`.

**Stack:** model provider abstraction (Gemini Flash 3.5 for local dev / vLLM-served Llama-3.1-8B for self-host) → LangGraph orchestration → Open-Banking-style mock FastAPI backend (SQLite + doc store) → A2UI / Flutter GenUI front end → optional MCP integration.

> **Model provider is configurable.** A single `LLM_PROVIDER` switch selects the backend: `gemini` (Gemini Flash 3.5, for fast local development with no GPU) or `vllm` (self-hosted Llama-3.1-8B, later the QLoRA-fine-tuned variant). The orchestrator code is provider-agnostic — see Section 5.0.

---

## 0. Design summary

### The use cases (five journeys, three interaction patterns)

| # | Use case | Pattern | Example query | GenUI output |
|---|----------|---------|---------------|--------------|
| 1 | **Balance & statement insights** | Structured retrieval + **progressive disclosure** | "Last week kitna kharch hua?" / "Shopping pe kitna spend kiya?" / "total UPI last month?" | Summary **amount card** → tap → **transaction list** drill-down |
| 2 | **Open deposit / savings** | **Transactional journey** | "मुझे ek FD खोलना है" / "open a recurring deposit" | **Product cards** → slot-fill widgets → **confirmation card** |
| 3 | **Knowledge repository** | **Knowledge RAG** | "FD ki minimum duration kya hai?" / "safe UPI kaise karein?" | Grounded **answer card** with source chips |
| 4 | **Fund transfer** | **Transactional journey + SCA** | "₹5000 transfer karna hai" | Rail picker (NEFT/IMPS) → **confirmation card** → **OTP step** |
| 5 | **Complaint** | **Action + insight extraction** | "mera transfer fail ho gaya aur paisa kat gaya" | Suggested-fix card or **ticket card**; voice→text + topic insights for support |

The **orchestrator's** core job is routing across these patterns. The single most valuable distinction to get right (a key fine-tuning target) is *"fetch my real numbers" → tool-call* (uc1/uc4) vs *"explain the policy" → RAG* (uc3).

### GenUI interaction model (progressive disclosure)

Every data answer starts **compact** and reveals detail **on user action** — this is the central UX idea the design team must support:

```
User: "How much did I spend last week?"
  → Agent emits  amount_summary_card  { ₹7,840 · 12 Jun–18 Jun · 9 txns }
User taps the card  (or says "show details")
  → Flutter sends a GenUI action event back to LangGraph
  → Agent resumes, calls get_statement(detailed=true), emits  transaction_list
User taps a single row
  → Agent emits  transaction_detail_card  (counterparty, status, category, ref no.)
```

The model never paints pixels. It emits **A2UI component references** against the catalog; the Flutter client renders native widgets and streams **action events** back so the graph can resume the journey. Cards are *interaction entry points*, not dead ends.

### The tiered-model principle (from CVS Health)

- **Fast tier (default):** the fine-tuned 8B handles intent routing, slot-filling, tool-calls, and A2UI emission for the vast majority of turns.
- **Escalation (optional, later):** only genuinely ambiguous multi-intent conversations escalate to a larger model. For the POC you can stub or skip this.
- **Deterministic shortcuts:** trivially classifiable intents (exact-match "balance") bypass the LLM via rules — the CVS "gatekeeper" idea, optionally realized as the HingBERT classifier (Section 5.7).

### What gets trained vs. engineered

| Component | Trained? |
|-----------|----------|
| ASR (Hindi/Hinglish speech→text) | Use AI4Bharat IndicConformer / IndicWhisper; light adapter only if banking terms fail |
| Orchestrator routing logic | **No** — LangGraph code |
| 8B brain (intent + slots + tool-calls + A2UI JSON) | **Yes** — QLoRA on synthetic data |
| Optional fast intent classifier (HingBERT) | Optional — small fine-tune (Section 5.7) |
| Mock backend / DB / doc store | **No** — plain code + seed data |
| A2UI rendering | **No** — Flutter GenUI + catalog |
| RAG retriever | **No** — embed + vector search |
| MCP servers | **No** — wrappers around backend |

---

## 1. Phased plan

**Phase A — Architecture first, zero-shot.** Stand up the mock backend, LangGraph graph, and the model behind the provider abstraction (Gemini Flash 3.5 locally; Llama-3.1-8B *un-fine-tuned* in vLLM). Validate all journeys end-to-end with few-shot prompting. Proves the wiring before investing in training.

**Phase B — Synthetic dataset with banking77** Generate journey traces (intent + slots + tool-calls + A2UI) across all patterns, in English/Hindi/Hinglish. Use banking77 to finetune model

**Phase C — QLoRA fine-tune** Llama-3.1-8B on the synthetic set. Goal: reliable structured output so you can stay at 8B and drop few-shot bloat.

**Phase D — Quantize & serve** the merged model (AWQ/GPTQ 4-bit) in vLLM; measure latency/quality, especially JSON validity.

**Phase E — A2UI + Flutter** wiring for all five journeys (FD/RD, statement drill-down, fund transfer + OTP, complaint, knowledge).

**Phase F — Voice** (IndicConformer ASR in front of the text pipeline).

**Phase G — MCP** (if time permits): re-expose backend tools via MCP servers.

---

## 2. Mock backend — Open-Banking-aligned

The backend deliberately mirrors **Open Banking** resource conventions (UK OBIE / India Account Aggregator + UPI framing) so the POC maps cleanly to a real integration later. Two API families:

- **AIS — Account Information Services** (read): accounts, balances, transactions.
- **PIS — Payment Initiation Services** (write): payment consent → authorization (SCA/OTP) → execution.

Resources are **noun-oriented and versioned** (`/open-banking/v1/...`), responses wrap data in a `Data` envelope, and money-moving calls require a **consent + Strong Customer Authentication (SCA/OTP)** step — exactly as PSD2/OBIE and UPI mandate. This makes the mock realistic without coupling the agent to any one bank's SDK.

### 2.1 Data model (SQLite)

```sql
-- schema.sql
CREATE TABLE customers (
    customer_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    phone         TEXT,
    kyc_verified  INTEGER DEFAULT 1
);

CREATE TABLE accounts (
    account_id    TEXT PRIMARY KEY,
    customer_id   TEXT REFERENCES customers(customer_id),
    account_type  TEXT,              -- 'savings' | 'current' | 'fd' | 'rd'
    balance       REAL DEFAULT 0,
    currency      TEXT DEFAULT 'INR',
    opened_on     TEXT
);

CREATE TABLE transactions (
    txn_id        TEXT PRIMARY KEY,
    account_id    TEXT REFERENCES accounts(account_id),
    amount        REAL,
    direction     TEXT,              -- 'debit' | 'credit'
    rail          TEXT,              -- 'upi' | 'neft' | 'imps' | 'card' | 'ach'
    category      TEXT,              -- 'food','shopping','transfer','bills','salary',...
    status        TEXT,              -- 'success' | 'failed' | 'pending'
    failure_code  TEXT,              -- NULL unless failed
    counterparty  TEXT,
    reference_no  TEXT,
    created_at    TEXT
);

CREATE TABLE deposit_products (
    product_id    TEXT PRIMARY KEY,
    kind          TEXT,              -- 'fd' | 'rd'
    name          TEXT,
    min_amount    REAL,
    max_amount    REAL,
    tenure_months INTEGER,
    interest_rate REAL
);

CREATE TABLE deposit_bookings (
    booking_id    TEXT PRIMARY KEY,
    customer_id   TEXT,
    product_id    TEXT,
    amount        REAL,
    tenure_months INTEGER,
    status        TEXT,              -- 'created' | 'confirmed'
    created_at    TEXT
);

CREATE TABLE payees (
    payee_id      TEXT PRIMARY KEY,
    customer_id   TEXT,
    name          TEXT,
    account_number TEXT,
    ifsc          TEXT
);

CREATE TABLE payment_consents (
    consent_id    TEXT PRIMARY KEY,
    customer_id   TEXT,
    from_account  TEXT,
    payee_id      TEXT,
    amount        REAL,
    rail          TEXT,              -- 'neft' | 'imps'
    reason        TEXT,
    status        TEXT,              -- 'awaiting_authorisation' | 'authorised' | 'rejected' | 'consumed'
    otp           TEXT,              -- mock SCA challenge
    created_at    TEXT
);

CREATE TABLE complaints (
    ticket_id     TEXT PRIMARY KEY,
    customer_id   TEXT,
    txn_id        TEXT,
    category      TEXT,
    description   TEXT,
    topics        TEXT,              -- JSON array of extracted insight topics
    sentiment     TEXT,              -- 'angry' | 'frustrated' | 'neutral'
    status        TEXT DEFAULT 'open',
    created_at    TEXT
);
```

### 2.2 Failure-code reference (for use case #1/#5)

```python
# failure_codes.py — maps backend codes to human explanations + next steps
FAILURE_CODES = {
    "INSUFFICIENT_FUNDS": {
        "reason": "The account balance was lower than the transfer amount.",
        "next_steps": ["Add funds and retry", "Try a smaller amount"],
        "complaint_eligible": False,
    },
    "DAILY_LIMIT_EXCEEDED": {
        "reason": "The transfer exceeded the daily transaction limit.",
        "next_steps": ["Retry tomorrow", "Request a limit increase"],
        "complaint_eligible": False,
    },
    "BENEFICIARY_BANK_DOWN": {
        "reason": "The beneficiary bank's systems were temporarily unavailable.",
        "next_steps": ["Retry after some time", "Raise a complaint if debited"],
        "complaint_eligible": True,
    },
    "TIMEOUT": {
        "reason": "The transaction timed out at the network switch.",
        "next_steps": ["Check if amount was debited", "Raise a complaint if debited"],
        "complaint_eligible": True,
    },
}
```

### 2.3 API surface (Open-Banking-style)

Each endpoint maps 1:1 to a **tool** the LLM can invoke. AIS endpoints are reads; PIS endpoints implement the **consent → SCA/OTP → execute** flow.

```python
# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3, uuid, json, random
from failure_codes import FAILURE_CODES

app = FastAPI(title="Mock Open Banking Backend")
DB = "bank.db"
V = "/open-banking/v1"

def q(sql, args=(), one=False):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    cur = con.execute(sql, args); rows = cur.fetchall()
    con.commit(); con.close()
    rows = [dict(r) for r in rows]
    return (rows[0] if rows else None) if one else rows

def envelope(data):                       # OBIE-style response wrapper
    return {"Data": data, "Meta": {"TotalRecords": len(data) if isinstance(data, list) else 1}}

# ========== AIS — Account Information Services (read) ==========
@app.get(f"{V}/accounts")
def get_accounts(customer_id: str):
    return envelope(q("SELECT * FROM accounts WHERE customer_id=?", (customer_id,)))

@app.get(f"{V}/accounts/{{account_id}}/balances")
def get_balance(account_id: str):
    acc = q("SELECT account_id,balance,currency FROM accounts WHERE account_id=?",
            (account_id,), one=True)
    if not acc: raise HTTPException(404, "account not found")
    return envelope(acc)

class StatementQuery(BaseModel):
    account_id: str
    from_date: str | None = None   # ISO date
    to_date: str | None = None
    category: str | None = None    # 'shopping','food',...
    rail: str | None = None        # 'upi','neft','imps',...
    detailed: bool = False         # GenUI: summary first, list on drill-down

@app.post(f"{V}/accounts/transactions/query")
def get_statement(req: StatementQuery):
    sql = "SELECT * FROM transactions WHERE account_id=?"; args = [req.account_id]
    if req.from_date: sql += " AND created_at>=?"; args.append(req.from_date)
    if req.to_date:   sql += " AND created_at<=?"; args.append(req.to_date)
    if req.category:  sql += " AND category=?";    args.append(req.category)
    if req.rail:      sql += " AND rail=?";        args.append(req.rail)
    sql += " ORDER BY created_at DESC"
    txns = q(sql, tuple(args))
    spent    = sum(t["amount"] for t in txns if t["direction"]=="debit"  and t["status"]=="success")
    received = sum(t["amount"] for t in txns if t["direction"]=="credit" and t["status"]=="success")
    summary = {"total_spent": spent, "total_received": received, "count": len(txns),
               "from_date": req.from_date, "to_date": req.to_date,
               "category": req.category, "rail": req.rail}
    # progressive disclosure: list only when the user drills in
    return envelope({**summary, "transactions": txns if req.detailed else []})

@app.get(f"{V}/transactions/{{txn_id}}/failure")
def explain_failure(txn_id: str):
    t = q("SELECT * FROM transactions WHERE txn_id=?", (txn_id,), one=True)
    if not t: raise HTTPException(404, "txn not found")
    if t["status"] != "failed":
        return envelope({"txn_id": txn_id, "status": t["status"], "explanation": None})
    info = FAILURE_CODES.get(t["failure_code"], {})
    return envelope({"txn_id": txn_id, "status": "failed",
                     "failure_code": t["failure_code"], **info})

# ========== Deposits — FD / RD journey ==========
@app.get(f"{V}/deposit-products")
def list_deposit_products(kind: str | None = None):   # kind='fd'|'rd'
    if kind: return envelope(q("SELECT * FROM deposit_products WHERE kind=? ORDER BY tenure_months",(kind,)))
    return envelope(q("SELECT * FROM deposit_products ORDER BY kind, tenure_months"))

class DepositBooking(BaseModel):
    customer_id: str
    product_id: str
    amount: float
    tenure_months: int

@app.post(f"{V}/deposit-bookings")
def book_deposit(req: DepositBooking):
    p = q("SELECT * FROM deposit_products WHERE product_id=?", (req.product_id,), one=True)
    if not p: raise HTTPException(404, "product not found")
    if not (p["min_amount"] <= req.amount <= p["max_amount"]):
        raise HTTPException(400, f"amount must be between {p['min_amount']} and {p['max_amount']}")
    bid = "DEP" + uuid.uuid4().hex[:8]
    q("INSERT INTO deposit_bookings VALUES (?,?,?,?,?,?,?)",
      (bid, req.customer_id, req.product_id, req.amount, req.tenure_months,
       "created", datetime.utcnow().isoformat()))
    return envelope({"booking_id": bid, "status": "created", "product": p["name"],
                     "kind": p["kind"], "amount": req.amount,
                     "tenure_months": req.tenure_months, "interest_rate": p["interest_rate"]})

@app.post(f"{V}/deposit-bookings/{{booking_id}}/confirm")
def confirm_deposit(booking_id: str):
    q("UPDATE deposit_bookings SET status='confirmed' WHERE booking_id=?", (booking_id,))
    return envelope({"booking_id": booking_id, "status": "confirmed"})

# ========== PIS — Payment Initiation (fund transfer + SCA/OTP) ==========
@app.get(f"{V}/payees")
def list_payees(customer_id: str):
    return envelope(q("SELECT * FROM payees WHERE customer_id=?", (customer_id,)))

class PaymentConsent(BaseModel):
    customer_id: str
    from_account: str
    payee_id: str
    amount: float
    rail: str                       # 'neft' | 'imps'
    reason: str | None = None

@app.post(f"{V}/payment-consents")
def create_payment_consent(req: PaymentConsent):
    # Stage the payment; issue a mock SCA (OTP) challenge. No money moves yet.
    cid = "PCN" + uuid.uuid4().hex[:8]; otp = f"{random.randint(0,999999):06d}"
    q("INSERT INTO payment_consents VALUES (?,?,?,?,?,?,?,?,?,?)",
      (cid, req.customer_id, req.from_account, req.payee_id, req.amount, req.rail,
       req.reason, "awaiting_authorisation", otp, datetime.utcnow().isoformat()))
    payee = q("SELECT * FROM payees WHERE payee_id=?", (req.payee_id,), one=True)
    # In the POC the OTP is returned for demo; in real SCA it is sent out-of-band.
    return envelope({"consent_id": cid, "status": "awaiting_authorisation",
                     "from_account": req.from_account, "payee": payee,
                     "amount": req.amount, "rail": req.rail, "reason": req.reason,
                     "_demo_otp": otp})

class Authorisation(BaseModel):
    consent_id: str
    otp: str

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
    # record the debit
    q("""INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
      (pid, c["from_account"], c["amount"], "debit", c["rail"], "transfer",
       "success", None, c["payee_id"], pid, datetime.utcnow().isoformat()))
    return envelope({"payment_id": pid, "status": "success", "rail": c["rail"],
                     "amount": c["amount"]})

# ========== Complaints (voice→text + insight extraction) ==========
class Complaint(BaseModel):
    customer_id: str
    txn_id: str | None = None
    category: str
    description: str
    topics: list[str] = []          # extracted by the agent before posting
    sentiment: str | None = None

@app.post(f"{V}/complaints")
def raise_complaint(req: Complaint):
    tid = "CMP" + uuid.uuid4().hex[:8]
    q("INSERT INTO complaints VALUES (?,?,?,?,?,?,?,?,?)",
      (tid, req.customer_id, req.txn_id, req.category, req.description,
       json.dumps(req.topics), req.sentiment, "open", datetime.utcnow().isoformat()))
    return envelope({"ticket_id": tid, "status": "open", "sla_hours": 48,
                     "topics": req.topics, "sentiment": req.sentiment})
```

### 2.4 Seed script

```python
# seed.py
import sqlite3, uuid
from datetime import datetime, timedelta

con = sqlite3.connect("bank.db")
con.executescript(open("schema.sql").read())

con.execute("INSERT INTO customers VALUES (?,?,?,?)",
            ("CUST001", "Asha Verma", "+91900000001", 1))
con.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
            ("ACC001", "CUST001", "savings", 84250.0, "INR", "2021-03-10"))

now = datetime.utcnow()
# rail + category populated so uc1 spend-by-category / spend-by-rail queries work
txns = [
  ("TXN001","ACC001",1200,"debit","upi","food",    "success",None,"Zomato","TXN001",(now-timedelta(days=2)).isoformat()),
  ("TXN002","ACC001",5000,"debit","imps","transfer","failed","BENEFICIARY_BANK_DOWN","R. Sharma","TXN002",(now-timedelta(days=1)).isoformat()),
  ("TXN003","ACC001",45000,"credit","neft","salary","success",None,"ACME Corp","TXN003",(now-timedelta(days=5)).isoformat()),
  ("TXN004","ACC001",800,"debit","upi","bills",   "success",None,"Electricity","TXN004",(now-timedelta(days=3)).isoformat()),
  ("TXN005","ACC001",3499,"debit","card","shopping","success",None,"Myntra","TXN005",(now-timedelta(days=4)).isoformat()),
  ("TXN006","ACC001",2150,"debit","upi","shopping","success",None,"Amazon","TXN006",(now-timedelta(days=6)).isoformat()),
]
con.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)", txns)

deps = [
  ("FDP001","fd","Short-Term FD",  10000,1000000, 6,  6.5),
  ("FDP002","fd","Standard FD",    10000,1000000,12,  7.1),
  ("FDP003","fd","Long-Term FD",   25000,5000000,36,  7.4),
  ("RDP001","rd","Recurring 12m",   500, 100000,12,  6.8),
  ("RDP002","rd","Recurring 24m",   500, 100000,24,  7.0),
]
con.executemany("INSERT INTO deposit_products VALUES (?,?,?,?,?,?,?)", deps)

con.execute("INSERT INTO payees VALUES (?,?,?,?,?)",
            ("PYE001","CUST001","Rahul Mehta","1234567890","HDFC0001234"))
con.commit(); con.close()
print("seeded bank.db")
```

### 2.5 Document store for RAG (use case #3)

A handful of help docs (markdown or PDF). Keep them short; demonstrate retrieval, not corpus scale. The knowledge repository is the **same** doc-RAG surface the agent queries for feature/FAQ questions ("FD minimum duration", "safe UPI practices").

```
docs/
  how_to_open_savings.md
  how_to_open_fd.md
  how_to_open_rd.md
  fees_and_charges.md
  kyc_requirements.md
  fund_transfer_neft_vs_imps.md
  safe_upi_practices.md
  transaction_failure_faq.md
```

Index with a lightweight embedding model + FAISS:

```python
# rag_index.py
from sentence_transformers import SentenceTransformer
import faiss, glob, pickle, numpy as np

embedder = SentenceTransformer("intfloat/multilingual-e5-small")  # handles Hi/Hinglish
chunks, meta = [], []
for path in glob.glob("docs/*.md"):
    text = open(path).read()
    for para in [p for p in text.split("\n\n") if p.strip()]:
        chunks.append(para); meta.append({"source": path})
emb = embedder.encode(["passage: " + c for c in chunks], normalize_embeddings=True)
index = faiss.IndexFlatIP(emb.shape[1]); index.add(np.array(emb, dtype="float32"))
faiss.write_index(index, "docs.faiss")
pickle.dump({"chunks": chunks, "meta": meta}, open("docs_meta.pkl","wb"))
```

```python
# rag_query.py
def retrieve(query, k=3):
    import faiss, pickle, numpy as np
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer("intfloat/multilingual-e5-small")
    index = faiss.read_index("docs.faiss")
    store = pickle.load(open("docs_meta.pkl","rb"))
    qv = embedder.encode(["query: " + query], normalize_embeddings=True)
    D, I = index.search(np.array(qv, dtype="float32"), k)
    return [{"text": store["chunks"][i], "source": store["meta"][i]["source"],
             "score": float(D[0][rank])} for rank, i in enumerate(I[0])]
```

---

## 3. Tool definitions (the bridge to the LLM)

These tool schemas are given to the model. Each maps to an Open-Banking endpoint.

```python
# tools.py
import requests
BASE = "http://localhost:8000/open-banking/v1"

def get_balance(account_id: str):
    return requests.get(f"{BASE}/accounts/{account_id}/balances").json()

def get_statement(account_id, from_date=None, to_date=None, category=None, rail=None, detailed=False):
    return requests.post(f"{BASE}/accounts/transactions/query", json={
        "account_id": account_id, "from_date": from_date, "to_date": to_date,
        "category": category, "rail": rail, "detailed": detailed}).json()

def explain_failure(txn_id: str):
    return requests.get(f"{BASE}/transactions/{txn_id}/failure").json()

def list_deposit_products(kind=None):
    return requests.get(f"{BASE}/deposit-products", params={"kind": kind}).json()

def book_deposit(customer_id, product_id, amount, tenure_months):
    return requests.post(f"{BASE}/deposit-bookings", json={
        "customer_id": customer_id, "product_id": product_id,
        "amount": amount, "tenure_months": tenure_months}).json()

def confirm_deposit(booking_id: str):
    return requests.post(f"{BASE}/deposit-bookings/{booking_id}/confirm").json()

def list_payees(customer_id: str):
    return requests.get(f"{BASE}/payees", params={"customer_id": customer_id}).json()

def create_payment_consent(customer_id, from_account, payee_id, amount, rail, reason=None):
    return requests.post(f"{BASE}/payment-consents", json={
        "customer_id": customer_id, "from_account": from_account, "payee_id": payee_id,
        "amount": amount, "rail": rail, "reason": reason}).json()

def execute_payment(consent_id, otp):
    return requests.post(f"{BASE}/payments", json={"consent_id": consent_id, "otp": otp}).json()

def raise_complaint(customer_id, category, description, txn_id=None, topics=None, sentiment=None):
    return requests.post(f"{BASE}/complaints", json={
        "customer_id": customer_id, "category": category, "description": description,
        "txn_id": txn_id, "topics": topics or [], "sentiment": sentiment}).json()

def search_help_docs(query: str):
    from rag_query import retrieve
    return retrieve(query, k=3)

TOOL_REGISTRY = {
    "get_balance": get_balance, "get_statement": get_statement,
    "explain_failure": explain_failure, "list_deposit_products": list_deposit_products,
    "book_deposit": book_deposit, "confirm_deposit": confirm_deposit,
    "list_payees": list_payees, "create_payment_consent": create_payment_consent,
    "execute_payment": execute_payment, "raise_complaint": raise_complaint,
    "search_help_docs": search_help_docs,
}
```

---

## 4. LangGraph orchestration

This is the CVS "Master Agent + specialists" pattern as a state graph.

### 4.1 Graph shape

```
                       ┌─────────────┐
                       │  classify   │  (intent router; LLM or HingBERT)
                       └──────┬──────┘
   ┌────────────┬─────────────┼──────────────┬───────────────┬────────────┐
   ▼            ▼             ▼              ▼               ▼            ▼
deposit_   data_query   transfer_      failure→        knowledge_   fallback
journey    (uc1: card   journey        complaint       rag (uc3)
(uc2)      → drilldown) (uc4: rail→    (uc5)
                         confirm→OTP)
   │            │             │              │               │            │
   └────────────┴─────────────┴──────┬───────┴───────────────┴────────────┘
                                      ▼
                               response + A2UI  ── action event ──┐
                                      ▲                            │
                                      └──── resume on user tap ────┘
```

Journeys are **resumable**: a node can emit an A2UI card and pause (`done=False`); when Flutter posts the user's action (tap/selection/OTP), the graph re-enters the same node with the new slot filled. This is what powers uc1's card→list drill-down and uc4's confirm→OTP step.

### 4.2 State

```python
# state.py
from typing import TypedDict, Optional
class AgentState(TypedDict):
    customer_id: str
    user_msg: str
    intent: Optional[str]
    slots: dict                 # accumulated across turns
    pending_slot: Optional[str] # what we still need to ask
    pending_action: Optional[str]   # 'show_txn_detail' | 'await_otp' | ...
    tool_result: Optional[dict]
    response_text: Optional[str]
    a2ui: Optional[dict]        # UI payload for Flutter
    done: bool
```

### 4.3 Intent registry (replaces the bare list — see Section 4.5)

```python
# intents.py — config-driven registry, NOT a hardcoded list
INTENT_REGISTRY = {
  "open_fixed_deposit":  {"handler": "deposit_journey", "required": ["product_id","amount","tenure_months"]},
  "open_recurring_deposit": {"handler": "deposit_journey", "required": ["product_id","amount","tenure_months"]},
  "open_savings":        {"handler": "deposit_journey", "required": []},
  "account_statement":   {"handler": "data_query",      "required": []},
  "balance_inquiry":     {"handler": "data_query",      "required": []},
  "fund_transfer":       {"handler": "transfer_journey","required": ["payee_id","amount","rail"]},
  "transaction_failure": {"handler": "failure_flow",    "required": []},
  "raise_complaint":     {"handler": "complaint_flow",  "required": ["description"]},
  "help_knowledge":      {"handler": "knowledge_rag",   "required": []},
  "fallback":            {"handler": "fallback",        "required": []},
}
INTENTS = list(INTENT_REGISTRY)   # passed to the classifier prompt
```

### 4.4 Nodes (selected — new/changed flows)

```python
# graph.py (excerpt)
def classify(state):
    out = llm_classify(state["user_msg"], INTENTS, history=state.get("slots"))
    state["intent"] = out["intent"]
    state["slots"] = {**state.get("slots", {}), **out.get("slots", {})}
    return state

def route(state):
    return INTENT_REGISTRY.get(state["intent"], INTENT_REGISTRY["fallback"])["handler"]

# --- uc1: balance / statement with progressive disclosure ---
def data_query(state):
    slots, acc = state["slots"], state["slots"].get("account_id","ACC001")
    # drill-down: user tapped the summary card -> emit the detailed list
    if state.get("pending_action") == "show_txn_detail":
        res = TOOL_REGISTRY["get_statement"](acc, slots.get("from_date"),
              slots.get("to_date"), slots.get("category"), slots.get("rail"), detailed=True)
        state["a2ui"] = build_transaction_list(res["Data"]["transactions"])
        state["response_text"] = "Here's the full list."
        state["pending_action"] = None; state["done"] = True
        return state
    if state["intent"] == "balance_inquiry":
        res = TOOL_REGISTRY["get_balance"](acc)
        state["a2ui"] = build_balance_card(res["Data"])
    else:
        res = TOOL_REGISTRY["get_statement"](acc, slots.get("from_date"),
              slots.get("to_date"), slots.get("category"), slots.get("rail"), detailed=False)
        # compact amount card FIRST; list appears only when the user taps it
        state["a2ui"] = build_amount_summary_card(res["Data"], on_tap="show_txn_detail")
    state["tool_result"] = res
    state["response_text"] = format_numbers(res["Data"], state["user_msg"])  # never invents numbers
    state["done"] = True
    return state

# --- uc2: deposit journey (FD/RD product cards -> slot fill -> confirm) ---
def deposit_journey(state):
    slots = state["slots"]
    if "product_id" not in slots:
        kind = "rd" if state["intent"]=="open_recurring_deposit" else "fd"
        products = TOOL_REGISTRY["list_deposit_products"](kind)["Data"]
        state["a2ui"] = build_product_cards(products)   # tappable product cards
        state["response_text"] = "Here are the available products."
        state["pending_slot"] = "product_id"; state["done"] = False
        return state
    for s in ["amount","tenure_months"]:
        if s not in slots:
            state["pending_slot"] = s
            state["a2ui"] = build_deposit_input_widget(s, slots["product_id"])
            state["response_text"] = ask_for_slot(s); state["done"] = False
            return state
    res = TOOL_REGISTRY["book_deposit"](state["customer_id"], slots["product_id"],
                                        slots["amount"], slots["tenure_months"])["Data"]
    state["a2ui"] = build_deposit_confirmation(res)     # confirmation card + Confirm button
    state["response_text"] = summarize_deposit(res); state["done"] = True
    return state

# --- uc4: fund transfer (ask rail -> confirm -> OTP/SCA) ---
def transfer_journey(state):
    slots = state["slots"]
    if "payee_id" not in slots:
        payees = TOOL_REGISTRY["list_payees"](state["customer_id"])["Data"]
        state["a2ui"] = build_payee_picker(payees)
        state["response_text"] = "Who would you like to pay?"; state["done"] = False
        return state
    if "amount" not in slots:
        state["pending_slot"] = "amount"; state["a2ui"] = build_amount_entry()
        state["response_text"] = "How much would you like to transfer?"; state["done"] = False
        return state
    if "rail" not in slots:                              # the NEFT vs IMPS follow-up
        state["pending_slot"] = "rail"
        state["a2ui"] = build_rail_picker(["NEFT","IMPS"])
        state["response_text"] = "Which transfer type — NEFT or IMPS?"; state["done"] = False
        return state
    if state.get("pending_action") != "await_otp":
        # stage consent, show confirmation card (from/to/amount/reason), request OTP
        consent = TOOL_REGISTRY["create_payment_consent"](state["customer_id"],
            slots.get("from_account","ACC001"), slots["payee_id"], slots["amount"],
            slots["rail"].lower(), slots.get("reason"))["Data"]
        state["slots"]["consent_id"] = consent["consent_id"]
        state["a2ui"] = build_transfer_confirmation(consent)   # review card + OTP field
        state["response_text"] = "Please review and enter the OTP to authorise."
        state["pending_action"] = "await_otp"; state["done"] = False
        return state
    # OTP submitted -> execute (multi-factor confirmation)
    res = TOOL_REGISTRY["execute_payment"](slots["consent_id"], slots["otp"])["Data"]
    state["a2ui"] = build_transfer_success(res)
    state["response_text"] = f"₹{res['amount']:.0f} sent via {res['rail'].upper()}."
    state["pending_action"] = None; state["done"] = True
    return state

# --- uc5: complaint (voice->text + topic/sentiment insights for support) ---
def complaint_flow(state):
    slots = state["slots"]
    if "description" not in slots:
        state["pending_slot"] = "description"
        state["response_text"] = "Please describe the issue in a sentence."
        state["done"] = False; return state
    # extract insight topics + sentiment from the (transcribed) complaint text
    insights = extract_complaint_insights(slots["description"])   # {topics:[...], sentiment:...}
    suggestion = suggest_self_fix(insights["topics"])             # may resolve without a ticket
    if suggestion:
        state["a2ui"] = build_suggested_fix_card(suggestion)
        state["response_text"] = suggestion["message"]; state["done"] = True
        return state
    res = TOOL_REGISTRY["raise_complaint"](state["customer_id"],
        slots.get("category","transaction"), slots["description"], slots.get("txn_id"),
        topics=insights["topics"], sentiment=insights["sentiment"])["Data"]
    state["a2ui"] = build_ticket_card(res)   # ticket id + SLA + detected topics chips
    state["response_text"] = f"Complaint raised. Ticket {res['ticket_id']}, SLA {res['sla_hours']}h."
    state["done"] = True
    return state
```

The `llm_classify`, `format_numbers`, `synthesize_answer`, `extract_complaint_insights`, `suggest_self_fix`, `ask_for_slot`, and `build_*` helpers are thin wrappers around the model provider (Section 5.0) and the A2UI catalog (Section 6 + `design_system_component_catalog.md`).

### 4.5 Is a flat `INTENTS` list scalable? (your question, answered)

**Short answer:** a flat Python list is perfectly fine for a *POC* with ≤ ~15 intents — it is how small intent-routed agents are normally bootstrapped, and it keeps the classifier prompt simple. It is **not** how you'd scale past a couple dozen intents or multiple product lines. The list has three structural weaknesses as it grows:

1. **The list is only half the contract.** A bare `INTENTS = [...]` still needs a parallel routing dict, a slot spec, an escalation policy, and prompt examples — kept in sync by hand. They drift.
2. **Prompt cost & confusion grow with N.** Every intent is enumerated in the classifier prompt each turn; at 40–50 intents accuracy degrades and latency/cost rise.
3. **No grouping.** Real banks have *domains* (deposits, payments, cards, loans, disputes) each with sub-intents. A flat namespace can't express that.

**Recommended evolution (already reflected in Section 4.3):**

- **Now (POC):** replace the bare list with a **config-driven `INTENT_REGISTRY`** — each intent carries its `handler`, `required` slots, and (later) `escalation` policy as metadata. `INTENTS = list(INTENT_REGISTRY)` is derived, so there's one source of truth. This is a one-line change in spirit but removes the drift problem.
- **Next:** make the registry **data, not code** — load from YAML/JSON (or a DB table) so product/ops can add an intent without a code deploy. Validate with a schema.
- **At scale:** go **hierarchical** (domain → sub-intent: `payments.fund_transfer`, `deposits.open_fd`) and/or **retrieval-based routing** — embed a few utterances per intent, match the user turn by nearest-neighbour, and only enumerate the top-k candidate intents in the LLM prompt. This keeps the prompt small no matter how many intents exist and lets you add intents without retraining the router.
- **Governance:** treat the intent taxonomy as a versioned artifact (the same way the A2UI catalog is versioned). New intent = new registry entry + seed utterances + handler + eval cases.

So: keep the list for the POC, but wrap it in the registry from day one. It costs nothing now and saves a refactor later.

---

## 5. Model provider + fine-tuning the 8B (QLoRA on MI300X / ROCm)

### 5.0 Provider abstraction (Gemini Flash 3.5 local · vLLM Llama-3.1-8B self-host)

One interface, two backends, selected by config. Develop locally against **Gemini Flash 3.5** (no GPU, fast iteration on prompts/graph), then flip to **vLLM-served Llama-3.1-8B** (and later the QLoRA-fine-tuned merge) for self-hosted inference — no orchestrator code changes.

```python
# llm.py
import os, requests, json
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")   # 'gemini' | 'vllm'

def chat(messages, json_mode=False, temperature=0.0):
    if LLM_PROVIDER == "gemini":
        return _gemini(messages, json_mode, temperature)      # Gemini Flash 3.5, local dev
    return _vllm(messages, json_mode, temperature)            # Llama-3.1-8B via vLLM

def _gemini(messages, json_mode, temperature):
    import google.genai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-flash-3.5")
    cfg = {"temperature": temperature}
    if json_mode: cfg["response_mime_type"] = "application/json"
    return model.generate_content([m["content"] for m in messages],
                                  generation_config=cfg).text

def _vllm(messages, json_mode, temperature):
    base = os.getenv("VLLM_URL", "http://localhost:8001/v1")
    body = {"model": os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
            "messages": messages, "temperature": temperature}
    if json_mode: body["response_format"] = {"type": "json_object"}
    r = requests.post(f"{base}/chat/completions", json=body).json()
    return r["choices"][0]["message"]["content"]
```

> Use `json_mode=True` for `classify` and all tool-call/A2UI emission so both providers return strict JSON. Validate every JSON payload before acting on it; on parse failure, one repair retry, else `fallback`.

### 5.1 Why 8B + QLoRA + quantization (recap)

- **8B is right-sized** for bounded tasks: fixed intent set, fixed tools, fixed widget catalog.
- **QLoRA** = load base in 4-bit, train small LoRA adapters. Cheap, fast, base stays swappable. MI300X's 192 GB gives huge headroom.
- **Serve quantized** (AWQ/GPTQ 4-bit) for latency/throughput. **Test JSON validity** after quantizing; if tool-call/A2UI formatting slips, fall back to 8-bit.

### 5.2 Base model

Primary target for self-hosted serving is **Llama-3.1-8B-Instruct** (best ecosystem/tooling, excellent tool-calling). If Hinglish becomes the bottleneck during eval, an Indic-tuned 7–8B (Sarvam-class) or Qwen2.5-7B-Instruct are drop-in alternatives behind the same provider interface.

| Model | Tool-calling | Multilingual (Hi/Hinglish) | Notes |
|-------|-------------|---------------------------|-------|
| **Llama-3.1-8B-Instruct** (primary) | Excellent | Decent | Best ecosystem/tooling; vLLM-served |
| Qwen2.5-7B-Instruct | Excellent | Strong | Great structured-output reliability |
| Indic-tuned 7–8B (Sarvam-class) | Good | Strongest Hi | Use if Hinglish is the bottleneck |

### 5.3 ROCm environment

```bash
# MI300X uses ROCm. Use AMD's PyTorch ROCm wheels.
pip install --index-url https://download.pytorch.org/whl/rocm6.2 torch torchvision torchaudio
pip install transformers peft trl datasets accelerate bitsandbytes
# vLLM has ROCm builds; install the ROCm variant for serving (section 5.6).
```

> Note on quantization libs: `bitsandbytes` 4-bit (QLoRA) and AWQ/GPTQ kernels have ROCm support that evolves quickly. Verify current ROCm-compatible versions at setup; if 4-bit training is unstable on your ROCm version, QLoRA can fall back to 8-bit loading — still cheap given 192 GB.

### 5.4 Training data format

Each example is a chat with the target output the model must learn — strict JSON for classification/tool-calls, natural language (grounded) for RAG answers. (Schema and examples in section 8.)

### 5.5 QLoRA training script

```python
# train_qlora.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

BASE = "meta-llama/Llama-3.1-8B-Instruct"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(
    BASE, quantization_config=bnb, device_map="auto", torch_dtype=torch.bfloat16)
lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
model = get_peft_model(model, lora)
ds = load_dataset("json", data_files={"train":"data/train.jsonl","eval":"data/eval.jsonl"})
cfg = SFTConfig(output_dir="out/bank-8b-lora", num_train_epochs=3,
    per_device_train_batch_size=4, gradient_accumulation_steps=4,
    learning_rate=2e-4, bf16=True, logging_steps=10,
    eval_strategy="steps", eval_steps=100, save_steps=200,
    max_seq_length=2048, packing=True)
trainer = SFTTrainer(model=model, args=cfg, processing_class=tok,
    train_dataset=ds["train"], eval_dataset=ds["eval"])
trainer.train(); trainer.save_model("out/bank-8b-lora")
```

### 5.6 Merge + quantize for serving

```bash
# 1) merge LoRA into base
python -c "
from peft import AutoPeftModelForCausalLM
m = AutoPeftModelForCausalLM.from_pretrained('out/bank-8b-lora')
m = m.merge_and_unload(); m.save_pretrained('out/bank-8b-merged')
from transformers import AutoTokenizer
AutoTokenizer.from_pretrained('meta-llama/Llama-3.1-8B-Instruct').save_pretrained('out/bank-8b-merged')
"
# 2) serve with vLLM (ROCm). Validate JSON validity on a held-out set BEFORE committing to 4-bit.
vllm serve out/bank-8b-merged --quantization awq --max-model-len 4096 --port 8001
```

### 5.7 Optional fast intent classifier — HingBERT (scope)

**What it is.** A tiny **encoder** classifier (`l3cube-pune/hing-bert`, ~110M params) fine-tuned on *intent labels only*. It sits in front of the 8B as the CVS-style "SLM gatekeeper": classify the easy, high-confidence turns in ~10–20 ms on CPU, and **escalate only ambiguous turns** to the LLM.

**Scope — in.**
- Single-label intent classification over the `INTENT_REGISTRY` labels (8–10 classes for the POC).
- A **confidence threshold** (e.g. softmax max ≥ 0.85) gates the shortcut; below it, fall through to `llm_classify`.
- Trains on the *same* synthetic seed utterances used for the LLM (Section 8) — labels are free, no extra annotation.
- Targets the high-frequency, unambiguous turns: "balance", "statement dekhana", "FD kholna", "paisa transfer".

**Scope — out (stays with the 8B).**
- **Slot extraction** (amount, tenure, dates, payee, rail) — HingBERT classifies intent, it does *not* fill slots. The 8B remains the slot/JSON/tool-call/A2UI engine.
- Multi-intent or context-dependent turns ("usme se details dikhao" after a card) — these need conversation state the encoder doesn't see; route to the LLM.
- Anything below threshold or labelled `fallback`.

**Effort & payoff.** ~1–2 hours to fine-tune on a few hundred labelled utterances; a few MB adapter. Payoff is latency/cost: it keeps the LLM out of the easy ~80% of turns. **It is strictly optional** — the system is fully functional with the LLM classifier alone, so treat HingBERT as a Phase-G-style optimization, not a dependency. Build and measure the LLM-only path first; add HingBERT only if per-turn latency/cost is a demonstrated problem.

---

## 6. A2UI / Flutter GenUI front end

The agent emits **A2UI JSON** referencing a **widget catalog you define**; the Flutter client renders native widgets. No model training here — it's prompt + catalog. The **full reusable component catalog (the design-team deliverable)** is specified in `design_system_component_catalog.md`; tokens and responsive specs are in `developer_handoff.md`. This section is the integration summary.

### 6.1 How it fits

- LangGraph nodes produce `state["a2ui"]` payloads.
- A2UI payload streams to Flutter over WebSocket/SSE via the `genui_a2ui` package (`A2uiAgentConnector` → `GenUiSurface`).
- The model never emits Flutter code — only structured component references the client validates.
- Flutter posts **action events** (taps, selections, OTP entry) back; LangGraph resumes the journey (the drill-down and OTP loops).

### 6.2 Catalog at a glance (full spec in the design doc)

| Journey | Key components |
|---------|----------------|
| uc1 Statement | `amount_summary_card`, `transaction_list`, `transaction_detail_card`, `balance_card`, `category_chip_row` |
| uc2 Deposit | `product_card` / `product_card_carousel`, `amount_slider`, `tenure_picker`, `deposit_confirmation_card` |
| uc3 Knowledge | `answer_card`, `source_chip`, `related_questions` |
| uc4 Transfer | `payee_picker`, `amount_entry`, `rail_picker` (NEFT/IMPS), `transfer_confirmation_card`, `otp_input`, `transfer_success_card` |
| uc5 Complaint | `complaint_composer`, `suggested_fix_card`, `ticket_card`, `topic_chip` |
| Shared | `app_bar`, `message_bubble`, `quick_reply_chips`, `loading_shimmer`, `error_banner`, `voice_mic_button` |

### 6.3 Example A2UI payloads

**Amount summary card (uc1 — compact first, drill-down on tap):**
```json
{
  "surfaceId": "stmt_main",
  "components": [
    {"id":"card","type":"AmountSummaryCard","properties":{
      "title":"Spent last week","amount":"₹7,840","subtitle":"12 Jun–18 Jun · 9 transactions",
      "trend":"down","action":{"event":"show_txn_detail","label":"View transactions"}}}
  ]
}
```

**Rail picker (uc4 — the NEFT vs IMPS follow-up):**
```json
{
  "surfaceId":"transfer_rail",
  "components":[
    {"id":"q","type":"Text","properties":{"text":"Which transfer type?","style":"heading"}},
    {"id":"rail","type":"SegmentedControl","properties":{"options":[
       {"value":"NEFT","label":"NEFT","caption":"Batches · no limit"},
       {"value":"IMPS","label":"IMPS","caption":"Instant · 24×7"}],"bindTo":"slots.rail"}},
    {"id":"next","type":"Button","properties":{"text":"Continue","action":"submit"}}
  ]
}
```

**Transfer confirmation + OTP (uc4 — multi-factor):**
```json
{
  "surfaceId":"transfer_confirm",
  "components":[
    {"id":"review","type":"TransferConfirmationCard","properties":{
      "from":"Savings ••1234","to":"Rahul Mehta ••7890","amount":"₹5,000",
      "rail":"IMPS","reason":"Rent"}},
    {"id":"otp","type":"OtpInput","properties":{"length":6,"bindTo":"slots.otp"}},
    {"id":"auth","type":"Button","properties":{"text":"Authorise","action":"submit"}}
  ]
}
```

### 6.4 Flutter wiring (sketch)

```dart
// pubspec: genui, genui_a2ui
final connector = A2uiAgentConnector(serverUrl: 'wss://your-agent/ws');
final conversation = GenUiConversation(
  contentGenerator: A2uiContentGenerator(connector: connector),
);
// In build():
GenUiSurface(conversation: conversation, surfaceId: 'stmt_main');
```

---

## 7. Voice (optional phase)

Put ASR in front of the text pipeline; everything downstream is unchanged.

- **Model:** AI4Bharat **IndicConformer-600M** (22 Indian languages, MIT) or **IndicWhisper**. Indic-specific models hugely outperform vanilla Whisper on Hindi (≈16–18% vs ≈47% WER).
- **Flow:** mic → IndicConformer → text → LangGraph `classify`. For complaints (uc5), the same transcript feeds `extract_complaint_insights` so topics/sentiment are captured for the support team.
- **Fine-tune ASR only if** banking terms (NEFT, IMPS, "fixed deposit", account digits) are mis-transcribed — a light adapter pass, not full training.
- **Prompt-based ASR correction** (a CVS technique): have the 8B fix domain-term transcription errors using context, avoiding ASR retraining.

---

## 8. Synthetic dataset (the thing you actually train on)

No public dataset has Indian banking journeys in Hinglish with tool-call traces. You **generate** a few hundred to low-thousands of examples. Bootstrap the *style* of code-mixed task queries from **Hinglish-TOP** (hierarchical intent+slot) and **L3Cube-HingCorpus** for Hinglish fluency.

### 8.1 Example schema

```json
{
  "messages": [
    {"role": "system", "content": "You are a banking assistant. Classify intent and extract slots. Respond ONLY in JSON."},
    {"role": "user", "content": "mujhe ek FD kholni hai 50 hazaar ki ek saal ke liye"},
    {"role": "assistant", "content": "{\"intent\": \"open_fixed_deposit\", \"slots\": {\"amount\": 50000, \"tenure_months\": 12}}"}
  ]
}
```

### 8.2 Worked examples (one per pattern)

**Transactional (FD), Hinglish:**
```json
{"messages":[
 {"role":"user","content":"Standard FD me 1 lakh daalna hai 1 saal ke liye"},
 {"role":"assistant","content":"{\"intent\":\"open_fixed_deposit\",\"slots\":{\"product_id\":\"FDP002\",\"amount\":100000,\"tenure_months\":12}}"}
]}
```

**Spend-by-category query (uc1), Hinglish:**
```json
{"messages":[
 {"role":"user","content":"is mahine shopping pe kitna kharch kiya?"},
 {"role":"assistant","content":"{\"intent\":\"account_statement\",\"slots\":{\"period\":\"this_month\",\"category\":\"shopping\"}}"}
]}
```

**Spend-by-rail query (uc1), Hinglish:**
```json
{"messages":[
 {"role":"user","content":"pichhle mahine total UPI kitna hua?"},
 {"role":"assistant","content":"{\"intent\":\"account_statement\",\"slots\":{\"period\":\"last_month\",\"rail\":\"upi\"}}"}
]}
```

**Fund transfer (uc4), Hinglish:**
```json
{"messages":[
 {"role":"user","content":"Rahul ko 5000 bhejne hain IMPS se"},
 {"role":"assistant","content":"{\"intent\":\"fund_transfer\",\"slots\":{\"payee_name\":\"Rahul\",\"amount\":5000,\"rail\":\"imps\"}}"}
]}
```

**Tool-result formatting (teaches: format numbers, never invent):**
```json
{"messages":[
 {"role":"system","content":"Format the tool result for the user. Use ONLY numbers present in the data."},
 {"role":"user","content":"pichhle hafte kitna kharch hua?"},
 {"role":"tool","content":"{\"total_spent\": 7840, \"count\": 9}"},
 {"role":"assistant","content":"Pichhle hafte aapne ₹7,840 kharch kiye (9 transactions)."}
]}
```

**Complaint insight extraction (teaches: topics + sentiment):**
```json
{"messages":[
 {"role":"system","content":"Extract complaint topics and sentiment as JSON."},
 {"role":"user","content":"transfer fail ho gaya lekin paisa kat gaya, koi madad nahi mili"},
 {"role":"assistant","content":"{\"topics\":[\"failed_transfer\",\"debited_amount\",\"poor_support\"],\"sentiment\":\"frustrated\"}"}
]}
```

**Knowledge RAG routing (teaches: route to RAG, not tool/data):**
```json
{"messages":[
 {"role":"user","content":"FD ki minimum duration kya hai?"},
 {"role":"assistant","content":"{\"intent\":\"help_knowledge\",\"slots\":{}}"}
]}
```

### 8.3 Generation strategy

1. Hand-write ~15–20 seed examples per intent, mixing English / Hindi / Hinglish and varying slot phrasings.
2. Use a strong LLM to **augment** each seed into many paraphrases (CST5-style augmentation, as Hinglish-TOP does — up to 20× less labeled data needed).
3. Generate **negative/ambiguous** cases (e.g. "balance" that's actually "minimum balance *policy*" → RAG, not data) — these sharpen the uc1-vs-uc3 boundary.
4. Hold out ~15% for eval; track **intent accuracy**, **slot F1**, **JSON validity rate**, **tool-call correctness**.

### 8.4 Public datasets to seed/augment from

| Dataset | Use |
|---------|-----|
| **Hinglish-TOP** (google-research-datasets) | Structure & style of code-mixed task queries (hierarchical intent+slot) |
| **L3Cube-HingCorpus / HingBERT** (l3cube-pune) | Hinglish fluency; the optional fast intent classifier base |
| **Banking77 / Bitext retail banking** | English banking intent phrasings to translate/code-mix |
| **PHINC, HinGE** | Hinglish augmentation/paraphrase pairs |

---

## 9. MCP integration (if time permits)

MCP standardizes how the tool-calling agent reaches your backend. Instead of the direct `requests` calls in `tools.py`, wrap the backend as one or more **MCP servers** exposing the same operations (`book_deposit`, `get_statement`, `create_payment_consent`, `execute_payment`, `raise_complaint`, `search_help_docs`). LangGraph's tool nodes then call MCP tools rather than bespoke functions.

This changes **integration only** — not the model, not 8B-vs-70B, not the training. Cleanly deferrable to a final phase. Benefit: tools become reusable across agents/clients with a standard auth/permission surface — which dovetails with the Open-Banking consent model already in the backend.

---

## 10. Build order checklist

1. [ ] `schema.sql` + `seed.py` → `bank.db`; FastAPI `app.py` (Open-Banking endpoints) running.
2. [ ] `docs/` written; `rag_index.py` builds `docs.faiss`.
3. [ ] `tools.py` verified against the live backend.
4. [ ] `llm.py` provider switch works for **both** Gemini Flash 3.5 (local) and vLLM Llama-3.1-8B.
5. [ ] LangGraph graph runs with **un-fine-tuned** model (few-shot) — all 5 journeys end-to-end, including drill-down and OTP loops.
6. [ ] Seed + augment synthetic dataset; `train.jsonl` / `eval.jsonl`.
7. [ ] QLoRA fine-tune (`train_qlora.py`); evaluate intent acc / slot F1 / JSON validity.
8. [ ] Merge + serve quantized via vLLM; re-check JSON validity at 4-bit (fall back to 8-bit if needed).
9. [ ] Swap fine-tuned model into the `vllm` provider; drop few-shot bloat.
10. [ ] A2UI catalog + Flutter GenUI wiring for all 5 journeys (per the design system + handoff docs).
11. [ ] (Optional) HingBERT gatekeeper — only if per-turn latency/cost is a demonstrated problem.
12. [ ] (Optional) IndicConformer ASR in front for voice.
13. [ ] (Optional) Re-expose tools via MCP servers.

---

## 11. Why this is "fast and cheap" (the CVS thesis, your scale)

- **8B fine-tuned** replaces a 70B for bounded tasks — lower latency, lower cost per call.
- **Provider abstraction** lets you develop free/fast on Gemini Flash 3.5 and self-host on Llama-3.1-8B without touching orchestration code.
- **4-bit serving** multiplies throughput on a single GPU.
- **Optional HingBERT gatekeeper** keeps the LLM out of the easy ~80% of turns.
- **Tool-calls for numbers, RAG for knowledge** — the model grounds every factual answer instead of reasoning expensively from scratch.
- **One MI300X** comfortably serves the 8B + ASR + occasional LoRA fine-tune for a POC.

---

## 12. Design-team handoff index

| Document | Audience | Contents |
|----------|----------|----------|
| `banking_voice_agent_poc_plan.md` (this) | Eng + Design | Architecture, use-case journeys, API, intents, models |
| `design_system_component_catalog.md` | **Design** | Principles, full GenUI component catalog (props/states), per-journey screen flows, content/voice guidelines — the brief for visual design |
| `developer_handoff.md` | **Eng** | Design tokens (color/type/spacing/radius/elevation), responsive breakpoints/grid, component→A2UI mapping, interaction states, accessibility |
