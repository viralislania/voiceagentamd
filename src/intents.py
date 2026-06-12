"""Intent registry — single source of truth.

INTENT_REGISTRY  maps intent name → {handler, required slots}
INTENTS          derived list passed to the LLM classifier prompt
"""

INTENT_REGISTRY: dict[str, dict] = {
    "balance_inquiry":        {"handler": "data_query",       "required": []},
    "account_statement":      {"handler": "data_query",       "required": []},
    "open_fixed_deposit":     {"handler": "deposit_journey",  "required": ["product_id", "amount", "tenure_months"]},
    "open_recurring_deposit": {"handler": "deposit_journey",  "required": ["product_id", "amount", "tenure_months"]},
    "open_savings":           {"handler": "deposit_journey",  "required": []},
    "fund_transfer":          {"handler": "transfer_journey", "required": ["payee_id", "amount", "rail"]},
    "transaction_failure":    {"handler": "failure_flow",     "required": []},
    "raise_complaint":        {"handler": "complaint_flow",   "required": ["description"]},
    "help_knowledge":         {"handler": "knowledge_rag",    "required": []},
    "fallback":               {"handler": "fallback_handler", "required": []},
}

INTENTS: list[str] = list(INTENT_REGISTRY)
