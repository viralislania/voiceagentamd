"""LLM provider abstraction — Gemini Flash (default) or vLLM Llama-3.1-8B.

Switch via LLM_PROVIDER env var (or .env).  Both providers expose the same
`chat()` call; all orchestration code is provider-agnostic.
"""
from __future__ import annotations

import json
import logging

from src.config import settings
from src.models import ClassifyResponse, InsightResponse

logger = logging.getLogger(__name__)

# ── Core chat ─────────────────────────────────────────────────────────────────

def chat(
    messages: list[dict],
    json_mode: bool = False,
    temperature: float = 0.0,
) -> str:
    if settings.llm_provider == "vllm":
        return _vllm(messages, json_mode, temperature)
    return _gemini(messages, json_mode, temperature)


def _gemini(messages: list[dict], json_mode: bool, temperature: float) -> str:
    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
    if not settings.gemini_api_key:
        raise EnvironmentError("GEMINI_API_KEY not set in .env")
    client = genai.Client(api_key=settings.gemini_api_key)

    # Flatten messages into a single prompt (google-genai uses contents, not chat history for simple calls)
    parts: list[str] = []
    for m in messages:
        role    = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.insert(0, f"[System]: {content}")
        elif role == "tool":
            parts.append(f"[Tool result]: {content}")
        else:
            parts.append(content)

    cfg = genai_types.GenerateContentConfig(temperature=temperature)
    if json_mode:
        cfg.response_mime_type = "application/json"

    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents="\n".join(parts),
        config=cfg,
    )
    return resp.text


def _vllm(messages: list[dict], json_mode: bool, temperature: float) -> str:
    import requests as _req
    body: dict = {
        "model": settings.vllm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _req.post(f"{settings.vllm_url}/chat/completions", json=body, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ── Structured helpers ────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """\
You are a banking assistant intent classifier for Indian customers (English / Hindi / Hinglish).

Given the user message, return ONLY valid JSON:
  "intent": one of {intents}
  "slots": dict with any of: account_id, amount, category, rail, payee_name,
           payee_id, period, tenure_months, txn_id, description, from_date, to_date

Intent rules:
- balance_inquiry        → wants current account balance
- account_statement      → wants spend/transaction history (may include category/rail/date filter)
- fund_transfer          → wants to send money
- open_fixed_deposit     → wants to open an FD
- open_recurring_deposit → wants to open an RD
- open_savings           → wants to open a savings account
- transaction_failure    → reporting or asking why a transaction failed
- raise_complaint        → wants to file a complaint
- help_knowledge         → policy / FAQ / how-to question (NOT for real balance numbers)
- fallback               → unclear, greeting, or out-of-scope

Period values: today | this_week | last_week | this_month | last_month | ISO date range
Rail values: upi | neft | imps | card
Category values: food | shopping | bills | salary | transfer
"""

_INSIGHT_SYSTEM = """\
Extract complaint topics and sentiment from the user message.
Return ONLY valid JSON: {"topics": [...], "sentiment": "angry"|"frustrated"|"neutral"}
Topic values: failed_transfer | debited_amount | poor_support | delayed_refund |
              wrong_amount | unauthorized_txn | app_error | upi_pin_blocked |
              insufficient_funds | daily_limit_exceeded
"""

_FORMAT_SYSTEM = """\
You are a friendly banking assistant. Format the tool result as a brief, clear response
in the same language as the user (English / Hindi / Hinglish).
Use ONLY numbers present in the Data field — do not invent or estimate figures.
"""

_RAG_SYSTEM = """\
Answer the user's question using ONLY the provided document excerpts.
Cite the source file name. If the answer is not in the excerpts, say so concisely.
"""


def llm_classify(user_msg: str, intents: list[str], history: dict | None = None) -> ClassifyResponse:
    system = _CLASSIFY_SYSTEM.format(intents=", ".join(intents))
    messages = [{"role": "system", "content": system}]
    if history:
        messages.append({"role": "user", "content": f"[Prior slots: {history}]"})
    messages.append({"role": "user", "content": user_msg})
    raw = chat(messages, json_mode=True)
    try:
        return ClassifyResponse(**json.loads(raw))
    except Exception:
        logger.warning(f"Classify parse failed: {raw[:200]}")
        return ClassifyResponse(intent="fallback", slots={})


def extract_complaint_insights(description: str) -> InsightResponse:
    raw = chat([
        {"role": "system", "content": _INSIGHT_SYSTEM},
        {"role": "user", "content": description},
    ], json_mode=True)
    try:
        return InsightResponse(**json.loads(raw))
    except Exception:
        return InsightResponse()


def format_numbers(data: dict, user_msg: str) -> str:
    return chat([
        {"role": "system", "content": _FORMAT_SYSTEM},
        {"role": "user",   "content": user_msg},
        {"role": "tool",   "content": json.dumps(data)},
    ])


def synthesize_rag_answer(query: str, chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"Source: {c['source']}\n{c['text']}" for c in chunks
    )
    return chat([
        {"role": "system", "content": _RAG_SYSTEM},
        {"role": "user",   "content": f"Question: {query}\n\nDocuments:\n{context}"},
    ])


def suggest_self_fix(topics: list[str]) -> dict | None:
    auto: dict[str, dict] = {
        "upi_pin_blocked": {
            "message": "Aapka UPI PIN block ho gaya hai. App ke settings mein PIN reset karein.",
            "action": "Reset UPI PIN",
        },
        "insufficient_funds": {
            "message": "Account mein balance kam hai. Funds add karein aur retry karein.",
            "action": "Add funds",
        },
        "daily_limit_exceeded": {
            "message": "Aaj ki daily limit exceed ho gayi. Kal retry karein ya limit badhane ki request karein.",
            "action": None,
        },
    }
    for topic in topics:
        if topic in auto:
            return auto[topic]
    return None
