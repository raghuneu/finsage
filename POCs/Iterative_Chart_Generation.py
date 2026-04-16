"""
FinSage — Iterative Vision-Enhanced Chart Generator
====================================================
Implements FinSight paper Section 2.4:
    LLM generates matplotlib code → chart rendered → VLM critiques image
    → LLM refines → repeat x 3 → professional-quality output

Model split (mirrors FinSight architecture):
    LLM role  → Snowflake Cortex (llama3.1-70b) — code generation
    VLM role  → Snowflake Cortex (llama3.1-70b) — text-based critique
               (swap vlm_critique to Gemini once billing is enabled)

Usage:
    # Works with no API keys — uses hardcoded data and mock responses
    python POCs/Iterative_Chart_Generation.py --mock

    # Real mode — needs working Snowflake connection
    python POCs/Iterative_Chart_Generation.py --ticker AAPL
    python POCs/Iterative_Chart_Generation.py --ticker TSLA --days 60

Install:
    .venv\\Scripts\\pip install matplotlib snowflake-ml-python
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import re

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── Output directory ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "iterative_charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# MOCK DATA
# Used when --mock flag is passed. Zero dependencies, works right now.
# ══════════════════════════════════════════════════════════════════════════════

# MOCK_DATA = [
#     {"date": "2025-01-06", "close": 243.36, "volume": 40500000, "high": 247.10, "low": 240.80},
#     {"date": "2025-01-13", "close": 248.13, "volume": 38200000, "high": 250.40, "low": 245.60},
#     {"date": "2025-01-21", "close": 241.84, "volume": 55100000, "high": 249.20, "low": 239.50},
#     {"date": "2025-01-27", "close": 249.72, "volume": 45800000, "high": 252.00, "low": 247.30},
#     {"date": "2025-02-03", "close": 253.20, "volume": 41300000, "high": 255.80, "low": 251.10},
#     {"date": "2025-02-10", "close": 247.88, "volume": 48700000, "high": 254.20, "low": 245.90},
#     {"date": "2025-02-18", "close": 255.64, "volume": 53200000, "high": 258.10, "low": 253.40},
#     {"date": "2025-02-24", "close": 252.12, "volume": 39600000, "high": 256.30, "low": 250.80},
#     {"date": "2025-03-03", "close": 259.45, "volume": 50100000, "high": 261.80, "low": 256.20},
#     {"date": "2025-03-10", "close": 262.18, "volume": 55400000, "high": 264.50, "low": 259.30},
# ]

MOCK_CODE_ITER1 = """
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df["date_str"], df["close"], color="#8884d8")
ax.set_title("AAPL Stock Price")
plt.xticks(rotation=45)
"""

MOCK_CRITIQUE_1 = (
    "❌ Information density is very low — only close price is shown, "
    "but volume and moving averages are available and standard in equity charts.\n"
    "❌ Axis labels are missing entirely — no units, no axis titles, "
    "making the chart unreadable in a report context.\n"
    "❌ No legend or gridlines — impossible to read precise values or identify the series.\n"
    "❌ Color choice (#8884d8) is non-standard — professional charts use blue or black for price."
)

MOCK_CODE_ITER2 = """
fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()
ax1.plot(df["date_str"], df["close"], color="#1f77b4", linewidth=2, label="Close Price")
ax1.plot(df["date_str"], df["ma5"], color="#ff7f0e", linewidth=1.5,
         linestyle="--", label="MA5")
ax2.bar(df["date_str"], df["volume_m"], color="#94a3b8", alpha=0.3, label="Volume (M)")
ax1.set_ylabel("Price (USD)")
ax2.set_ylabel("Volume (M)")
ax1.set_title("AAPL Stock Price with Volume and MA5")
ax1.grid(True, alpha=0.3, linestyle="--")
ax1.legend(loc="upper left", fontsize=9)
plt.xticks(rotation=45)
"""

MOCK_CRITIQUE_2 = (
    "⚠️ Clear improvements: volume and MA5 added, axes are now labeled. "
    "The chart reads much better than the first iteration.\n"
    "⚠️ High/Low range is still absent — a shaded band between high and low "
    "is standard in equity research charts and adds valuable context."
)

MOCK_CODE_ITER3 = """
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor("#f8f9fa")
fig.patch.set_facecolor("white")
ax2 = ax1.twinx()
ax1.fill_between(df["date_str"], df["low"], df["high"],
                 alpha=0.06, color="gray", label="High/Low range")
ax1.fill_between(df["date_str"], df["close"].min(), df["close"],
                 alpha=0.15, color="#2563eb")
ax1.plot(df["date_str"], df["close"], color="#2563eb",
         linewidth=2, label="Close Price")
ax1.plot(df["date_str"], df["ma5"], color="#f59e0b",
         linewidth=2, linestyle=(0, (5, 3)), label="MA5")
ax2.bar(df["date_str"], df["volume_m"], color="#94a3b8", alpha=0.3, label="Volume (M)")
ax1.set_ylabel("Price (USD)", fontsize=11)
ax2.set_ylabel("Volume (M)", fontsize=11)
ax1.set_title("AAPL Weekly Price Analysis — Jan to Mar 2025",
              fontsize=14, fontweight="bold")
ax1.grid(True, color="#e0e0e0", alpha=0.7, linestyle="--", linewidth=0.5)
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(handles1 + handles2, labels1 + labels2,
           loc="upper left", fontsize=9, framealpha=0.9)
plt.xticks(rotation=30, fontsize=9)
"""

MOCK_FINAL_REVIEW = (
    "✅ APPROVED — Chart meets professional equity research standards with clear price, "
    "volume, and trend indicators, proper labeling, and publication-quality styling."
)


# ══════════════════════════════════════════════════════════════════════════════
# LLM ROLE — Snowflake Cortex (llama3.1-70b)
# Generates and refines matplotlib chart code
# ══════════════════════════════════════════════════════════════════════════════

def llm_complete(session, model: str, prompt: str) -> str:
    """
    LLM role: generates and refines matplotlib chart code.
    Uses Snowflake Cortex — no external API key needed.
    """
    from snowflake.cortex import complete

    result = complete(model, prompt, session=session)

    # Strip markdown code fences Cortex sometimes wraps around code
    result = result.strip()
    if result.startswith("```"):
        lines = result.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        result = "\n".join(lines)

    return result.strip()


# ══════════════════════════════════════════════════════════════════════════════
# VLM ROLE — Snowflake Cortex (llama3.1-70b) — text-based critique
# ══════════════════════════════════════════════════════════════════════════════
#
# NOTE: The FinSight paper uses Qwen2.5-VL-72B which critiques rendered images.
# pixtral-large image input is blocked on Snowflake EDU accounts.
# Gemini Flash (real image critique) can be swapped in once billing is enabled:
#
#   from google import genai
#   from google.genai import types
#   client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#   with open(image_path, "rb") as f:
#       image_bytes = f.read()
#   response = client.models.generate_content(
#       model="gemini-2.0-flash",
#       contents=[
#           types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
#           types.Part.from_text(text=prompt),
#       ]
#   )
#   return response.text.strip()
#
# ══════════════════════════════════════════════════════════════════════════════

def vlm_critique(session, model: str, image_path: str, prompt: str) -> str:
    """
    VLM role: critiques the chart via Cortex text reasoning.
    image_path is accepted for interface consistency but not used until
    Gemini billing is enabled (see swap instructions above).
    """
    from snowflake.cortex import complete

    result = complete(model, prompt, session=session)

    result = result.strip()
    if result.startswith("```"):
        lines = result.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        result = "\n".join(lines)

    return result.strip()


# ══════════════════════════════════════════════════════════════════════════════
# SNOWFLAKE DATA FETCH
# ══════════════════════════════════════════════════════════════════════════════

def fetch_snowflake_data(ticker: str, days: int = 90) -> pd.DataFrame:
    """Pull OHLCV data from Snowflake staging layer."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from snowflake_connection import get_session

    session = get_session()
    try:
        df = session.sql(f"""
            SELECT DATE, OPEN, HIGH, LOW, CLOSE, VOLUME
            FROM FINSAGE_DB.STAGING.STG_STOCK_PRICES
            WHERE TICKER = '{ticker.upper()}'
            ORDER BY DATE DESC
            LIMIT {days}
        """).to_pandas()
    finally:
        session.close()

    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ma5"] = df["close"].rolling(window=5).mean().round(2)
    df["volume_m"] = (df["volume"] / 1_000_000).round(2)
    df["date_str"] = df["date"].dt.strftime("%b %d")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CHART CODE EXECUTOR
# Runs LLM-generated matplotlib code safely in a subprocess
# ══════════════════════════════════════════════════════════════════════════════

def execute_chart_code(code: str, df: pd.DataFrame, output_path: str):
    """
    Writes df to a temp CSV, wraps LLM code in a runner script,
    executes in subprocess, saves chart PNG to output_path.
    Raises RuntimeError with actual stderr if rendering fails.
    """
    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        df.to_csv(f, index=False)
        csv_path = f.name

    # Sanitize known bad kwargs Cortex sometimes generates
    code = code.replace("fillalpha=", "alpha=")
    code = code.replace("fill_alpha=", "alpha=")
    code = code.replace(
        ".legend(lines1 + lines2)",
        ".legend(lines1 + lines2, labels1 + labels2)"
    )
    code = re.sub(r'\(20\d\d-20\d\d\)', '', code)

    runner = textwrap.dedent(f"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv(r"{csv_path}")
df["date"] = pd.to_datetime(df["date"])

{code}

try:
    plt.tight_layout()
except Exception:
    pass
plt.savefig(r"{output_path}", dpi=150, bbox_inches="tight", facecolor="white")
plt.close("all")
""")

    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(runner)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Chart render failed (exit {result.returncode}):\n"
                f"{result.stderr[-1500:]}"
            )
    finally:
        os.unlink(script_path)
        os.unlink(csv_path)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# System prompt enforces raw code output — no markdown fences
# ══════════════════════════════════════════════════════════════════════════════

CHART_CODE_SYSTEM = (
    "Return ONLY raw executable Python code. "
    "NO markdown, NO backticks, NO ```python fences, NO explanations, NO comments. "
    "Start directly with code statements. "
    "Already available — do NOT import or redefine: "
    "pandas as pd, matplotlib.pyplot as plt, matplotlib.ticker as mticker, "
    "numpy as np, df (DataFrame with columns: date, open, high, low, close, "
    "volume, ma5, volume_m, date_str). "
    "Do NOT call plt.show() or plt.savefig()."
)


def prompt_iter1(ticker: str, df: pd.DataFrame) -> str:
    return (
        f"{CHART_CODE_SYSTEM}\n\n"
        f"Generate a BASIC, intentionally minimal matplotlib chart for {ticker} stock.\n"
        f"Data: {len(df)} rows | "
        f"close range ${df['close'].min():.2f}-${df['close'].max():.2f} | "
        f"date range {df['date_str'].iloc[0]} to {df['date_str'].iloc[-1]}\n\n"
        "Requirements — keep this simple on purpose:\n"
        "- Single line chart of close price only\n"
        "- Use date_str on x-axis, rotate labels 45 degrees\n"
        "- No gridlines, no legend, no axis labels\n"
        "- Default matplotlib blue line, no custom styling\n"
        f"- Title: \"{ticker} Stock Price\"\n"
        "- figsize=(12, 5)"
    )


def prompt_critique_1(ticker: str) -> str:
    return (
        f"You are a top-tier visualization critic refining a {ticker} stock chart "
        "for publication-grade financial research.\n\n"
        "Evaluate on these dimensions:\n"
        "1. Communication — does it clearly answer the price/volume trend question?\n"
        "2. Clarity — are axes, ticks, legends, and title present and accurate?\n"
        "3. Aesthetics — are colors professional and series clearly distinguished?\n"
        "4. Core improvements (max 2) — give concrete, specific fixes with rationale.\n"
        "5. Verdict — state what still needs fixing. Do NOT say FINISH yet.\n\n"
        "Plain text only. Be specific and actionable."
    )

def prompt_iter2(ticker: str, prev_code: str, critique: str) -> str:
    return (
        f"{CHART_CODE_SYSTEM}\n\n"
        f"Improve this {ticker} chart based on the VLM critique.\n\n"
        f"Previous code:\n{prev_code}\n\n"
        f"VLM critique:\n{critique}\n\n"
        "Apply these improvements:\n"
        "- Add volume_m as semi-transparent bars on a right Y-axis (ax.twinx())\n"
        "- Add ma5 as a dashed orange line (color='#ff7f0e', linewidth=1.5)\n"
        "- Add gridlines (alpha=0.3, linestyle='--')\n"
        "- Label left Y-axis 'Price (USD)', right Y-axis 'Volume (M)'\n"
        "- Add legend (loc='upper left', fontsize=9)\n"
        "- Use professional blue (#1f77b4) for close price\n"
        "- figsize=(12, 5)"
    )


def prompt_critique_2(ticker: str) -> str:
    return (
        f"You are re-evaluating an improved {ticker} stock chart for publication.\n\n"
        "1. Note what improved from the previous version.\n"
        "2. Identify 1-2 remaining gaps with ⚠️.\n"
        "3. Verdict — if still not publication-ready, state the remaining fix. "
        "Do NOT say FINISH yet.\n\n"
        "2-4 sentences. Plain text only."
    )

def prompt_iter3(ticker: str, prev_code: str, critique: str, df: pd.DataFrame) -> str:
    return (
        f"{CHART_CODE_SYSTEM}\n\n"
        f"Create a PROFESSIONAL, publication-ready {ticker} stock chart.\n\n"
        f"Previous code:\n{prev_code}\n\n"
        f"VLM critique:\n{critique}\n\n"
        "Make it publication-ready. Use ONLY these exact patterns — no other kwargs:\n"
        "- Setup: fig, ax1 = plt.subplots(figsize=(14, 6)); ax2 = ax1.twinx()\n"
        "- Background: ax1.set_facecolor('#f8f9fa')\n"
        "- High/Low band: ax1.fill_between(df['date_str'], df['low'], df['high'], alpha=0.06, color='gray', label='High/Low range')\n"
        "- Close area: ax1.fill_between(df['date_str'], df['close'].min(), df['close'], alpha=0.15, color='#2563eb')\n"
        "- Close line: ax1.plot(df['date_str'], df['close'], color='#2563eb', linewidth=2, label='Close Price')\n"
        "- MA5 line: ax1.plot(df['date_str'], df['ma5'], color='#f59e0b', linewidth=2, linestyle='--', label='MA5')\n"
        "- Volume bars: ax2.bar(df['date_str'], df['volume_m'], color='#94a3b8', alpha=0.3, label='Volume (M)')\n"
        "- Grid: ax1.grid(True, color='#e0e0e0', alpha=0.7, linestyle='--', linewidth=0.5)\n"
        f"- Title: ax1.set_title('{ticker} Weekly Price Analysis ({df['date_str'].iloc[0]} to {df['date_str'].iloc[-1]})', fontsize=14, fontweight='bold')\n"
        "- Axis labels: ax1.set_ylabel('Price (USD)', fontsize=11) and ax2.set_ylabel('Volume (M)', fontsize=11)\n"
        "- Legend (use exactly this pattern):\n"
        "    handles1, labels1 = ax1.get_legend_handles_labels()\n"
        "    handles2, labels2 = ax2.get_legend_handles_labels()\n"
        "    ax1.legend(handles1 + handles2, labels1 + labels2, loc='upper left', fontsize=9, framealpha=0.9)\n"
        "- Ticks: show only every 5th label to avoid crowding:\n"
        "    tick_positions = range(0, len(df), 5)\n"
        "    ax1.set_xticks(list(tick_positions))\n"
        "    ax1.set_xticklabels([df['date_str'].iloc[i] for i in tick_positions], rotation=30, fontsize=9)\n"        "IMPORTANT: fill_between does NOT accept fillalpha — use alpha only."
    )


def prompt_final_review(ticker: str) -> str:
    return (
        f"You are a top-tier visualization critic giving final sign-off on a "
        f"{ticker} stock chart for a professional research report.\n\n"
        "Evaluate: communication clarity, axis/legend completeness, "
        "color professionalism, layout balance.\n\n"
        "If it meets publication-grade standards output exactly: "
        "'✅ APPROVED — ' followed by one sentence why.\n"
        "If not output: '⚠️ NEEDS REVISION — ' and one specific fix.\n"
        "1-2 sentences only."
    )

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _print_box(label: str, text: str):
    width = 54
    print(f"\n  ┌─ {label} {'─' * max(0, width - len(label) - 1)}")
    for line in text.strip().splitlines():
        print(f"  │ {line}")
    print(f"  └{'─' * (width + 2)}\n")


def _prepare_mock_df() -> pd.DataFrame:
    df = pd.DataFrame(MOCK_DATA)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ma5"] = df["close"].rolling(window=5).mean().round(2)
    df["volume_m"] = (df["volume"] / 1_000_000).round(2)
    df["date_str"] = df["date"].dt.strftime("%b %d")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run(ticker: str, mock: bool = False, days: int = 90) -> dict:
    banner = "  FinSage — Iterative Vision-Enhanced Chart Generator  "
    div = "═" * len(banner)
    mode_label = "MOCK MODE (no API calls)" if mock else "REAL MODE (Cortex LLM + Cortex VLM)"
    print(f"\n{div}\n{banner}\n{div}")
    print(f"  Ticker: {ticker}  |  Mode: {mode_label}\n")

    # ── 1. Data ────────────────────────────────────────────────────────────────
    if mock:
        print("[ 1 / 7 ]  Loading mock AAPL data (hardcoded)...")
        df = _prepare_mock_df()
        session = None
    else:
        print("[ 1 / 7 ]  Fetching data from Snowflake...")
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from snowflake_connection import get_session
        df = fetch_snowflake_data(ticker, days)
        session = get_session()

    print(
        f"           {len(df)} rows | "
        f"{df['date_str'].iloc[0]} → {df['date_str'].iloc[-1]} | "
        f"Close ${df['close'].min():.2f}–${df['close'].max():.2f}"
    )

    # ── Run directory ──────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ticker}_{ts}{'_mock' if mock else ''}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "ticker": ticker,
        "mode": "mock" if mock else "real",
        "run_at": ts,
        "data_rows": len(df),
        "date_range": {
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end":   df["date"].max().strftime("%Y-%m-%d"),
        },
        "iterations": [],
    }

    # ── 2. Iteration 1 — Basic ─────────────────────────────────────────────────
    print("[ 2 / 7 ]  Iteration 1: Generating basic chart (LLM — Cortex llama3.1-70b)...")
    code1 = MOCK_CODE_ITER1 if mock else llm_complete(
        session, "llama3.1-70b", prompt_iter1(ticker, df)
    )
    path1 = str(run_dir / "iter1_basic.png")
    execute_chart_code(code1, df, path1)
    print(f"           ✓ Saved → iter1_basic.png")

    # ── 3. Critique 1 ─────────────────────────────────────────────────────────
    print("[ 3 / 7 ]  VLM Critique #1 (Cortex llama3.1-70b)...")
    critique1 = MOCK_CRITIQUE_1 if mock else vlm_critique(
        session, "llama3.1-70b", path1, prompt_critique_1(ticker)
    )
    _print_box("VLM Critique 1", critique1)
    results["iterations"].append({
        "label": "Iteration 1 — Basic",
        "chart": "iter1_basic.png",
        "critique": critique1,
    })

    # ── 4. Iteration 2 — Improved ─────────────────────────────────────────────
    print("[ 4 / 7 ]  Iteration 2: Improving chart based on critique (LLM — Cortex)...")
    code2 = MOCK_CODE_ITER2 if mock else llm_complete(
        session, "llama3.1-70b", prompt_iter2(ticker, code1, critique1)
    )
    path2 = str(run_dir / "iter2_improved.png")
    execute_chart_code(code2, df, path2)
    print(f"           ✓ Saved → iter2_improved.png")

    # ── 5. Critique 2 ─────────────────────────────────────────────────────────
    print("[ 5 / 7 ]  VLM Critique #2 (Cortex llama3.1-70b)...")
    critique2 = MOCK_CRITIQUE_2 if mock else vlm_critique(
        session, "llama3.1-70b", path2, prompt_critique_2(ticker)
    )
    _print_box("VLM Critique 2", critique2)
    results["iterations"].append({
        "label": "Iteration 2 — Improved",
        "chart": "iter2_improved.png",
        "critique": critique2,
    })

    # ── 6. Iteration 3 — Professional ─────────────────────────────────────────
    print("[ 6 / 7 ]  Iteration 3: Creating publication-ready chart (LLM — Cortex)...")
    code3 = llm_complete(
        session, "llama3.1-70b", prompt_iter3(ticker, code2, critique2, df)
    )
    path3 = str(run_dir / "iter3_professional.png")
    execute_chart_code(code3, df, path3)
    print(f"           ✓ Saved → iter3_professional.png")

    # ── 7. Final review ────────────────────────────────────────────────────────
    print("[ 7 / 7 ]  VLM Final Review (Cortex llama3.1-70b)...")
    final = MOCK_FINAL_REVIEW if mock else vlm_critique(
        session, "llama3.1-70b", path3, prompt_final_review(ticker)
    )
    _print_box("Final Review", final)
    results["iterations"].append({
        "label": "Iteration 3 — Professional",
        "chart": "iter3_professional.png",
        "critique": final,
    })

    # ── Cleanup ────────────────────────────────────────────────────────────────
    if session:
        session.close()

    # ── Summary JSON ───────────────────────────────────────────────────────────
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    # ── Final banner ───────────────────────────────────────────────────────────
    print(f"\n{div}")
    print(f"  ✅  Complete!")
    print(f"  Output: {run_dir}")
    print(f"    iter1_basic.png          <- intentionally basic")
    print(f"    iter2_improved.png       <- partially improved")
    print(f"    iter3_professional.png   <- publication-ready")
    print(f"    summary.json             <- all critiques + metadata")
    if mock:
        print(f"\n  This was MOCK MODE — re-run without --mock once")
        print(f"  Snowflake connection is confirmed working.")
    print(f"{div}\n")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FinSage Iterative Vision-Enhanced Chart Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              # No dependencies needed — run right now
              python POCs/Iterative_Chart_Generation.py --mock

              # Real mode — needs working Snowflake connection
              python POCs/Iterative_Chart_Generation.py --ticker AAPL
              python POCs/Iterative_Chart_Generation.py --ticker TSLA --days 60

            Available tickers: AAPL, TSLA, MSFT
        """),
    )
    parser.add_argument(
        "--ticker", default="AAPL",
        help="Stock ticker symbol (default: AAPL)"
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="Trading days to fetch from Snowflake (default: 90, real mode only)"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Run with hardcoded data and mock responses — no API calls"
    )
    args = parser.parse_args()

    run(args.ticker.upper(), mock=args.mock, days=args.days)