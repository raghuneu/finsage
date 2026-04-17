"""Report Chat Service — Snowflake Cortex conversational Q&A grounded in generated report context."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CORTEX_MODEL = os.getenv("CORTEX_CHAT_MODEL", "claude-sonnet-4-6")
MAX_HISTORY_TURNS = 10
MAX_CONTEXT_CHARS = 40_000

# ---------------------------------------------------------------------------
# Session store — in-process dict, wiped on uvicorn restart
# ---------------------------------------------------------------------------

class _Message(TypedDict):
    role: str   # "user" or "assistant"
    content: str


class _SessionState(TypedDict):
    ticker: str
    history: List[_Message]


_sessions: Dict[str, _SessionState] = {}
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are FinSage, an expert financial research assistant. You answer follow-up \
questions about a generated financial research report.

Rules:
- Explain financial concepts in plain English.
- When referencing numbers, include the metric name and value.
- Keep answers concise but thorough.
- Do NOT give investment advice (e.g. "you should buy/sell"). \
Instead, present facts and let the user draw their own conclusions.
- If the report context does not contain enough information to answer, say so \
honestly rather than guessing.
- Reference specific data from the report when possible.

--- REPORT CONTEXT ---
{report_context}
--- END CONTEXT ---
"""

# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

def _load_report_context(ticker: str) -> str:
    """Load context from the most recent outputs/<TICKER>_*/ directory.

    Reads pipeline_result.json, chart_manifest.json, *.md, analysis*.txt,
    *analysis*.json, and executive_summary* files. Caps at MAX_CONTEXT_CHARS.
    """
    if not OUTPUTS_DIR.exists():
        return f"No outputs directory found. No generated report available for {ticker}."

    # Pick most recent directory by mtime
    candidates = [
        d for d in OUTPUTS_DIR.iterdir()
        if d.is_dir() and d.name.upper().startswith(f"{ticker.upper()}_")
    ]
    if not candidates:
        return f"No generated report found for {ticker}."

    out_dir = max(candidates, key=lambda p: p.stat().st_mtime)

    parts: List[str] = [f"Report directory: {out_dir.name}"]

    # pipeline_result.json
    pr = out_dir / "pipeline_result.json"
    if pr.exists():
        try:
            data = json.loads(pr.read_text())
            parts.append(f"Pipeline result:\n{json.dumps(data, indent=2)}")
        except Exception:
            logger.warning("Failed to parse pipeline_result.json")

    # chart_manifest.json
    cm = out_dir / "chart_manifest.json"
    if cm.exists():
        try:
            data = json.loads(cm.read_text())
            parts.append(f"Chart manifest (data summaries per chart):\n{json.dumps(data, indent=2)}")
        except Exception:
            logger.warning("Failed to parse chart_manifest.json")

    # *.md files
    for f in sorted(out_dir.glob("*.md")):
        text = f.read_text()[:30_000]
        parts.append(f"--- {f.name} ---\n{text}")

    # analysis*.txt files
    for f in sorted(out_dir.glob("analysis*.txt")):
        text = f.read_text()[:30_000]
        parts.append(f"--- {f.name} ---\n{text}")

    # *analysis*.json files
    for f in sorted(out_dir.glob("*analysis*.json")):
        if f.name in ("pipeline_result.json", "chart_manifest.json"):
            continue
        try:
            data = json.loads(f.read_text())
            parts.append(f"--- {f.name} ---\n{json.dumps(data, indent=2)}")
        except Exception:
            pass

    # executive_summary* files
    for f in sorted(out_dir.glob("executive_summary*")):
        if any(f.name == p.split("--- ")[0] for p in parts):
            continue
        text = f.read_text()[:30_000]
        parts.append(f"--- {f.name} ---\n{text}")

    context = "\n\n".join(parts)
    return context[:MAX_CONTEXT_CHARS]


# ---------------------------------------------------------------------------
# Cortex caller
# ---------------------------------------------------------------------------

def _call_cortex(session: Any, messages: List[Dict[str, str]]) -> str:
    """Call Snowflake Cortex COMPLETE() with a messages array.

    Tries parameterized query first, falls back to inline SQL with escaping.
    Parses multiple possible response formats from Cortex.
    """
    messages_json = json.dumps(messages)
    options_json = json.dumps({"temperature": 0.3, "max_tokens": 2048})

    # Try parameterized call first
    try:
        sql = (
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, PARSE_JSON(?), "
            "PARSE_JSON(?)) AS response"
        )
        result = session.sql(sql, params=[CORTEX_MODEL, messages_json, options_json]).collect()
        return _parse_cortex_response(result[0]["RESPONSE"])
    except Exception as e:
        logger.debug("Parameterized Cortex call failed (%s), trying inline SQL", e)

    # Fallback: inline SQL with escaping
    escaped_messages = messages_json.replace("\\", "\\\\").replace("'", "\\'")
    escaped_options = options_json.replace("'", "\\'")
    sql = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', "
        f"PARSE_JSON('{escaped_messages}'), "
        f"PARSE_JSON('{escaped_options}')) AS response"
    )
    result = session.sql(sql).collect()
    return _parse_cortex_response(result[0]["RESPONSE"])


def _parse_cortex_response(raw: str) -> str:
    """Parse Cortex COMPLETE response — handles multiple formats."""
    try:
        data = json.loads(raw)
        # Format: {"choices": [{"messages": "..."}]}
        if isinstance(data, dict) and "choices" in data:
            choice = data["choices"][0]
            if "messages" in choice:
                return choice["messages"]
            if "message" in choice:
                msg = choice["message"]
                if isinstance(msg, dict) and "content" in msg:
                    return msg["content"]
                return str(msg)
            if "text" in choice:
                return choice["text"]
        # Format: {"message": {"content": "..."}}
        if isinstance(data, dict) and "message" in data:
            msg = data["message"]
            if isinstance(msg, dict) and "content" in msg:
                return msg["content"]
        # If parsed but unexpected structure, stringify
        return str(data)
    except (json.JSONDecodeError, TypeError):
        # Raw text response
        return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ask(session: Any, session_id: str, ticker: str, question: str) -> str:
    """Ask a question about the ticker's report via Snowflake Cortex.

    Binds session_id to ticker on first call. If the ticker changes mid-session,
    the session history is reset. Returns the answer string.
    """
    ticker = ticker.upper().strip()

    with _lock:
        state = _sessions.get(session_id)
        if state is None or state["ticker"] != ticker:
            # New session or ticker changed — reset
            report_context = _load_report_context(ticker)
            _sessions[session_id] = {
                "ticker": ticker,
                "history": [],
            }
            state = _sessions[session_id]
        else:
            report_context = _load_report_context(ticker)

        # Build messages array for Cortex
        system_content = SYSTEM_PROMPT.format(report_context=report_context)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        # Add conversation history
        for msg in state["history"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add the new user question
        messages.append({"role": "user", "content": question})

    # Call Cortex outside the lock to avoid blocking other sessions
    answer = _call_cortex(session, messages)

    with _lock:
        state = _sessions.get(session_id)
        if state is not None:
            state["history"].append({"role": "user", "content": question})
            state["history"].append({"role": "assistant", "content": answer})

            # Cap at MAX_HISTORY_TURNS (each turn = 1 user + 1 assistant = 2 entries)
            max_entries = MAX_HISTORY_TURNS * 2
            if len(state["history"]) > max_entries:
                state["history"] = state["history"][-max_entries:]

    return answer


def reset_session(session_id: str) -> bool:
    """Clear a session's history and ticker binding. Returns True if found."""
    with _lock:
        if session_id in _sessions:
            del _sessions[session_id]
            return True
        return False
