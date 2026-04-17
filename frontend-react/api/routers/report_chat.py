"""Report Chat Service — Snowflake Cortex conversational Q&A grounded in generated report context."""

from __future__ import annotations

import json
import logging
import os
import re
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
    folder_name: str  # output directory name grounding this session
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

COMPARISON_SYSTEM_PROMPT = """\
You are FinSage, an expert financial research assistant. You are comparing \
multiple stocks based on their generated financial research reports.

Rules:
- Structure comparisons clearly, using sections or tables when helpful.
- Explain financial concepts in plain English.
- When referencing numbers, include the ticker, metric name, and value.
- Keep answers concise but thorough.
- Do NOT give investment advice (e.g. "you should buy/sell"). \
Instead, present facts and let the user draw their own conclusions.
- If the report context does not contain enough information for a ticker, say so \
honestly rather than guessing.
- Highlight key differences and similarities between the stocks.

Stocks being compared: {tickers}
{missing_note}

--- REPORT CONTEXT ---
{report_context}
--- END CONTEXT ---
"""

# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

def _load_report_context(ticker: str, folder_name: str | None = None) -> tuple[str, str]:
    """Load context from an outputs/<TICKER>_*/ directory.

    If *folder_name* is provided, uses that specific directory; otherwise falls
    back to the most recent one by mtime.

    Returns (context_text, resolved_folder_name).
    """
    if not OUTPUTS_DIR.exists():
        return f"No outputs directory found. No generated report available for {ticker}.", ""

    candidates = [
        d for d in OUTPUTS_DIR.iterdir()
        if d.is_dir() and d.name.upper().startswith(f"{ticker.upper()}_")
    ]
    if not candidates:
        return f"No generated report found for {ticker}.", ""

    # Resolve target directory
    out_dir = None
    if folder_name:
        out_dir = next((d for d in candidates if d.name == folder_name), None)
    if out_dir is None:
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
    return context[:MAX_CONTEXT_CHARS], out_dir.name


# ---------------------------------------------------------------------------
# Multi-ticker helpers
# ---------------------------------------------------------------------------

def _get_available_report_tickers() -> set[str]:
    """Return set of tickers that have at least one output folder with a PDF."""
    if not OUTPUTS_DIR.exists():
        return set()
    tickers: set[str] = set()
    for folder in OUTPUTS_DIR.iterdir():
        if not folder.is_dir():
            continue
        parts = folder.name.split("_")
        if len(parts) < 3:
            continue
        ticker_parts: list[str] = []
        for p in parts:
            if len(p) == 8 and p.isdigit():
                break
            ticker_parts.append(p)
        if ticker_parts and list(folder.glob("*.pdf")):
            tickers.add("_".join(ticker_parts))
    return tickers


def _extract_tickers_from_question(question: str, available: set[str]) -> list[str]:
    """Extract ticker symbols mentioned in the question that have reports available.

    Returns list of matched tickers (upper-case). Only matches against tickers
    known to have generated reports so we don't get false positives on common words.
    """
    found: list[str] = []
    q_upper = question.upper()
    for t in sorted(available):
        # Match ticker as a whole word (handles "AAPL vs MSFT" and "compare GOOGL and TSLA")
        if re.search(rf'\b{re.escape(t)}\b', q_upper):
            found.append(t)
    return found


def _load_multi_report_context(tickers: list[str]) -> tuple[str, list[str], list[str]]:
    """Load condensed context for multiple tickers.

    Returns (combined_context, loaded_tickers, missing_tickers).
    Each ticker gets a proportional share of MAX_CONTEXT_CHARS.
    """
    available = _get_available_report_tickers()
    loaded: list[str] = []
    missing: list[str] = []

    for t in tickers:
        if t in available:
            loaded.append(t)
        else:
            missing.append(t)

    if not loaded:
        return "", loaded, missing

    per_ticker_budget = MAX_CONTEXT_CHARS // len(loaded)
    sections: list[str] = []

    for t in loaded:
        ctx, folder = _load_report_context(t)
        # Truncate to per-ticker budget
        truncated = ctx[:per_ticker_budget]
        sections.append(f"=== {t} (from {folder}) ===\n{truncated}")

    combined = "\n\n".join(sections)
    return combined[:MAX_CONTEXT_CHARS], loaded, missing


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

def ask(session: Any, session_id: str, ticker: str, question: str, folder_name: str | None = None) -> dict:
    """Ask a question about the ticker's report via Snowflake Cortex.

    Detects multi-ticker comparison questions automatically. If the user
    mentions other tickers in their question, loads context for all of them.

    Returns dict with keys: answer, missing_tickers (list of tickers without reports).
    """
    ticker = ticker.upper().strip()

    # Check if the question mentions additional tickers
    available = _get_available_report_tickers()
    mentioned = _extract_tickers_from_question(question, available)

    # Also check for tickers mentioned that are NOT in available reports
    # by scanning for common ticker-like patterns (1-5 uppercase letters)
    all_mentioned_raw = set(re.findall(r'\b[A-Z]{1,5}\b', question.upper()))
    # Filter to only plausible tickers (exclude common English words)
    _common_words = {
        "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF",
        "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR", "SO", "TO",
        "UP", "US", "WE", "VS", "THE", "AND", "ARE", "BUT", "CAN", "DID", "FOR",
        "GET", "GOT", "HAS", "HAD", "HER", "HIM", "HIS", "HOW", "ITS", "LET",
        "MAY", "NEW", "NOT", "NOW", "OLD", "OUR", "OUT", "OWN", "SAY", "SHE",
        "TOO", "USE", "WAY", "WHO", "WHY", "ALL", "ANY", "BIG", "DAY", "END",
        "FAR", "FEW", "HAS", "KEY", "MAN", "RUN", "SET", "TOP", "TRY", "TWO",
        "ALSO", "BACK", "BEEN", "BOTH", "CALL", "COME", "EACH", "FIND", "GIVE",
        "GOOD", "HAVE", "HERE", "HIGH", "JUST", "KEEP", "KNOW", "LAST", "LIKE",
        "LONG", "LOOK", "MADE", "MAKE", "MORE", "MOST", "MUCH", "MUST", "NAME",
        "NEXT", "ONLY", "OVER", "PART", "SAME", "SHOW", "SUCH", "TAKE", "TELL",
        "THAN", "THAT", "THEM", "THEN", "THEY", "THIS", "TIME", "TURN", "VERY",
        "WANT", "WELL", "WHAT", "WHEN", "WILL", "WITH", "WORK", "YEAR",
        "ABOUT", "AFTER", "BEING", "COULD", "EVERY", "FIRST", "FOUND", "GREAT",
        "THEIR", "THERE", "THESE", "THINK", "THREE", "UNDER", "WHERE", "WHICH",
        "WHILE", "WOULD", "RISK", "BEAR", "BULL", "STOCK",
        "COMPARE", "REVENUE", "GROWTH", "PRICE", "MARKET", "SHARE",
    }
    # Load the configured tickers list for better matching
    config_tickers_path = PROJECT_ROOT / "config" / "tickers.yaml"
    known_tickers: set[str] = set()
    if config_tickers_path.exists():
        try:
            import yaml
            with open(config_tickers_path) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "tickers" in data:
                for sector_tickers in data["tickers"].values():
                    if isinstance(sector_tickers, list):
                        known_tickers.update(t.upper() for t in sector_tickers)
        except Exception:
            pass

    # Find tickers mentioned that don't have reports
    missing_tickers: list[str] = []
    for raw_t in all_mentioned_raw:
        if raw_t in _common_words:
            continue
        if raw_t in available:
            continue  # has a report
        if raw_t in known_tickers:
            missing_tickers.append(raw_t)

    # Build the set of all tickers to include in context
    all_tickers = list(dict.fromkeys([ticker] + mentioned))  # dedupe, preserve order

    is_comparison = len(all_tickers) > 1

    if is_comparison:
        # Multi-ticker comparison mode
        multi_context, loaded, multi_missing = _load_multi_report_context(all_tickers)
        missing_tickers = list(set(missing_tickers + multi_missing))

        missing_note = ""
        if missing_tickers:
            missing_note = (
                f"Note: The following tickers were mentioned but have no generated reports: "
                f"{', '.join(missing_tickers)}. Please generate reports for these tickers first."
            )

        system_content = COMPARISON_SYSTEM_PROMPT.format(
            report_context=multi_context,
            tickers=", ".join(loaded),
            missing_note=missing_note,
        )
    else:
        # Single-ticker mode (original behavior)
        with _lock:
            state = _sessions.get(session_id)
            needs_reset = (
                state is None
                or state["ticker"] != ticker
                or (folder_name and state.get("folder_name") != folder_name)
            )
            if needs_reset:
                report_context, resolved_folder = _load_report_context(ticker, folder_name)
                _sessions[session_id] = {
                    "ticker": ticker,
                    "folder_name": resolved_folder,
                    "history": [],
                }
                state = _sessions[session_id]
            else:
                report_context, _ = _load_report_context(ticker, state.get("folder_name"))
        system_content = SYSTEM_PROMPT.format(report_context=report_context)

    # Build messages array
    with _lock:
        state = _sessions.get(session_id)
        if state is None:
            _sessions[session_id] = {
                "ticker": ticker,
                "folder_name": "",
                "history": [],
            }
            state = _sessions[session_id]

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        for msg in state["history"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": question})

    # Call Cortex outside the lock
    answer = _call_cortex(session, messages)

    with _lock:
        state = _sessions.get(session_id)
        if state is not None:
            state["history"].append({"role": "user", "content": question})
            state["history"].append({"role": "assistant", "content": answer})

            max_entries = MAX_HISTORY_TURNS * 2
            if len(state["history"]) > max_entries:
                state["history"] = state["history"][-max_entries:]

    return {"answer": answer, "missing_tickers": missing_tickers}


def reset_session(session_id: str) -> bool:
    """Clear a session's history and ticker binding. Returns True if found."""
    with _lock:
        if session_id in _sessions:
            del _sessions[session_id]
            return True
        return False
