"""
FinSage — Iterative Vision-Enhanced Chart Generator
====================================================
Implements FinSight paper Section 2.4:
    LLM generates matplotlib code → chart rendered → VLM critiques image
    → LLM refines → repeat × 3 → professional-quality output

Usage:
    # Works RIGHT NOW — no Snowflake, no API keys needed
    python POCs/iterative_chart_demo.py --mock

    # Once Snowflake + Cortex connection is fixed
    python POCs/iterative_chart_demo.py --ticker AAPL

Install:
    .venv\\Scripts\\pip install matplotlib snowflake-ml-python
"""

import argparse
import os
import subprocess
import sys
import tempfile
import textwrap
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# ── Output directory ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "iterative_charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# MOCK DATA — Hardcoded AAPL data, mirrors the demo artifact exactly
# Used when --mock flag is passed. No Snowflake or API needed.
# ══════════════════════════════════════════════════════════════════════════════

MOCK_DATA = [
    {"date": "2025-01-06", "close": 243.36, "volume": 40500000, "high": 247.10, "low": 240.80},
    {"date": "2025-01-13", "close": 248.13, "volume": 38200000, "high": 250.40, "low": 245.60},
    {"date": "2025-01-21", "close": 241.84, "volume": 55100000, "high": 249.20, "low": 239.50},
    {"date": "2025-01-27", "close": 249.72, "volume": 45800000, "high": 252.00, "low": 247.30},
    {"date": "2025-02-03", "close": 253.20, "volume": 41300000, "high": 255.80, "low": 251.10},
    {"date": "2025-02-10", "close": 247.88, "volume": 48700000, "high": 254.20, "low": 245.90},
    {"date": "2025-02-18", "close": 255.64, "volume": 53200000, "high": 258.10, "low": 253.40},
    {"date": "2025-02-24", "close": 252.12, "volume": 39600000, "high": 256.30, "low": 250.80},
    {"date": "2025-03-03", "close": 259.45, "volume": 50100000, "high": 261.80, "low": 256.20},
    {"date": "2025-03-10", "close": 262.18, "volume": 55400000, "high": 264.50, "low": 259.30},
]

# ── Mock LLM/VLM responses ─────────────────────────────────────────────────────
# These simulate what Cortex would return. Realistic enough to show the concept.

MOCK_CODE_ITER1 = '''
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(df["date_str"], df["close"], color="#8884d8")
ax.set_title("AAPL Stock Price")
'''

MOCK_CRITIQUE_1 = """❌ Information density is very low — only close price is shown, but volume and moving averages are available and standard in equity charts.
❌ Axis labels are missing entirely — no units, no axis titles, making the chart unreadable in a report context.
❌ No legend or gridlines — impossible to read precise values or identify the series.
❌ Color choice (#8884d8) is non-standard for financial charts — professional charts use blue or black for price."""

MOCK_CODE_ITER2 = '''
fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()
ax1.plot(df["date_str"], df["close"], color="#1f77b4", linewidth=2, label="Close Price")
ax1.plot(df["date_str"], df["ma5"], color="#ff7f0e", linewidth=1.5, linestyle="--", label="MA5")
ax2.bar(df["date_str"], df["volume_m"], color="#94a3b8", alpha=0.3, label="Volume (M)")
ax1.set_ylabel("Price (USD)")
ax2.set_ylabel("Volume (M)")
ax1.set_title("AAPL Stock Price with Volume and MA5")
ax1.grid(True, alpha=0.3, linestyle="--")
ax1.legend(loc="upper left", fontsize=9)
plt.xticks(rotation=45)
'''

MOCK_CRITIQUE_2 = """⚠️ Clear improvements: volume and MA5 added, axes are now labeled. The chart reads much better than the first iteration.
⚠️ High/Low range is still absent — a shaded band between high and low is standard in equity research charts and adds context about daily price spread."""

MOCK_CODE_ITER3 = '''
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.set_facecolor("#f8f9fa")
fig.patch.set_facecolor("white")
ax2 = ax1.twinx()

# High/Low shaded band
ax1.fill_between(df["date_str"], df["low"], df["high"],
                 alpha=0.06, color="gray", label="High/Low range")

# Close as filled area
ax1.fill_between(df["date_str"], df["close"].min(), df["close"],
                 alpha=0.15, color="#2563eb")
ax1.plot(df["date_str"], df["close"], color="#2563eb",
         linewidth=2, label="Close Price")

# MA5 dashed
ax1.plot(df["date_str"], df["ma5"], color="#f59e0b",
         linewidth=2, linestyle=(0, (5, 3)), label="MA5")

# Volume bars
ax2.bar(df["date_str"], df["volume_m"], color="#94a3b8", alpha=0.3, label="Volume (M)")

ax1.set_ylabel("Price (USD)", fontsize=11)
ax2.set_ylabel("Volume (M)", fontsize=11)
ax1.set_title("AAPL Weekly Price Analysis — Jan to Mar 2025",
              fontsize=14, fontweight="bold")
ax1.grid(True, color="#e0e0e0", alpha=0.7, linestyle="--", linewidth=0.5)

# Combined legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2,
           loc="upper left", fontsize=9, framealpha=0.9)

plt.xticks(rotation=30, fontsize=9)
plt.tight_layout()
'''

MOCK_FINAL_REVIEW = "✅ APPROVED — Chart meets professional equity research standards with clear price, volume, and trend indicators, proper labeling, and publication-quality styling."


# ══════════════════════════════════════════════════════════════════════════════
# REAL MODE — Snowflake data fetch + Cortex LLM/VLM
# Only used when --mock is NOT passed
# ══════════════════════════════════════════════════════════════════════════════

def fetch_snowflake_data(ticker: str, days: int = 90) -> pd.DataFrame:
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


def cortex_complete(session, model: str, prompt: str) -> str:
    from snowflake.cortex import Complete
    return Complete(model, prompt, session=session)


def cortex_vision(session, model: str, image_path: str, prompt: str) -> str:
    """
    Cortex multimodal call — passes rendered chart image to pixtral-large.
    This is the VLM critique step from FinSight Section 2.4.
    """
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    # Cortex multimodal via Snowpark SQL
    sql = f"""
        SELECT SNOWFLAKE.CORTEX.COMPLETE(
            '{model}',
            [{{
                'role': 'user',
                'content': [
                    {{'type': 'image_url', 'image_url': {{'url': 'data:image/png;base64,{b64}'}}}},
                    {{'type': 'text', 'text': '{prompt.replace("'", "''")}'}}
                ]
            }}]
        ) AS result
    """
    result = session.sql(sql).collect()[0][0]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CHART CODE EXECUTOR
# Runs LLM-generated matplotlib code safely in a subprocess
# ══════════════════════════════════════════════════════════════════════════════

def execute_chart_code(code: str, df: pd.DataFrame, output_path: str):
    """
    Writes df to a temp CSV, wraps LLM code in a runner script,
    executes in a subprocess, saves the chart to output_path.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                     delete=False, encoding="utf-8") as f:
        df.to_csv(f, index=False)
        csv_path = f.name

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
print("SAVED:" + r"{output_path}")
""")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write(runner)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Chart render failed:\n{result.stderr[-1500:]}"
            )
    finally:
        os.unlink(script_path)
        os.unlink(csv_path)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS — Real Cortex mode only
# ══════════════════════════════════════════════════════════════════════════════

CHART_CODE_SYSTEM = (
    "Return ONLY executable Python matplotlib code — no markdown, no explanations. "
    "Already available: pandas as pd, matplotlib.pyplot as plt, numpy as np, "
    "df (DataFrame with columns: date, open, high, low, close, volume, ma5, volume_m, date_str). "
    "Do NOT redefine df. Do NOT call plt.show() or plt.savefig()."
)

def prompt_iter1(ticker, df):
    return (
        f"Generate a BASIC minimal matplotlib chart for {ticker}. "
        f"Data: {len(df)} rows, close range ${df['close'].min():.2f}–${df['close'].max():.2f}. "
        "Single close price line only, no grid, no legend, no axis labels. "
        f'Title: "{ticker} Stock Price". figsize=(12,5). Use date_str on x-axis, rotate 45 degrees.'
    )

def prompt_critique_1(ticker):
    return (
        f"You are a VLM critiquing a {ticker} stock chart for an equity research report. "
        "List exactly 3-4 issues starting with ❌. Cover: information density, label clarity, "
        "visual quality, missing elements. 3-5 sentences total. Plain text only."
    )

def prompt_iter2(ticker, prev_code, critique):
    return (
        f"Improve this {ticker} chart. Previous code:\n{prev_code}\n\n"
        f"VLM critique:\n{critique}\n\n"
        "Add: volume_m bars on right axis (ax.twinx()), ma5 as dashed orange line, "
        "gridlines (alpha=0.3), axis labels 'Price (USD)' and 'Volume (M)', legend. "
        "Professional blue (#1f77b4) for close. figsize=(12,5)."
    )

def prompt_critique_2(ticker):
    return (
        f"Re-evaluate this improved {ticker} chart. Note 1-2 improvements, "
        "then list 1-2 remaining gaps with ⚠️ for publication readiness. "
        "2-4 sentences. Plain text only."
    )

def prompt_iter3(ticker, prev_code, critique):
    return (
        f"Create a PROFESSIONAL publication-ready {ticker} chart. Previous:\n{prev_code}\n\n"
        f"Critique:\n{critique}\n\n"
        "Requirements: close as filled area (#2563eb, alpha=0.15), ma5 dashed amber (#f59e0b), "
        "high/low shaded band (alpha=0.06 gray), volume bars (#94a3b8 alpha=0.3) on right axis, "
        "ax.set_facecolor('#f8f9fa'), gridlines (#e0e0e0), fontsize title=14 bold, labels=11, ticks=9, "
        "combined legend upper left, rotate x-ticks 30deg. figsize=(14,6)."
    )

def prompt_final_review(ticker):
    return (
        f"You are a senior equity analyst approving a {ticker} chart for client publication. "
        "If it meets professional standards start with '✅ APPROVED —' then one sentence why. "
        "If not start with '⚠️ NEEDS REVISION —' and one specific fix. 1-2 sentences only."
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run(ticker: str, mock: bool = False, days: int = 90):
    banner = f"  FinSage — Iterative Vision-Enhanced Chart Generator  "
    div = "═" * len(banner)
    mode_label = "MOCK MODE (no API calls)" if mock else "REAL MODE (Cortex AI)"
    print(f"\n{div}\n{banner}\n{div}")
    print(f"  Ticker: {ticker}  |  Mode: {mode_label}\n")

    # ── Data ───────────────────────────────────────────────────────────────────
    if mock:
        print("[ 1 / 7 ]  Loading mock AAPL data (hardcoded)...")
        df = pd.DataFrame(MOCK_DATA)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["ma5"] = df["close"].rolling(window=5).mean().round(2)
        df["volume_m"] = (df["volume"] / 1_000_000).round(2)
        df["date_str"] = df["date"].dt.strftime("%b %d")
        session = None
    else:
        print("[ 1 / 7 ]  Fetching data from Snowflake...")
        df = fetch_snowflake_data(ticker, days)
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from snowflake_connection import get_session
        session = get_session()

    print(f"           {len(df)} rows | "
          f"{df['date_str'].iloc[0]} → {df['date_str'].iloc[-1]} | "
          f"Close ${df['close'].min():.2f}–${df['close'].max():.2f}")

    # ── Run directory ──────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ticker}_{ts}{'_mock' if mock else ''}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "ticker": ticker,
        "mode": "mock" if mock else "real",
        "run_at": ts,
        "data_rows": len(df),
        "iterations": [],
    }

    # ── Iteration 1 ───────────────────────────────────────────────────────────
    print("[ 2 / 7 ]  Iteration 1: Generating basic chart (LLM)...")
    if mock:
        code1 = MOCK_CODE_ITER1
    else:
        code1 = cortex_complete(
            session, "llama3.1-70b",
            f"{CHART_CODE_SYSTEM}\n\n{prompt_iter1(ticker, df)}"
        )
    path1 = str(run_dir / "iter1_basic.png")
    execute_chart_code(code1, df, path1)
    print(f"           ✓ Saved → iter1_basic.png")

    # ── Critique 1 ────────────────────────────────────────────────────────────
    print("[ 3 / 7 ]  VLM Critique #1 (pixtral-large reviewing rendered image)...")
    if mock:
        critique1 = MOCK_CRITIQUE_1
    else:
        critique1 = cortex_vision(session, "pixtral-large", path1,
                                  prompt_critique_1(ticker))
    _print_box("VLM Critique 1", critique1)
    results["iterations"].append({
        "label": "Iteration 1 — Basic",
        "chart": "iter1_basic.png",
        "critique": critique1,
    })

    # ── Iteration 2 ───────────────────────────────────────────────────────────
    print("[ 4 / 7 ]  Iteration 2: Improving chart based on critique (LLM)...")
    if mock:
        code2 = MOCK_CODE_ITER2
    else:
        code2 = cortex_complete(
            session, "llama3.1-70b",
            f"{CHART_CODE_SYSTEM}\n\n{prompt_iter2(ticker, code1, critique1)}"
        )
    path2 = str(run_dir / "iter2_improved.png")
    execute_chart_code(code2, df, path2)
    print(f"           ✓ Saved → iter2_improved.png")

    # ── Critique 2 ────────────────────────────────────────────────────────────
    print("[ 5 / 7 ]  VLM Critique #2...")
    if mock:
        critique2 = MOCK_CRITIQUE_2
    else:
        critique2 = cortex_vision(session, "pixtral-large", path2,
                                  prompt_critique_2(ticker))
    _print_box("VLM Critique 2", critique2)
    results["iterations"].append({
        "label": "Iteration 2 — Improved",
        "chart": "iter2_improved.png",
        "critique": critique2,
    })

    # ── Iteration 3 ───────────────────────────────────────────────────────────
    print("[ 6 / 7 ]  Iteration 3: Creating publication-ready chart (LLM)...")
    if mock:
        code3 = MOCK_CODE_ITER3
    else:
        code3 = cortex_complete(
            session, "llama3.1-70b",
            f"{CHART_CODE_SYSTEM}\n\n{prompt_iter3(ticker, code2, critique2)}"
        )
    path3 = str(run_dir / "iter3_professional.png")
    execute_chart_code(code3, df, path3)
    print(f"           ✓ Saved → iter3_professional.png")

    # ── Final review ──────────────────────────────────────────────────────────
    print("[ 7 / 7 ]  VLM Final Review...")
    if mock:
        final = MOCK_FINAL_REVIEW
    else:
        final = cortex_vision(session, "pixtral-large", path3,
                              prompt_final_review(ticker))
    _print_box("Final Review", final)
    results["iterations"].append({
        "label": "Iteration 3 — Professional",
        "chart": "iter3_professional.png",
        "critique": final,
    })

    # ── Cleanup ───────────────────────────────────────────────────────────────
    if session:
        session.close()

    # ── Summary JSON ──────────────────────────────────────────────────────────
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    # ── Final banner ──────────────────────────────────────────────────────────
    print(f"\n{div}")
    print(f"  ✅  Complete!")
    print(f"  Output folder: {run_dir}")
    print(f"    iter1_basic.png          ← intentionally basic")
    print(f"    iter2_improved.png       ← partially improved")
    print(f"    iter3_professional.png   ← publication-ready")
    print(f"    summary.json             ← all critiques + metadata")
    if mock:
        print(f"\n  This was MOCK MODE — re-run without --mock once")
        print(f"  Snowflake connection is working to use real Cortex AI")
    print(div + "\n")

    return results


def _print_box(label: str, text: str):
    print(f"\n  ┌─ {label} {'─' * max(0, 50 - len(label))}")
    for line in text.strip().splitlines():
        print(f"  │ {line}")
    print(f"  └{'─' * 54}\n")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FinSage Iterative Vision-Enhanced Chart Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              # Test right now — no Snowflake or API needed
              python POCs/iterative_chart_demo.py --mock

              # Real mode — needs working Snowflake + Cortex
              python POCs/iterative_chart_demo.py --ticker AAPL
              python POCs/iterative_chart_demo.py --ticker TSLA --days 60
        """),
    )
    parser.add_argument("--ticker", default="AAPL",
                        help="Stock ticker (default: AAPL)")
    parser.add_argument("--days", type=int, default=90,
                        help="Trading days to fetch (default: 90, real mode only)")
    parser.add_argument("--mock", action="store_true",
                        help="Run with hardcoded data and mock responses (no API calls)")
    args = parser.parse_args()

    run(args.ticker.upper(), mock=args.mock, days=args.days)