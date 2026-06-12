"""A2A server for the banking voice agent.

Exposes the LangGraph graph as an A2A-protocol endpoint that the Flutter
genui_a2a client can connect to via SSE.

Run:
    python -m src.server
    # or
    uvicorn src.server:app --host 0.0.0.0 --port 10002

Environment (via src/config.py / .env):
    AGENT_HOST, AGENT_PORT — bind address
    LLM_PROVIDER, GEMINI_API_KEY, etc.

The agent is stateless between connections; session continuity is maintained by
the client re-sending accumulated slots in each request body via task context.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterable

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from starlette.middleware.cors import CORSMiddleware
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import TaskUpdater
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    DataPart,
    Message,
    MessageSendParams,
    Part,
    Role,
    Task,
    TaskState,
    TextPart,
)
from a2ui.a2a.extension import get_a2ui_agent_extension
from a2ui.schema.constants import VERSION_0_9

from src.a2ui import to_parts
from src.config import settings
from src.graph import build_graph, initial_state

logger = logging.getLogger(__name__)

_graph = build_graph()

AGENT_CARD = AgentCard(
    name="BankingVoiceAgent",
    description="Indian-context banking assistant (EN/HI/Hinglish). Handles balance, statements, deposits, transfers, complaints and policy FAQs.",
    url=f"http://{settings.agent_host}:{settings.agent_port}/",
    version="0.1.0",
    default_input_modes=["text/plain", "application/json"],
    default_output_modes=["text/plain", "application/json", "application/json+a2ui"],
    capabilities=AgentCapabilities(
        streaming=True,
        extensions=[get_a2ui_agent_extension(version=VERSION_0_9)],
    ),
    skills=[
        AgentSkill(id="balance_inquiry",    name="Balance Inquiry",       description="Check account balances",                   tags=["balance", "account"]),
        AgentSkill(id="account_statement",  name="Account Statement",     description="View recent transactions",                 tags=["statement", "transactions"]),
        AgentSkill(id="open_fixed_deposit", name="Open Fixed Deposit",    description="Book FD/RD products",                     tags=["fd", "rd", "deposit"]),
        AgentSkill(id="fund_transfer",      name="Fund Transfer",         description="NEFT/IMPS payments with OTP",             tags=["transfer", "payment", "upi"]),
        AgentSkill(id="raise_complaint",    name="Raise Complaint",       description="Log a service complaint",                 tags=["complaint", "support"]),
        AgentSkill(id="help_knowledge",     name="Help & Policy FAQ",     description="Answers from help docs",                  tags=["faq", "help", "policy"]),
    ],
)


def _extract_text(message: Message) -> str:
    parts = []
    for part in message.parts:
        p = part.root
        if isinstance(p, TextPart):
            parts.append(p.text)
    return " ".join(parts).strip()


def _extract_context(message: Message) -> dict[str, Any]:
    """Pull slots / session state from a DataPart if the client re-sends it."""
    for part in message.parts:
        p = part.root
        if isinstance(p, DataPart):
            try:
                return json.loads(p.data) if isinstance(p.data, str) else p.data
            except Exception:
                pass
    return {}


class BankingAgentExecutor(AgentExecutor):
    """Runs the LangGraph graph and streams TextPart + DataPart A2UI messages."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        t0 = time.perf_counter()
        try:
            await updater.submit()
            await updater.start_work()

            user_msg       = _extract_text(context.message)
            ctx_data       = _extract_context(context.message)
            customer_id    = ctx_data.get("customer_id", "CUST001")
            slots          = ctx_data.get("slots", {})
            pending_action = ctx_data.get("pending_action")

            logger.info(
                "→ task=%s customer=%s pending_action=%s msg=%r",
                context.task_id[:8], customer_id, pending_action, user_msg[:120],
            )

            state  = initial_state(customer_id, user_msg, slots=slots,
                                   pending_action=pending_action)
            result = _graph.invoke(state)

            intent        = result.get("intent")
            response_text = result.get("response_text") or ""
            a2ui_msgs     = result.get("a2ui") or []

            logger.info(
                "← task=%s intent=%s a2ui_msgs=%d done=%s (%.0fms)",
                context.task_id[:8], intent, len(a2ui_msgs),
                result.get("done"), (time.perf_counter() - t0) * 1000,
            )

            out_parts: list[Part] = []

            # Text response
            if response_text:
                out_parts.append(Part(root=TextPart(type="text", text=response_text)))

            # A2UI payload — each dict becomes a DataPart tagged with
            # application/json+a2ui so genui_a2a routes it to the surface controller.
            if a2ui_msgs:
                out_parts.extend(to_parts(a2ui_msgs))

            # Session continuation data (client re-sends this next turn)
            session_state = {
                "customer_id":    customer_id,
                "slots":          result.get("slots", {}),
                "pending_action": result.get("pending_action"),
                "pending_slot":   result.get("pending_slot"),
                "done":           result.get("done", True),
            }
            out_parts.append(Part(root=DataPart(
                type="data",
                data={"_session": session_state},
            )))

            await updater.add_artifact(
                parts=out_parts,
                artifact_id=str(uuid.uuid4()),
                name="banking_response",
            )
            await updater.complete()

        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000
            logger.exception("✗ task=%s ERROR (%.0fms): %s", context.task_id[:8], ms, exc)
            await updater.failed()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def create_app() -> A2AStarletteApplication:
    handler = DefaultRequestHandler(
        agent_executor=BankingAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(
        agent_card=AGENT_CARD,
        http_handler=handler,
    )


app = create_app().build()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "src.server:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=False,
    )
