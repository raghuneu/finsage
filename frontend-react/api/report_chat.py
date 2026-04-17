"""Report Chat — Snowflake Cortex conversational Q&A grounded in generated report context."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session store — in-process dict, wiped on server restart
# ---------------------------------------------------------------------------

class _Message(TypedDict):
    role: str   # "user" or "assistant"
    content: str


_sessions: Dict[str, List[_Message]] = {}

OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "outputs"
CORTEX_MODEL = os.getenv("CORTEX_MODEL_LLM", "claude-opus-4-6")

# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

def _latest_output_dir(ticker: str) -> Path | None:
    """Return the most-recent outputs/<TICKER>_*/ directory for a ticker."""
    if not OUTPUTS_DIR.exists():
        return None
    candidates = sorted(
        [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and d.name.startswith(f"{ticker}_")],
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_report_context(ticker: str) -> str:
    """Build a context string from the latest report's JSON artifacts."""
    out_dir = _latest_output_dir(ticker)
    if out_dir is None:
        return f"No generated report found for {ticker}. Answer based on general financial knowledge."

    parts: List[str] = [f"Generated report directory: {out_dir.name}"]

    # pipeline_result.json
    pr = out_dir / "pipeline_result.json"
    if pr.exists():
        data = json.loads(pr.read_text())
        parts.append(f"Pipeline result:\n{json.dumps(data, indent=2)}")

    # chart_manifest.json
    cm = out_dir / "chart_manifest.json"
    if cm.exists():
        data = json.loads(cm.read_text())
        parts.append(f"Chart manifest (data summaries per chart):\n{json.dumps(data, indent=2)}")

    # Pick up any .md or .txt analysis files if present
    for ext in ("*.md", "*.txt"):
        for f in out_dir.glob(ext):
            text = f.read_text()[:30_000]  # cap per file
            parts.append(f"--- {f.name} ---\n{text}")

    context = "\n\n".join(parts)
    # Hard cap to stay within Cortex prompt limits
    return context[:50_000]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_TEMPLATE = """\
You are FinSage Report Assistant — an AI that answers questions about a generated \
financial research report for {ticker}.

Below is the report context (chart data summaries, pipeline metadata, and any \
analysis text that was saved alongside the PDF). Use this context to give accurate, \
specific answers. If the context doesn't contain enough information to answer, say so \
honestly rather than guessing.

Explain financial concepts in plain English. When referencing numbers, include the \
metric name and value. Keep answers concise but thorough.

--- REPORT CONTEXT ---
{report_context}
--- END CONTEXT ---
"""


def _build_prompt(ticker: str, session_id: str, question: str) -> str:
    """Build a single prompt string with system context + conversation history + new question."""
    report_context = _load_report_context(ticker)
    system = SYSTEM_TEMPLATE.format(ticker=ticker, report_context=report_context)

    history = _sessions.get(session_id, [])

    parts = [system, ""]
    for msg in history:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role_label}: {msg['content']}")

    parts.append(f"User: {question}")
    parts.append("Assistant:")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Cortex caller
# ---------------------------------------------------------------------------

def _cortex_complete(session, prompt: str) -> str:
    """Call Snowflake Cortex COMPLETE() with the given prompt."""
    escaped = prompt.replace("'", "''")
    # Truncate if too long for Cortex
    if len(escaped) > 50_000:
        escaped = escaped[:50_000]
        logger.warning("Prompt truncated to 50k characters for Cortex")

    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{CORTEX_MODEL}', '{escaped}') AS response"
    result = session.sql(sql).collect()
    return result[0]["RESPONSE"]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def ask(session, ticker: str, session_id: str, question: str) -> str:
    """Ask a question about the ticker's report via Snowflake Cortex. Returns the answer string."""
    prompt = _build_prompt(ticker, session_id, question)
    answer = _cortex_complete(session, prompt)

    # Store in session history
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": "user", "content": question})
    _sessions[session_id].append({"role": "assistant", "content": answer})

    # Cap history at 20 turns (10 exchanges) to keep prompt size manageable
    if len(_sessions[session_id]) > 20:
        _sessions[session_id] = _sessions[session_id][-20:]

    return answer


def reset_session(session_id: str) -> bool:
    """Clear a session's memory. Returns True if a session was found and cleared."""
    if session_id in _sessions:
        del _sessions[session_id]
        return True
    return False
