"""LLM provider abstraction.

Set LLM_PROVIDER=gemini  (default) for Gemini Flash 2.0 — no GPU needed.
Set LLM_PROVIDER=vllm    for vLLM-served Llama-3.1-8B (or fine-tuned variant).

Both providers support json_mode=True for strict JSON output.
"""
from __future__ import annotations

import json
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")


def chat(
    messages: list[dict],
    json_mode: bool = False,
    temperature: float = 0.0,
) -> str:
    if LLM_PROVIDER == "vllm":
        return _vllm(messages, json_mode, temperature)
    return _gemini(messages, json_mode, temperature)


def _gemini(messages: list[dict], json_mode: bool, temperature: float) -> str:
    import google.genai as genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)

    # gemini-2.0-flash is the current fast model; fall back to gemini-1.5-flash
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)

    cfg: dict = {"temperature": temperature}
    if json_mode:
        cfg["response_mime_type"] = "application/json"

    # Gemini uses a flat list of text parts; build from messages
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.insert(0, f"[System]: {content}")
        elif role == "tool":
            parts.append(f"[Tool result]: {content}")
        else:
            parts.append(content)

    response = model.generate_content(parts, generation_config=cfg)
    return response.text


def _vllm(messages: list[dict], json_mode: bool, temperature: float) -> str:
    import requests as _requests

    base = os.getenv("VLLM_URL", "http://localhost:8001/v1")
    model = os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    r = _requests.post(f"{base}/chat/completions", json=body, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ── Structured helpers ────────────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are a banking assistant intent classifier for Indian customers (English/Hindi/Hinglish).

Given a user message, return ONLY a JSON object with:
  "intent": one of {intents}
  "slots": dict of extracted slot values (account_id, amount, category, rail, payee_name, period, tenure_months, txn_id, description, from_date, to_date — omit if not present)

Rules:
- "balance_inquiry" → user wants current account balance
- "account_statement" → user wants spend/transaction history (may include category/rail filter, date range)
- "fund_transfer" → user wants to send money to someone
- "open_fixed_deposit" → user wants to open an FD
- "open_recurring_deposit" → user wants to open an RD
- "open_savings" → user wants to open a savings account
- "transaction_failure" → user reporting a failed transaction or asking why it failed
- "raise_complaint" → user wants to file a complaint
- "help_knowledge" → user asking a policy/FAQ/how-to question (do NOT use for real balance/transaction numbers)
- "fallback" → unclear, out of scope, or greeting

Period slot values: "today", "this_week", "last_week", "this_month", "last_month", or ISO date range.
Rail slot values: "upi", "neft", "imps", "card".
Category slot values: "food", "shopping", "bills", "salary", "transfer".
"""

EXTRACT_INSIGHTS_SYSTEM = """Extract complaint insights from the user message.
Return ONLY JSON: {"topics": [list of topic strings], "sentiment": "angry"|"frustrated"|"neutral"}
Topics should be specific: failed_transfer, debited_amount, poor_support, delayed_refund, wrong_amount, unauthorized_txn, app_error.
"""


def llm_classify(user_msg: str, intents: list[str], history: dict | None = None) -> dict:
    system = CLASSIFY_SYSTEM.format(intents=", ".join(intents))
    messages = [{"role": "system", "content": system}]
    if history:
        messages.append({"role": "user", "content": f"[Context slots so far: {history}]"})
    messages.append({"role": "user", "content": user_msg})
    raw = chat(messages, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"intent": "fallback", "slots": {}}


def extract_complaint_insights(description: str) -> dict:
    messages = [
        {"role": "system", "content": EXTRACT_INSIGHTS_SYSTEM},
        {"role": "user", "content": description},
    ]
    raw = chat(messages, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"topics": [], "sentiment": "neutral"}


def format_numbers(data: dict, user_msg: str) -> str:
    """Format tool result data into a natural response. Never invents numbers."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful banking assistant. Format the tool result as a brief, "
                "friendly response in the same language as the user message (English/Hindi/Hinglish). "
                "Use ONLY the numbers present in the Data field. Do not invent or estimate figures."
            ),
        },
        {"role": "user", "content": user_msg},
        {"role": "tool", "content": json.dumps(data)},
    ]
    return chat(messages)


def synthesize_rag_answer(query: str, chunks: list[dict]) -> str:
    """Synthesize a grounded answer from RAG chunks. Quotes only retrieved figures."""
    context = "\n\n---\n\n".join(
        f"Source: {c['source']}\n{c['text']}" for c in chunks
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Answer the user's question using ONLY the provided document excerpts. "
                "If the answer is not in the excerpts, say so. "
                "Cite the source file name. Keep the answer concise."
            ),
        },
        {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{context}"},
    ]
    return chat(messages)


def suggest_self_fix(topics: list[str]) -> dict | None:
    """Return a self-fix suggestion dict if the issue can be resolved without a ticket, else None."""
    auto_resolvable = {
        "upi_pin_blocked": {
            "message": "Aapka UPI PIN block ho gaya hai. App ke settings mein jaakar PIN reset karein.",
            "action": "Reset UPI PIN",
        },
        "insufficient_funds": {
            "message": "Account mein balance kam hai. Please funds add karein aur retry karein.",
            "action": "Add funds",
        },
        "daily_limit_exceeded": {
            "message": "Aaj ki limit exceed ho gayi hai. Kal retry karein ya limit badhane ke liye request karein.",
            "action": None,
        },
    }
    for topic in topics:
        if topic in auto_resolvable:
            return auto_resolvable[topic]
    return None
