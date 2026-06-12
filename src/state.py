"""AgentState TypedDict — shared state flowing through the LangGraph graph."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict):
    customer_id:    str
    user_msg:       str
    intent:         Optional[str]
    slots:          dict[str, Any]       # accumulated across turns
    pending_slot:   Optional[str]        # next slot the agent is waiting for
    pending_action: Optional[str]        # 'show_txn_detail' | 'await_otp' | None
    tool_result:    Optional[dict]
    response_text:  Optional[str]
    a2ui:           Optional[list[dict]] # list of A2UI v0.9 message dicts
    done:           bool
