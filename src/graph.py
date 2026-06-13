"""LangGraph orchestration for all 5 banking journeys.

Graph shape:
  classify → route → [data_query | deposit_journey | transfer_journey |
                       failure_flow | complaint_flow | knowledge_rag | fallback_handler]

Journeys are resumable: nodes can return done=False to wait for a user action
or slot value, then re-enter when the next message arrives with the state slot filled.

Build and run:
    from src.graph import build_graph, initial_state
    graph = build_graph()
    result = graph.invoke(initial_state("CUST001", "mera balance kya hai?"))
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from langgraph.graph import END, StateGraph

from src import a2ui
from src.intents import INTENT_REGISTRY, INTENTS
from src.llm import (
    extract_complaint_insights,
    format_numbers,
    llm_classify,
    suggest_self_fix,
    synthesize_rag_answer,
)
from src.state import AgentState
from src.tools import (
    TOOL_REGISTRY,
    book_deposit,
    confirm_deposit,
    create_payment_consent,
    execute_payment,
    explain_failure,
    get_balance,
    get_statement,
    list_deposit_products,
    list_payees,
    raise_complaint,
    search_help_docs,
)

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT = "ACC001"


# ── Intent guardrails ─────────────────────────────────────────────────────────
# Checked BEFORE any LLM call. Each tuple is (compiled_pattern, category_label).
# If the user message matches any pattern the request is rejected immediately —
# the LLM is never invoked and the in-progress journey state is preserved.

_BLOCKED: list[tuple[re.Pattern[str], str]] = [
    # Harmful / security violations — highest priority
    (re.compile(r'\b(hack|crack|exploit|phish|fraud|scam|bypass|cheat|illegal)\b', re.I),
     "harmful_request"),
    (re.compile(r'\b(share\s+otp|otp\s+bata|otp\s+do|give\s+otp|tell\s+otp)\b', re.I),
     "otp_sharing"),
    (re.compile(r'\b(account\s+(access|password|pin)\s+(do|de|dena|share|bata))\b', re.I),
     "credential_sharing"),
    # Weather
    (re.compile(r'\b(weather|mausam|barish|rain|sunny|forecast|temperature|garmi|sardi)\b', re.I),
     "weather"),
    # Medical advice
    (re.compile(r'\b(doctor|medicine|hospital|symptom|disease|prescription|diagnos|dawai|dawa)\b', re.I),
     "medical"),
    # Legal advice
    (re.compile(r'\b(lawyer|legal\s+advice|court|lawsuit|advocate|vakeel|kanoon\s+kya)\b', re.I),
     "legal"),
    # Political / religious content
    (re.compile(r'\b(election|vote|political\s+party|bjp|congress|aap\s+party|politician|neta)\b', re.I),
     "political"),
    # Romantic / personal relationship advice
    (re.compile(r'\b(girlfriend|boyfriend|love\s+advice|shaadi|breakup|divorce\s+kaise)\b', re.I),
     "personal_relationship"),
    # Pure entertainment (not finance-related)
    (re.compile(r'\b(movie\s+recommend|kal\s+ka\s+match|cricket\s+score|ipl\s+score|film\s+dekh)\b', re.I),
     "entertainment"),
]

_BLOCKED_RESPONSE = (
    "Main sirf banking services ke baare mein madad kar sakta hoon — "
    "balance, transactions, deposits, transfers aur complaints. "
    "Kripya banking se related sawaal poochhen."
)


def _check_guardrails(user_msg: str) -> str | None:
    """Return a rejection message if the query is blocked, else None.

    Patterns are checked against the lowercased message. The check is fast
    (pure regex, no LLM call) and fires even mid-journey so that a stray
    off-topic message does not disrupt the ongoing slot-fill state.
    """
    for pattern, category in _BLOCKED:
        if pattern.search(user_msg):
            logger.info("Guardrail blocked [%s]: %r", category, user_msg[:80])
            return _BLOCKED_RESPONSE
    return None


def initial_state(customer_id: str, user_msg: str, slots: dict | None = None,
                  pending_action: str | None = None) -> AgentState:
    return AgentState(
        customer_id=customer_id, user_msg=user_msg,
        intent=None, slots=slots or {}, pending_slot=None,
        pending_action=pending_action, tool_result=None,
        response_text=None, a2ui=None, done=False,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_range(period: str) -> tuple[str, str]:
    now = datetime.utcnow()
    ranges = {
        "today":      (now,                    now),
        "this_week":  (now - timedelta(days=7), now),
        "last_week":  (now - timedelta(days=14), now - timedelta(days=7)),
        "this_month": (now.replace(day=1),      now),
        "last_month": ((now.replace(day=1) - timedelta(days=1)).replace(day=1),
                       now.replace(day=1) - timedelta(days=1)),
    }
    s, e = ranges.get(period, (now - timedelta(days=30), now))
    return s.date().isoformat(), e.date().isoformat()


# ── Nodes ─────────────────────────────────────────────────────────────────────

def classify(state: AgentState) -> AgentState:
    """Classify intent — runs guardrails before invoking the LLM.

    If a guardrail pattern matches, the intent is set to "blocked" and
    done is set to False (preserving any in-progress journey state) so the
    client can re-send with the same accumulated slots on the next turn.
    """
    rejection = _check_guardrails(state["user_msg"])
    if rejection:
        return {**state,
                "intent": "blocked",
                "response_text": rejection,
                "a2ui": None,
                "done": False}   # keep journey alive; slots/pending_action unchanged

    result = llm_classify(state["user_msg"], INTENTS, history=state.get("slots"))
    # account_id is session-managed (DEFAULT_ACCOUNT); never accept it from the LLM
    clean_slots = {k: v for k, v in result.slots.items() if k != "account_id"}
    return {**state,
            "intent": result.intent,
            "slots":  {**state.get("slots", {}), **clean_slots}}


def blocked_response(state: AgentState) -> AgentState:
    """Passthrough for guardrail-blocked requests; response_text already set."""
    return state


def route(state: AgentState) -> str:
    if state["intent"] == "blocked":
        return "blocked_response"
    return INTENT_REGISTRY.get(state["intent"], INTENT_REGISTRY["fallback"])["handler"]


# ── uc1: balance / statement ──────────────────────────────────────────────────

def data_query(state: AgentState) -> AgentState:
    slots   = state.get("slots", {})
    acc     = slots.get("account_id", DEFAULT_ACCOUNT)

    # Drill-down: user tapped the summary card
    if state.get("pending_action") == "show_txn_detail":
        period = slots.get("period", "this_month")
        fd, td = _date_range(period)
        res = get_statement(acc, from_date=fd, to_date=td,
                            category=slots.get("category"),
                            rail=slots.get("rail"), detailed=True)
        data = res["Data"]
        return {**state,
                "tool_result":    res,
                "a2ui":           a2ui.transaction_list(data["transactions"]),
                "response_text":  "Here's the full transaction list.",
                "pending_action": None, "done": True}

    if state["intent"] == "balance_inquiry":
        res  = get_balance(acc)
        data = res["Data"]
        return {**state,
                "tool_result":   res,
                "a2ui":          a2ui.balance_card(data),
                "response_text": format_numbers(data, state["user_msg"]),
                "done": True}

    # Statement / spend query
    period = slots.get("period", "this_month")
    fd, td = _date_range(period)
    res  = get_statement(acc, from_date=fd, to_date=td,
                         category=slots.get("category"), rail=slots.get("rail"))
    data = res["Data"]
    return {**state,
            "tool_result":    res,
            "a2ui":           a2ui.amount_summary_card(data),
            "response_text":  format_numbers(data, state["user_msg"]),
            "done": True}


# ── uc2: FD/RD deposit journey ────────────────────────────────────────────────

def deposit_journey(state: AgentState) -> AgentState:
    slots = state.get("slots", {})
    kind  = "rd" if state["intent"] == "open_recurring_deposit" else "fd"

    if "product_id" not in slots:
        res      = list_deposit_products(kind)
        products = res["Data"]
        return {**state,
                "tool_result":  res,
                "a2ui":         a2ui.product_cards(products),
                "response_text": f"Here are the available {'RD' if kind=='rd' else 'FD'} products.",
                "pending_slot": "product_id", "done": False}

    # Find the selected product for constraint hints
    prod_res  = list_deposit_products(kind)
    prod_list = prod_res["Data"]
    product   = next((p for p in prod_list if p["product_id"] == slots["product_id"]), {})

    if "amount" not in slots:
        return {**state,
                "a2ui":         a2ui.deposit_amount_input(product),
                "response_text": f"How much would you like to deposit? (min ₹{product.get('min_amount',10000):,.0f})",
                "pending_slot": "amount", "done": False}

    if "tenure_months" not in slots:
        # For fixed-tenure products, auto-fill from the product
        if product.get("tenure_months"):
            slots = {**slots, "tenure_months": product["tenure_months"]}
        else:
            return {**state,
                    "slots":        slots,
                    "a2ui":         a2ui.deposit_amount_input(product),
                    "response_text": "Please choose a tenure.",
                    "pending_slot": "tenure_months", "done": False}

    res     = book_deposit(state["customer_id"], slots["product_id"],
                            float(slots["amount"]), int(slots["tenure_months"]))
    booking = res["Data"]
    return {**state,
            "slots":        {**slots, "booking_id": booking["booking_id"]},
            "tool_result":  res,
            "a2ui":         a2ui.deposit_confirmation_card(booking),
            "response_text": f"Booking created. Maturity value: ₹{booking['maturity_value']:,.2f}",
            "done": True}


# ── uc4: fund transfer ────────────────────────────────────────────────────────

def transfer_journey(state: AgentState) -> AgentState:
    slots = state.get("slots", {})

    if "payee_id" not in slots:
        res    = list_payees(state["customer_id"])
        payees = res["Data"]
        return {**state,
                "tool_result":  res,
                "a2ui":         a2ui.payee_picker(payees),
                "response_text": "Who would you like to pay?",
                "pending_slot": "payee_id", "done": False}

    if "amount" not in slots:
        return {**state,
                "response_text": "How much would you like to transfer?",
                "pending_slot": "amount", "done": False}

    if "rail" not in slots:
        return {**state,
                "a2ui":         a2ui.rail_picker(),
                "response_text": "NEFT (batched) or IMPS (instant 24×7)?",
                "pending_slot": "rail", "done": False}

    # OTP loop: consent already created, waiting for OTP
    if state.get("pending_action") == "await_otp":
        otp = slots.get("otp", "")
        try:
            res     = execute_payment(slots["consent_id"], otp)
            payment = res["Data"]
            return {**state,
                    "tool_result":    res,
                    "a2ui":           a2ui.transfer_success_card(payment),
                    "response_text":  f"₹{payment['amount']:,.0f} sent via {payment['rail'].upper()}.",
                    "pending_action": None, "done": True}
        except Exception as exc:
            # 401 invalid OTP — do NOT advance; re-render OTP error
            logger.warning(f"OTP failed: {exc}")
            return {**state,
                    "a2ui":         a2ui.otp_error_card(),
                    "response_text": "Invalid OTP. Please try again.",
                    "done": False}

    # Stage the consent, show confirmation + OTP input
    consent_res = create_payment_consent(
        state["customer_id"],
        slots.get("from_account", DEFAULT_ACCOUNT),
        slots["payee_id"], float(slots["amount"]),
        slots["rail"].lower(), slots.get("reason"),
    )
    consent = consent_res["Data"]
    return {**state,
            "slots":          {**slots, "consent_id": consent["consent_id"]},
            "tool_result":    consent_res,
            "a2ui":           a2ui.transfer_confirmation_card(consent),
            "response_text":  "Please review and enter the OTP to authorise.",
            "pending_action": "await_otp", "done": False}


# ── uc1b: transaction failure detail ─────────────────────────────────────────

def failure_flow(state: AgentState) -> AgentState:
    slots  = state.get("slots", {})
    txn_id = slots.get("txn_id")
    if not txn_id:
        return {**state,
                "response_text": "Which transaction failed? Please share the transaction ID.",
                "pending_slot": "txn_id", "done": False}
    res          = explain_failure(txn_id)
    data         = res["Data"]
    failure_info = {k: data[k] for k in ("reason","next_steps","complaint_eligible") if k in data}
    # Need the transaction row too — reuse txn from statement or mock
    txn = {"txn_id": txn_id, "status": data.get("status","failed"),
           "failure_code": data.get("failure_code",""), **slots}
    return {**state,
            "tool_result":   res,
            "a2ui":          a2ui.transaction_detail_card(txn, failure_info),
            "response_text": data.get("reason","Transaction failed."),
            "done": True}


# ── uc5: complaint ────────────────────────────────────────────────────────────

def complaint_flow(state: AgentState) -> AgentState:
    slots = state.get("slots", {})
    if "description" not in slots:
        return {**state,
                "response_text": "Please describe the issue so I can raise a complaint.",
                "pending_slot": "description", "done": False}

    insights   = extract_complaint_insights(slots["description"])
    suggestion = suggest_self_fix(insights.topics)
    if suggestion:
        return {**state,
                "a2ui":         a2ui.suggested_fix_card(suggestion),
                "response_text": suggestion["message"],
                "done": True}

    res    = raise_complaint(
        state["customer_id"], slots.get("category","transaction"),
        slots["description"], slots.get("txn_id"),
        topics=insights.topics, sentiment=insights.sentiment,
    )
    ticket = res["Data"]
    return {**state,
            "tool_result":   res,
            "a2ui":          a2ui.ticket_card(ticket),
            "response_text": f"Complaint raised. Ticket {ticket['ticket_id']}. SLA: {ticket['sla_hours']}h.",
            "done": True}


# ── uc3: knowledge RAG ────────────────────────────────────────────────────────

def knowledge_rag(state: AgentState) -> AgentState:
    chunks = search_help_docs(state["user_msg"])
    answer = synthesize_rag_answer(state["user_msg"], chunks)
    return {**state,
            "a2ui":          a2ui.answer_card(answer, chunks),
            "response_text": answer,
            "done": True}


# ── fallback ──────────────────────────────────────────────────────────────────

def fallback_handler(state: AgentState) -> AgentState:
    return {**state,
            "response_text": "Main samajh nahi paya. Kya aap thoda aur detail de sakte hain?",
            "done": True}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("classify",         classify)
    g.add_node("blocked_response", blocked_response)
    g.add_node("data_query",       data_query)
    g.add_node("deposit_journey",  deposit_journey)
    g.add_node("transfer_journey", transfer_journey)
    g.add_node("failure_flow",     failure_flow)
    g.add_node("complaint_flow",   complaint_flow)
    g.add_node("knowledge_rag",    knowledge_rag)
    g.add_node("fallback_handler", fallback_handler)

    g.set_entry_point("classify")
    g.add_conditional_edges("classify", route, {
        "blocked_response": "blocked_response",
        "data_query":        "data_query",
        "deposit_journey":   "deposit_journey",
        "transfer_journey":  "transfer_journey",
        "failure_flow":      "failure_flow",
        "complaint_flow":    "complaint_flow",
        "knowledge_rag":     "knowledge_rag",
        "fallback_handler":  "fallback_handler",
    })

    for node in ["blocked_response","data_query","deposit_journey","transfer_journey",
                 "failure_flow","complaint_flow","knowledge_rag","fallback_handler"]:
        g.add_edge(node, END)

    return g.compile()
