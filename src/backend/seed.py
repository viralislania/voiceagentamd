"""Seed bank.db with demo data.
Run: python -m src.backend.seed
     or: python -m src.backend.seed  (from project root)

Reset: rm src/backend/bank.db && python -m src.backend.seed
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

DB  = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "bank.db"))
now = datetime.utcnow()

con = sqlite3.connect(DB)
con.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())

# ── Customers ─────────────────────────────────────────────────────────────────
con.execute("INSERT OR REPLACE INTO customers VALUES (?,?,?,?)",
            ("CUST001", "Asha Verma", "+91900000001", 1))

# ── Accounts  (nickname + 12-digit account_number) ───────────────────────────
# account_number ends in "1234" / "5678" to match the Figma "••1234" mask
con.execute("INSERT OR REPLACE INTO accounts VALUES (?,?,?,?,?,?,?,?)",
            ("ACC001", "CUST001", "savings", "Savings", "123456781234", 84250.0, "INR", "2021-03-10"))
con.execute("INSERT OR REPLACE INTO accounts VALUES (?,?,?,?,?,?,?,?)",
            ("ACC002", "CUST001", "current", "Current", "987654325678", 12000.0, "INR", "2022-06-15"))

# ── Transactions (last ~14 days to exercise statement comparisons) ────────────
txns = [
    # This week (last 7 days)
    ("TXN001", "ACC001", 1200,  "debit",  "upi",  "food",     "success", None,                    "Zomato",       "TXN001", (now - timedelta(days=1)).isoformat()),
    ("TXN002", "ACC001", 5000,  "debit",  "imps", "transfer", "failed",  "BENEFICIARY_BANK_DOWN", "R. Sharma",    "TXN002", (now - timedelta(days=1)).isoformat()),
    ("TXN003", "ACC001", 45000, "credit", "neft", "salary",   "success", None,                    "ACME Corp",    "TXN003", (now - timedelta(days=5)).isoformat()),
    ("TXN004", "ACC001", 800,   "debit",  "upi",  "bills",    "success", None,                    "Electricity",  "TXN004", (now - timedelta(days=3)).isoformat()),
    ("TXN005", "ACC001", 3499,  "debit",  "card", "shopping", "success", None,                    "Myntra",       "TXN005", (now - timedelta(days=4)).isoformat()),
    ("TXN006", "ACC001", 2150,  "debit",  "upi",  "shopping", "success", None,                    "Amazon",       "TXN006", (now - timedelta(days=2)).isoformat()),
    ("TXN007", "ACC001", 650,   "debit",  "upi",  "food",     "success", None,                    "Swiggy",       "TXN007", (now - timedelta(days=6)).isoformat()),
    # Previous week (-14 to -7 days)
    ("TXN008", "ACC001", 1500,  "debit",  "neft", "transfer", "success", None,                    "Priya Singh",  "TXN008", (now - timedelta(days=9)).isoformat()),
    ("TXN009", "ACC001", 999,   "debit",  "card", "shopping", "success", None,                    "Flipkart",     "TXN009", (now - timedelta(days=10)).isoformat()),
    ("TXN010", "ACC001", 200,   "debit",  "upi",  "food",     "success", None,                    "Chai Point",   "TXN010", (now - timedelta(days=12)).isoformat()),
    ("TXN011", "ACC001", 3200,  "debit",  "upi",  "shopping", "success", None,                    "Meesho",       "TXN011", (now - timedelta(days=8)).isoformat()),
    ("TXN012", "ACC001", 600,   "debit",  "upi",  "food",     "success", None,                    "Blinkit",      "TXN012", (now - timedelta(days=11)).isoformat()),
]
con.executemany("INSERT OR REPLACE INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)", txns)

# ── Deposit products ──────────────────────────────────────────────────────────
deps = [
    ("FDP001", "fd", "Short-Term FD", 10000, 1000000, 6,  6.5),
    ("FDP002", "fd", "Standard FD",   10000, 1000000, 12, 7.1),
    ("FDP003", "fd", "Long-Term FD",  25000, 5000000, 36, 7.4),
    ("RDP001", "rd", "Recurring 12m", 500,   100000,  12, 6.8),
    ("RDP002", "rd", "Recurring 24m", 500,   100000,  24, 7.0),
]
con.executemany("INSERT OR REPLACE INTO deposit_products VALUES (?,?,?,?,?,?,?)", deps)

# ── Payees ────────────────────────────────────────────────────────────────────
con.execute("INSERT OR REPLACE INTO payees VALUES (?,?,?,?,?)",
            ("PYE001", "CUST001", "Rahul Mehta",  "1234567890", "HDFC0001234"))
con.execute("INSERT OR REPLACE INTO payees VALUES (?,?,?,?,?)",
            ("PYE002", "CUST001", "Priya Singh",  "9876543210", "ICIC0009876"))
con.execute("INSERT OR REPLACE INTO payees VALUES (?,?,?,?,?)",
            ("PYE003", "CUST001", "Rent Account", "1122334455", "SBIN0001122"))

# ── Seeded complaint (matches "recent conversations" in Home screen) ──────────
con.execute(
    "INSERT OR REPLACE INTO complaints VALUES (?,?,?,?,?,?,?,?,?)",
    ("CMP3F9A21", "CUST001", "TXN002", "transaction",
     "IMPS transfer failed but amount was debited",
     json.dumps(["failed_transfer", "debited_amount", "poor_support"]),
     "frustrated", "open",
     (now - timedelta(days=2)).isoformat()),
)

con.commit(); con.close()
print(f"Seeded {DB}")
print("  CUST001 Asha Verma")
print("  ACC001  Savings ••1234  ₹84,250")
print("  ACC002  Current ••5678  ₹12,000")
print("  12 transactions · 5 payees · 5 deposit products · 1 complaint")
