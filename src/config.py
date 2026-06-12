"""App configuration — reads from .env, reloads automatically on file changes.

Usage:
    from src.config import settings   # always current values

The module starts a background watchfiles watcher so that editing .env during
development is picked up without restarting the process.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider
    llm_provider: str = "gemini"          # "gemini" | "vllm"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    vllm_url: str = "http://localhost:8001/v1"
    vllm_model: str = "meta-llama/Llama-3.1-8B-Instruct"

    # Backend
    backend_url: str = "http://localhost:8000/open-banking/v1"
    db_path: str = "src/backend/bank.db"

    # RAG (ChromaDB)
    rag_docs_glob: str = "src/backend/docs/*.md"
    rag_db_path: str = "src/backend/chroma_db"
    rag_model: str = "intfloat/multilingual-e5-small"
    rag_top_k: int = 3

    # A2A server
    agent_host: str = "localhost"
    agent_port: int = 10002


# Module-level singleton; reassigned on .env change
settings = Settings()


def _reload() -> None:
    global settings
    try:
        settings = Settings()
        logger.info("Settings reloaded from .env")
    except Exception as exc:
        logger.warning(f"Settings reload failed: {exc}")


def _watch_env() -> None:
    """Background thread: watch .env and reload settings on change."""
    try:
        import watchfiles

        async def _awatch() -> None:
            async for _ in watchfiles.awatch(str(_ENV_FILE), stop_event=_stop):
                _reload()

        _loop = asyncio.new_event_loop()
        _loop.run_until_complete(_awatch())
    except ImportError:
        logger.debug("watchfiles not installed — .env hot-reload disabled")
    except Exception as exc:
        logger.debug(f"Env watcher stopped: {exc}")


_stop = threading.Event()
_watcher = threading.Thread(target=_watch_env, daemon=True, name="env-watcher")
_watcher.start()
