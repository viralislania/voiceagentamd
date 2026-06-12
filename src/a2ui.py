"""A2UI v0.9 payload builders.

Architecture (mirrors restaurant_finder sample):
  - updateComponents  = stable component *template* with {"path": "/field"} references.
    Never embeds live data values — the template only changes when layout changes.
  - updateDataModel   = carries all dynamic data (amounts, names, dates, arrays).
    Every builder ends with a single _udm(surface_id, "/", {...all data...}) call.
  - List component uses the template pattern
    {"componentId": "row-tpl", "path": "/items"} to iterate arrays without
    generating one component definition per data item.

Call to_parts() to wrap message dicts into A2A DataParts for the wire.
"""
from __future__ import annotations

from datetime import datetime

from a2a.types import Part
from a2ui.a2a.parts import A2UI_MIME_TYPE, create_a2ui_part  # noqa: F401
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.constants import VERSION_0_9

_catalog_schema = BasicCatalog.get_config(VERSION_0_9).provider.load()
CATALOG_ID: str = _catalog_schema["catalogId"]


def to_parts(msgs: list[dict]) -> list[Part]:
    """Wrap A2UI message dicts into a2a DataParts tagged application/json+a2ui."""
    return [create_a2ui_part(m) for m in msgs]


# ── Protocol primitives ───────────────────────────────────────────────────────

def _cs(surface_id: str, send_data_model: bool = True) -> dict:
    return {"version": "v0.9", "createSurface": {
        "surfaceId": surface_id, "catalogId": CATALOG_ID,
        "sendDataModel": send_data_model,
    }}


def _uc(surface_id: str, components: list[dict]) -> dict:
    return {"version": "v0.9", "updateComponents": {
        "surfaceId": surface_id, "components": components,
    }}


def _udm(surface_id: str, path: str, value) -> dict:
    return {"version": "v0.9", "updateDataModel": {
        "surfaceId": surface_id, "path": path, "value": value,
    }}


def _btn(id_: str, text: str, event_name: str,
         context: dict | None = None, variant: str | None = None) -> list[dict]:
    btn: dict = {
        "id": id_, "component": "Button",
        "child": f"{id_}_lbl",
        "action": {"event": {"name": event_name,
                              **({"context": context} if context else {})}},
    }
    if variant:
        btn["variant"] = variant
    return [btn, {"id": f"{id_}_lbl", "component": "Text", "text": text}]


# ── Formatting helpers (pure, no side-effects) ────────────────────────────────

def _fmt_inr(amount: float | int) -> str:
    return f"₹{amount:,.0f}"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso[:10]).strftime("%-d %b")
    except Exception:
        return iso[:10]


def _fmt_date_range(from_date: str | None, to_date: str | None) -> str:
    if not from_date:
        return ""
    fd = _fmt_date(from_date)
    td = _fmt_date(to_date) if to_date else "today"
    return f"{fd} – {td}"


def _txn_meta(t: dict) -> str:
    cat  = t.get("category", "")
    rail = t.get("rail", "").upper()
    date = _fmt_date(t.get("created_at"))
    return " · ".join(filter(None, [cat.capitalize() if cat else None, rail, date]))


# ── uc1: Balance ──────────────────────────────────────────────────────────────

# _BALANCE_COMPS is defined once — it's a stable template.
_BALANCE_COMPS = [
    {"id": "root",     "component": "Card",   "child": "col"},
    {"id": "col",      "component": "Column", "children": ["acc_row", "amt", "lbl_avail", "div", "row_act"]},
    {"id": "acc_row",  "component": "Row",    "children": ["acc_lbl"], "justify": "start"},
    {"id": "acc_lbl",  "component": "Text",   "text": {"path": "/account_label"}, "variant": "caption"},
    {"id": "amt",      "component": "Text",   "text": {"path": "/balance"},       "variant": "h1"},
    {"id": "lbl_avail","component": "Text",   "text": "Available balance",        "variant": "caption"},
    {"id": "div",      "component": "Divider"},
    {"id": "row_act",  "component": "Row",    "children": ["btn_stmt"],           "justify": "end"},
    *_btn("btn_stmt", "View Transactions", "show_statement"),
]


def balance_card(data: dict, surface_id: str = "balance") -> list[dict]:
    nickname = data.get("nickname") or data.get("account_type", "Savings").capitalize()
    masked   = data.get("masked_number") or f"••{data.get('account_id', '')[-4:]}"
    dm = {
        "account_label": f"{nickname} {masked}",
        "balance":       _fmt_inr(data.get("balance", 0)),
    }
    return [_cs(surface_id), _uc(surface_id, _BALANCE_COMPS), _udm(surface_id, "/", dm)]


# ── uc1: Statement summary ────────────────────────────────────────────────────

_STMT_SUMMARY_COMPS = [
    {"id": "root",     "component": "Card",   "child": "col"},
    {"id": "col",      "component": "Column", "children": ["lbl", "amt", "meta_row", "div", "row_act"]},
    {"id": "lbl",      "component": "Text",   "text": {"path": "/label"},    "variant": "h4"},
    {"id": "amt",      "component": "Text",   "text": {"path": "/spent"},    "variant": "h1"},
    {"id": "meta_row", "component": "Row",    "children": ["subtitle", "badge"], "justify": "spaceBetween"},
    {"id": "subtitle", "component": "Text",   "text": {"path": "/subtitle"}, "variant": "caption"},
    {"id": "badge",    "component": "Text",   "text": {"path": "/badge"},    "variant": "caption"},
    {"id": "div",      "component": "Divider"},
    {"id": "row_act",  "component": "Row",    "children": ["btn_detail"],    "justify": "end"},
    *_btn("btn_detail", "View transactions ›", "show_txn_detail", variant="borderless"),
]


def amount_summary_card(data: dict, surface_id: str = "stmt_summary") -> list[dict]:
    spent      = data.get("total_spent", 0)
    count      = data.get("count", 0)
    cat        = data.get("category") or data.get("rail")
    label      = f"{cat.capitalize()} spend" if cat else "Spent last week"
    date_range = _fmt_date_range(data.get("from_date"), data.get("to_date"))
    subtitle   = (f"{date_range} · {count} transaction{'s' if count != 1 else ''}"
                  if date_range else f"{count} transactions")
    pct = data.get("pct_change")
    badge = (f"{'↓' if pct <= 0 else '↑'}{abs(pct)}% vs prev") if pct is not None else ""
    dm = {"label": label, "spent": _fmt_inr(spent), "subtitle": subtitle, "badge": badge}
    return [_cs(surface_id), _uc(surface_id, _STMT_SUMMARY_COMPS), _udm(surface_id, "/", dm)]


# ── uc1: Transaction list (List template pattern) ─────────────────────────────

# Template: one component tree for all rows; data drives the list via /items.
_TXN_LIST_COMPS = [
    {"id": "root",     "component": "List", "direction": "vertical",
     "children": {"componentId": "txn-row-tpl", "path": "/items"}},
    # --- row template ---
    {"id": "txn-row-tpl", "component": "Button", "child": "inner-tpl",
     "variant": "borderless",
     "action": {"event": {"name": "show_txn", "context": {"txn_id": {"path": "txn_id"}}}}},
    {"id": "inner-tpl",   "component": "Row",
     "children": ["info-tpl", "amt-tpl"], "justify": "spaceBetween"},
    {"id": "info-tpl",    "component": "Column",
     "children": ["name-tpl", "meta-tpl"]},
    {"id": "name-tpl",    "component": "Text",   "text": {"path": "counterparty"}},
    {"id": "meta-tpl",    "component": "Text",   "text": {"path": "meta"},    "variant": "caption"},
    {"id": "amt-tpl",     "component": "Text",   "text": {"path": "amount_display"}},
]


def transaction_list(transactions: list[dict], surface_id: str = "txn_list") -> list[dict]:
    items = []
    for t in transactions:
        sign   = "−" if t["direction"] == "debit" else "+"
        failed = t.get("status") == "failed"
        items.append({
            "txn_id":         t["txn_id"],
            "counterparty":   t.get("counterparty", ""),
            "meta":           _txn_meta(t),
            "amount_display": "Failed" if failed else f"{sign}{_fmt_inr(t['amount'])}",
        })
    return [_cs(surface_id), _uc(surface_id, _TXN_LIST_COMPS), _udm(surface_id, "/items", items)]


# ── uc1: Transaction detail ───────────────────────────────────────────────────

_TXN_DETAIL_ROWS = ["Amount", "Status", "Rail", "Counterparty", "Date", "Reference"]

_TXN_DETAIL_COMPS = [
    {"id": "root", "component": "Card",   "child": "col"},
    {"id": "col",  "component": "Column",
     "children": ["hdg"] + [f"r_{k.lower()}" for k in _TXN_DETAIL_ROWS] + ["fail_reason"]},
    {"id": "hdg",  "component": "Text",   "text": {"path": "/heading"}, "variant": "h3"},
    *[comp
      for k in _TXN_DETAIL_ROWS
      for comp in [
          {"id": f"r_{k.lower()}",   "component": "Row",  "justify": "spaceBetween",
           "children": [f"lbl_{k.lower()}", f"val_{k.lower()}"]},
          {"id": f"lbl_{k.lower()}", "component": "Text", "text": k, "variant": "caption"},
          {"id": f"val_{k.lower()}", "component": "Text", "text": {"path": f"/{k.lower()}"}},
      ]],
    {"id": "fail_reason", "component": "Text", "text": {"path": "/fail_reason"}, "variant": "caption"},
]


def transaction_detail_card(txn: dict, failure_info: dict | None = None,
                             surface_id: str = "txn_detail") -> list[dict]:
    sign = "−" if txn.get("direction") == "debit" else "+"
    dm = {
        "heading":    txn.get("counterparty", "Transaction"),
        "amount":     f"{sign}{_fmt_inr(txn.get('amount', 0))}",
        "status":     txn.get("status", "").upper(),
        "rail":       txn.get("rail", "").upper(),
        "counterparty": txn.get("counterparty", ""),
        "date":       _fmt_date(txn.get("created_at")),
        "reference":  txn.get("reference_no", ""),
        "fail_reason": f"Reason: {failure_info['reason']}" if failure_info else "",
    }
    comps = list(_TXN_DETAIL_COMPS)
    if failure_info and failure_info.get("complaint_eligible"):
        comps[1]["children"].append("btn_complaint")  # type: ignore[index]
        comps += _btn("btn_complaint", "Raise Complaint", "raise_complaint",
                      context={"txn_id": txn["txn_id"]})
    return [_cs(surface_id), _uc(surface_id, comps), _udm(surface_id, "/", dm)]


# ── uc2: Deposits — product list (List template) ──────────────────────────────

_PRODUCT_LIST_COMPS = [
    {"id": "root",          "component": "Column", "children": ["hdg", "list"]},
    {"id": "hdg",           "component": "Text",   "text": {"path": "/heading"}, "variant": "h3"},
    {"id": "list",          "component": "List",   "direction": "vertical",
     "children": {"componentId": "prod-card-tpl",  "path": "/items"}},
    # --- product template ---
    {"id": "prod-card-tpl", "component": "Button", "child": "prod-card-inner",
     "action": {"event": {"name": "select_product",
                           "context": {"product_id": {"path": "product_id"}}}}},
    {"id": "prod-card-inner","component": "Card",  "child": "prod-row"},
    {"id": "prod-row",       "component": "Row",   "children": ["prod-left", "prod-rate"], "justify": "spaceBetween"},
    {"id": "prod-left",      "component": "Column","children": ["prod-name", "prod-sub"]},
    {"id": "prod-name",      "component": "Text",  "text": {"path": "name"},     "variant": "h4"},
    {"id": "prod-sub",       "component": "Text",  "text": {"path": "subtitle"}, "variant": "caption"},
    {"id": "prod-rate",      "component": "Text",  "text": {"path": "rate"},     "variant": "h3"},
]


def product_cards(products: list[dict], surface_id: str = "deposit_products") -> list[dict]:
    items = []
    for p in products:
        min_k = p["min_amount"] / 1000
        max_k = p["max_amount"] / 1000
        range_ = (f"₹{min_k:.0f}k–₹{max_k:.0f}k" if max_k < 10000
                  else f"₹{min_k:.0f}k–₹{p['max_amount'] / 100000:.0f}L")
        items.append({
            "product_id": p["product_id"],
            "name":       p["name"],
            "subtitle":   f"{p['tenure_months']} months · {range_}",
            "rate":       f"{p['interest_rate']}% p.a.",
        })
    dm = {"heading": "Choose a product", "items": items}
    return [_cs(surface_id), _uc(surface_id, _PRODUCT_LIST_COMPS), _udm(surface_id, "/", dm)]


def deposit_amount_input(product: dict, surface_id: str = "dep_amount") -> list[dict]:
    min_a = int(product.get("min_amount", 10000))
    max_a = int(product.get("max_amount", 1000000))
    comps = [
        {"id": "root",   "component": "Column", "children": ["lbl", "slider", "btn_amt"], "align": "stretch"},
        {"id": "lbl",    "component": "Text",   "text": {"path": "/amount_label"}, "variant": "h4"},
        {"id": "slider", "component": "Slider", "label": "Deposit Amount",
         "min": min_a, "max": max_a, "value": {"path": "/deposit/amount"}},
        *_btn("btn_amt", "Continue", "submit_amount",
              context={"amount": {"path": "/deposit/amount"}}),
    ]
    dm = {
        "amount_label":   f"Select amount (₹{min_a:,} – ₹{max_a:,})",
        "deposit":        {"amount": min_a},
    }
    return [_cs(surface_id), _uc(surface_id, comps), _udm(surface_id, "/", dm)]


_DEPOSIT_CONFIRM_ROWS = ["Amount", "Tenure", "Rate", "Maturity value"]

_DEPOSIT_CONFIRM_COMPS = [
    {"id": "root",      "component": "Card",   "child": "col"},
    {"id": "col",       "component": "Column",
     "children": ["hdg", "prod_name"] + [f"r_{k.lower().replace(' ', '_')}" for k in _DEPOSIT_CONFIRM_ROWS] + ["div", "btn_confirm"]},
    {"id": "hdg",       "component": "Text",   "text": "Confirm your deposit", "variant": "h3"},
    {"id": "prod_name", "component": "Text",   "text": {"path": "/product_name"}, "variant": "h4"},
    *[comp
      for k in _DEPOSIT_CONFIRM_ROWS
      for comp in [
          {"id": f"r_{k.lower().replace(' ', '_')}",   "component": "Row",  "justify": "spaceBetween",
           "children": [f"lbl_{k.lower().replace(' ', '_')}", f"val_{k.lower().replace(' ', '_')}"]},
          {"id": f"lbl_{k.lower().replace(' ', '_')}", "component": "Text", "text": k, "variant": "caption"},
          {"id": f"val_{k.lower().replace(' ', '_')}", "component": "Text", "text": {"path": f"/{k.lower().replace(' ', '_')}"}},
      ]],
    {"id": "div",       "component": "Divider"},
    *_btn("btn_confirm", "Confirm & open deposit", "confirm_deposit",
          context={"booking_id": {"path": "/booking_id"}}, variant="primary"),
]


def deposit_confirmation_card(booking: dict, surface_id: str = "dep_confirm") -> list[dict]:
    dm = {
        "product_name":  booking.get("product", ""),
        "booking_id":    booking.get("booking_id", ""),
        "amount":        _fmt_inr(booking["amount"]),
        "tenure":        f"{booking['tenure_months']} months",
        "rate":          f"{booking.get('interest_rate', 0)}% p.a.",
        "maturity_value": _fmt_inr(booking.get("maturity_value", 0)),
    }
    return [_cs(surface_id), _uc(surface_id, _DEPOSIT_CONFIRM_COMPS), _udm(surface_id, "/", dm)]


# ── uc3: Knowledge RAG ────────────────────────────────────────────────────────

_ANSWER_COMPS = [
    {"id": "root",     "component": "Card",   "child": "col"},
    {"id": "col",      "component": "Column", "children": ["body", "src_lbl", "src_list", "rel_lbl", "rel_list"]},
    {"id": "body",     "component": "Text",   "text": {"path": "/answer"}},
    {"id": "src_lbl",  "component": "Text",   "text": "Sources", "variant": "caption"},
    {"id": "src_list", "component": "List",   "direction": "horizontal",
     "children": {"componentId": "src-chip-tpl", "path": "/sources"}},
    {"id": "src-chip-tpl", "component": "Text", "text": {"path": "label"}, "variant": "caption"},
    {"id": "rel_lbl",  "component": "Text",   "text": "Related", "variant": "caption"},
    {"id": "rel_list", "component": "List",   "direction": "vertical",
     "children": {"componentId": "rel-btn-tpl", "path": "/related"}},
    {"id": "rel-btn-tpl", "component": "Button", "child": "rel-lbl-tpl",
     "variant": "borderless",
     "action": {"event": {"name": "ask_related", "context": {"question": {"path": "question"}}}}},
    {"id": "rel-lbl-tpl", "component": "Text", "text": {"path": "question"}},
]

_RELATED_MAP: dict[str, list[str]] = {
    "how_to_open_fd":              ["How is FD interest taxed?", "Penalty for breaking an FD?"],
    "how_to_open_rd":              ["What if I miss an RD instalment?"],
    "safe_upi_practices":          ["Daily UPI limit?", "How to block a UPI PIN?"],
    "fund_transfer_neft_vs_imps":  ["NEFT vs IMPS charges?", "RTGS kab use karein?"],
    "kyc_requirements":            ["How long does KYC take?", "Can I do video KYC?"],
    "fees_and_charges":            ["ATM withdrawal charges?", "Cheque bounce fee?"],
}


def _derive_related(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for c in chunks[:2]:
        key = c.get("source", "").replace("src/backend/docs/", "").replace(".md", "")
        for q in _RELATED_MAP.get(key, []):
            if q not in seen and len(result) < 3:
                seen.add(q)
                result.append({"question": q})
    return result


def answer_card(answer: str, chunks: list[dict], surface_id: str = "rag_answer") -> list[dict]:
    sources = [
        {"label": f"⊙ {c['source'].replace('src/backend/docs/', '').replace('.md', '')}"}
        for c in chunks
    ]
    dm = {"answer": answer, "sources": sources, "related": _derive_related(chunks)}
    return [_cs(surface_id), _uc(surface_id, _ANSWER_COMPS), _udm(surface_id, "/", dm)]


# ── uc4: Fund Transfer — payee list (List template) ──────────────────────────

_PAYEE_LIST_COMPS = [
    {"id": "root",         "component": "Column", "children": ["hdg", "list"]},
    {"id": "hdg",          "component": "Text",   "text": "Who would you like to pay?", "variant": "h3"},
    {"id": "list",         "component": "List",   "direction": "vertical",
     "children": {"componentId": "payee-row-tpl", "path": "/items"}},
    # --- payee template ---
    {"id": "payee-row-tpl","component": "Button", "child": "payee-inner",
     "variant": "borderless",
     "action": {"event": {"name": "select_payee", "context": {"payee_id": {"path": "payee_id"}}}}},
    {"id": "payee-inner",  "component": "Row",    "children": ["payee-ico", "payee-info"]},
    {"id": "payee-ico",    "component": "Icon",   "name": "person"},
    {"id": "payee-info",   "component": "Column", "children": ["payee-name", "payee-acct"]},
    {"id": "payee-name",   "component": "Text",   "text": {"path": "name"}},
    {"id": "payee-acct",   "component": "Text",   "text": {"path": "acct_label"}, "variant": "caption"},
]


def payee_picker(payees: list[dict], surface_id: str = "payee_picker") -> list[dict]:
    items = [
        {
            "payee_id":   p["payee_id"],
            "name":       p["name"],
            "acct_label": f"••{p.get('account_number', '')[-4:]} · {p.get('ifsc', '')[:8]}",
        }
        for p in payees
    ]
    return [_cs(surface_id), _uc(surface_id, _PAYEE_LIST_COMPS), _udm(surface_id, "/items", items)]


def rail_picker(surface_id: str = "rail_picker") -> list[dict]:
    comps = [
        {"id": "root",   "component": "Column",
         "children": ["hdg", "picker", "btn_rail"]},
        {"id": "hdg",    "component": "Text",
         "text": "Which transfer type — NEFT or IMPS?", "variant": "h4"},
        {"id": "picker", "component": "ChoicePicker", "variant": "mutuallyExclusive",
         "options": [
             {"label": "NEFT", "sublabel": "Batched · no limit", "value": "neft"},
             {"label": "IMPS", "sublabel": "Instant · 24×7",     "value": "imps"},
         ],
         "value": {"path": "/transfer/rail"}},
        *_btn("btn_rail", "Continue", "submit_rail",
              context={"rail": {"path": "/transfer/rail"}}, variant="primary"),
    ]
    return [_cs(surface_id), _uc(surface_id, comps), _udm(surface_id, "/transfer/rail", "imps")]


_XFER_DETAIL_ROWS = ["From", "To", "Amount", "Type", "Reason"]

_XFER_CONFIRM_COMPS = [
    {"id": "root", "component": "Card",   "child": "col"},
    {"id": "col",  "component": "Column",
     "children": ["hdg"] + [f"r_{k.lower()}" for k in _XFER_DETAIL_ROWS]
               + ["div", "otp_lbl", "otp_field", "btn_auth"]},
    {"id": "hdg",  "component": "Text",   "text": "Review transfer", "variant": "h3"},
    *[comp
      for k in _XFER_DETAIL_ROWS
      for comp in [
          {"id": f"r_{k.lower()}",   "component": "Row",  "justify": "spaceBetween",
           "children": [f"lbl_{k.lower()}", f"val_{k.lower()}"]},
          {"id": f"lbl_{k.lower()}", "component": "Text", "text": k, "variant": "caption"},
          {"id": f"val_{k.lower()}", "component": "Text", "text": {"path": f"/{k.lower()}"}},
      ]],
    {"id": "div",      "component": "Divider"},
    {"id": "otp_lbl",  "component": "Text",
     "text": "Enter the 6-digit OTP to authorise", "variant": "caption"},
    {"id": "otp_field","component": "TextField", "label": "OTP",
     "variant": "number", "value": {"path": "/transfer/otp"},
     "checks": [{"call": "length",
                 "args": {"value": {"path": "/transfer/otp"}, "min": 6, "max": 6},
                 "message": "OTP must be exactly 6 digits"}]},
    *_btn("btn_auth", "Authorise", "submit_otp",
          context={"consent_id": {"path": "/consent_id"},
                   "otp":        {"path": "/transfer/otp"}}, variant="primary"),
]


def transfer_confirmation_card(consent: dict, surface_id: str = "xfer_confirm") -> list[dict]:
    payee    = consent.get("payee", {})
    from_acc = consent.get("from_account", "")
    dm = {
        "consent_id": consent["consent_id"],
        "from":       f"Savings ••{from_acc[-4:]}" if from_acc else "Savings",
        "to":         f"{payee.get('name', '')} ••{payee.get('account_number', '')[-4:]}",
        "amount":     _fmt_inr(consent["amount"]),
        "type":       consent.get("rail", "").upper(),
        "reason":     consent.get("reason") or "—",
        "transfer":   {"otp": ""},
    }
    return [_cs(surface_id), _uc(surface_id, _XFER_CONFIRM_COMPS), _udm(surface_id, "/", dm)]


_XFER_SUCCESS_COMPS = [
    {"id": "root",   "component": "Card",   "child": "col"},
    {"id": "col",    "component": "Column", "children": ["ico", "hdg", "amount", "ref"], "align": "center"},
    {"id": "ico",    "component": "Icon",   "name": "check"},
    {"id": "hdg",    "component": "Text",   "text": "Transfer Successful", "variant": "h3"},
    {"id": "amount", "component": "Text",   "text": {"path": "/amount_label"}, "variant": "h2"},
    {"id": "ref",    "component": "Text",   "text": {"path": "/ref_label"},    "variant": "caption"},
]


def transfer_success_card(payment: dict, surface_id: str = "xfer_success") -> list[dict]:
    dm = {
        "amount_label": f"{_fmt_inr(payment['amount'])} via {payment.get('rail', '').upper()}",
        "ref_label":    f"Ref: {payment.get('payment_id', '')}",
    }
    return [_cs(surface_id), _uc(surface_id, _XFER_SUCCESS_COMPS), _udm(surface_id, "/", dm)]


def otp_error_card(surface_id: str = "xfer_confirm") -> list[dict]:
    """Additive patch — appends an error message without rebuilding the surface."""
    return [_uc(surface_id, [
        {"id": "otp_err", "component": "Text",
         "text": "Invalid OTP — please try again.", "variant": "caption"},
    ])]


# ── uc5: Complaints ───────────────────────────────────────────────────────────

_FIX_CARD_COMPS = [
    {"id": "root", "component": "Card",   "child": "col"},
    {"id": "col",  "component": "Column", "children": ["hdg", "msg", "btn_fix"]},
    {"id": "hdg",  "component": "Text",   "text": "Suggested Fix",  "variant": "h4"},
    {"id": "msg",  "component": "Text",   "text": {"path": "/message"}},
    *_btn("btn_fix", "Take action", "action_tap"),
]


def suggested_fix_card(suggestion: dict, surface_id: str = "fix_card") -> list[dict]:
    dm = {"message": suggestion["message"]}
    return [_cs(surface_id), _uc(surface_id, _FIX_CARD_COMPS), _udm(surface_id, "/", dm)]


_TICKET_COMPS = [
    {"id": "root",      "component": "Card",   "child": "col"},
    {"id": "col",       "component": "Column",
     "children": ["hdg", "badge_row", "row_id", "row_txn", "tags_row"]},
    {"id": "hdg",       "component": "Text",   "text": "Ticket raised",      "variant": "h4"},
    {"id": "badge_row", "component": "Row",    "children": ["badge_txt"],    "justify": "end"},
    {"id": "badge_txt", "component": "Text",   "text": {"path": "/badge"},   "variant": "caption"},
    {"id": "row_id",    "component": "Row",    "justify": "spaceBetween",
     "children": ["lbl_id", "val_id"]},
    {"id": "lbl_id",    "component": "Text",   "text": "Ticket ID",          "variant": "caption"},
    {"id": "val_id",    "component": "Text",   "text": {"path": "/ticket_id"}},
    {"id": "row_txn",   "component": "Row",    "justify": "spaceBetween",
     "children": ["lbl_txn", "val_txn"]},
    {"id": "lbl_txn",   "component": "Text",   "text": "Linked txn",         "variant": "caption"},
    {"id": "val_txn",   "component": "Text",   "text": {"path": "/txn_id"}},
    {"id": "tags_row",  "component": "List",   "direction": "horizontal",
     "children": {"componentId": "tag-tpl", "path": "/tags"}},
    {"id": "tag-tpl",   "component": "Text",   "text": {"path": "label"},    "variant": "caption"},
]


def ticket_card(ticket: dict, surface_id: str = "ticket") -> list[dict]:
    sla    = ticket.get("sla_hours", 48)
    status = ticket.get("status", "open").capitalize()
    dm = {
        "badge":     f"{status} · SLA {sla}h",
        "ticket_id": ticket["ticket_id"],
        "txn_id":    ticket.get("txn_id") or "—",
        "tags":      [{"label": t.replace("_", " ")} for t in ticket.get("topics", [])],
    }
    return [_cs(surface_id), _uc(surface_id, _TICKET_COMPS), _udm(surface_id, "/", dm)]


# ── Error / fallback ──────────────────────────────────────────────────────────

_ERROR_COMPS = [
    {"id": "root", "component": "Card",   "child": "col"},
    {"id": "col",  "component": "Column", "children": ["ico", "msg"]},
    {"id": "ico",  "component": "Icon",   "name": "error"},
    {"id": "msg",  "component": "Text",   "text": {"path": "/message"}},
]


def error_card(message: str, surface_id: str = "error") -> list[dict]:
    return [_cs(surface_id), _uc(surface_id, _ERROR_COMPS), _udm(surface_id, "/message", message)]
