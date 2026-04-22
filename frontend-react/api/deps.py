"""Shared dependencies for FastAPI routers."""

from __future__ import annotations

import sys
import os
import logging
import threading
from pathlib import Path

# Add project root to path so we can import existing modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "sec_filings"))
sys.path.insert(0, str(PROJECT_ROOT / "agents"))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from snowflake_connection import get_session

logger = logging.getLogger("finsage.deps")


# ── Snowflake session pool ─────────────────────────────────
# Reuse sessions instead of creating/destroying per request.
# The pool is a simple thread-safe list of sessions.

_session_pool: list = []
_pool_lock = threading.Lock()
_POOL_MAX_SIZE = int(os.getenv("SNOWFLAKE_POOL_SIZE", "3"))


def _create_session():
    """Create a single Snowflake session."""
    return get_session()


def init_session_pool():
    """Pre-warm the session pool at startup."""
    with _pool_lock:
        if _session_pool:
            return
        try:
            session = _create_session()
            _session_pool.append(session)
            logger.info("Session pool initialized with 1 session (max %d)", _POOL_MAX_SIZE)
        except Exception as e:
            logger.warning("Failed to pre-warm session pool: %s", e)


def close_session_pool():
    """Close all pooled sessions at shutdown."""
    with _pool_lock:
        for s in _session_pool:
            try:
                s.close()
            except Exception:
                pass
        _session_pool.clear()
        logger.info("Session pool closed")


def _acquire_session():
    """Get a session from the pool or create a new one."""
    with _pool_lock:
        if _session_pool:
            return _session_pool.pop()
    return _create_session()


def _release_session(session):
    """Return a session to the pool (or close it if pool is full)."""
    with _pool_lock:
        if len(_session_pool) < _POOL_MAX_SIZE:
            _session_pool.append(session)
            return
    # Pool is full — close the excess session
    try:
        session.close()
    except Exception:
        pass


def get_snowpark_session():
    """Yield a pooled Snowpark session for each request."""
    session = _acquire_session()
    try:
        yield session
    except Exception:
        # Session may be broken — close it instead of returning to pool
        try:
            session.close()
        except Exception:
            pass
        raise
    else:
        _release_session(session)


def get_tickers() -> list[str]:
    """Load ticker list from config/tickers.yaml or return defaults."""
    import yaml

    tickers_path = PROJECT_ROOT / "config" / "tickers.yaml"
    if tickers_path.exists():
        with open(tickers_path) as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "tickers" in data:
                return data["tickers"]
            if isinstance(data, list):
                return data
    return ["AAPL", "GOOGL", "JPM", "MSFT", "TSLA"]
