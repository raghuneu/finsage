#!/usr/bin/env python3
"""
FinSage — Iterative Vision-Enhanced Chart Generator
====================================================
Implements FinSight paper Section 2.4:
    LLM generates matplotlib code → chart rendered → VLM critiques image
    → LLM refines → repeat × 3 → professional-quality output

Person 2 task (CAVM / iterative vision component)

Usage:
    python scripts/iterative_chart_generator.py
    python scripts/iterative_chart_generator.py --ticker TSLA
    python scripts/iterative_chart_generator.py --ticker MSFT --days 60

Requirements (add to venv):
    pip install matplotlib anthropic
    Add ANTHROPIC_API_KEY=sk-ant-... to your .env file
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "ANTHROPIC_API_KEY not found in .env\n"
        "Add this line to your .env file:\n"
        "  ANTHROPIC_API_KEY=sk-ant-..."
    )

# ── Output directory ───────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "iterative_charts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# ANTHROPIC API HELPERS
# Two functions — one for text (LLM role), one for vision (VLM role)
# ══════════════════════════════════════════════════════════════════════════════

def claude_text(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """
    LLM role: generates chart code or improved versions.
    Plain text input → text output.
    """
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def claude_vision(image_path: str, prompt: str) -> str:
    """
    VLM role: looks at the rendered chart image and critiques it.
    Image + text → text critique.
    This is what Qwen2.5-VL-72B does in the original FinSight paper.
    We use Claude's vision capability here instead.
    """
    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 800,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


# ══════════════════════════════════════════════════════════════════════════════
# SNOWFLAKE DATA FETCH
# ══════════════════════════════════════════════════════════════════════════════

def fetch_stock_data(ticker: str, days: int = 90) -> pd.DataFrame:
    """
    Pull OHLCV data from FINSAGE_DB.STAGING.STG_STOCK_PRICES.
    Computes MA5 and volume_m (volume in millions) for chart use.
    """
    # Add scripts/ to path so we can import the shared connection module
    scripts_dir = PROJECT_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from snowflake_connection import get_session  # noqa: E402

    session = get_session()
    try:
        query = f"""
            SELECT
                DATE,
                OPEN,
                HIGH,
                LOW,
                CLOSE,
                VOLUME
            FROM FINSAGE_DB.STAGING.STG_STOCK_PRICES
            WHERE TICKER = '{ticker.upper()}'
            ORDER BY DATE DESC
            LIMIT {days}
        """
        df = session.sql(query).to_pandas()
    finally:
        session.close()

    # Normalise columns
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Derived columns the LLM can reference
    df["ma5"] = df["close"].rolling(window=5).mean().round(2)
    df["volume_m"] = (df["volume"] / 1_000_000).round(2)
    df["date_str"] = df["date"].dt.strftime("%b %d")

    print(f"  ✓ Fetched {len(df)} rows for {ticker} from Snowflake "
          f"({df['date'].min().date()} → {df['date'].max().date()})")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CHART CODE EXECUTOR
# Runs LLM-generated matplotlib code safely in a subprocess.
# The code receives `df` via a temp CSV and saves to a known output path.
# ══════════════════════════════════════════════════════════════════════════════

def execute_chart_code(llm_code: str, df: pd.DataFrame, output_path: str) -> str:
    """
    Execute matplotlib code produced by the LLM.

    Strategy:
    - Write df to a temp CSV (subprocess can't share in-memory objects)
    - Wrap the LLM code in a runner that pre-imports libraries and saves the figure
    - Run in subprocess with 30s timeout
    - Return the output path on success, raise on failure
    """
    # Write data to temp CSV
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f, index=False)
        csv_path = f.name

    # Runner template — safe preamble + LLM code + save
    runner_code = textwrap.dedent(f"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # Non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# Data is pre-loaded — the LLM code should NOT redefine df
df = pd.read_csv("{csv_path}")
df["date"] = pd.to_datetime(df["date"])

# The LLM code saves to this path via plt.savefig() OR
# the runner below saves after the LLM code runs
OUTPUT_PATH = "{output_path}"

# ── LLM-generated chart code ──────────────────────────────────────────────────
{llm_code}
# ─────────────────────────────────────────────────────────────────────────────

# Save whatever figure is currently active
try:
    plt.tight_layout()
except Exception:
    pass
plt.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight", facecolor="white")
plt.close("all")
print("CHART_SAVED:" + OUTPUT_PATH)
""")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(runner_code)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Surface the actual matplotlib error to help debugging
            raise RuntimeError(
                f"Chart code execution failed (exit {result.returncode}):\n"
                f"{result.stderr[-1500:]}"   # Last 1500 chars of stderr
            )
        return output_path
    finally:
        # Always clean up temp files
        os.unlink(script_path)
        os.unlink(csv_path)


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# Each prompt corresponds to one step in the FinSight Section 2.4 loop.
# System prompt constrains the LLM to return only executable Python code.
# ══════════════════════════════════════════════════════════════════════════════

CHART_CODE_SYSTEM = """You are a financial data visualization expert.
Return ONLY executable Python matplotlib code — no markdown fences, no explanations, no comments.
The following are already imported and available:
  - pandas as pd
  - matplotlib.pyplot as plt
  - matplotlib.ticker as mticker
  - matplotlib.dates as mdates
  - numpy as np
  - df (pandas DataFrame with columns: date, open, high, low, close, volume, ma5, volume_m, date_str)
Do NOT import these again. Do NOT define df. Do NOT call plt.show() or plt.savefig().
Create the figure using plt.figure() or plt.subplots()."""


def _data_summary(ticker: str, df: pd.DataFrame) -> str:
    """Brief data snapshot to orient the LLM."""
    return (
        f"Ticker: {ticker} | Rows: {len(df)} | "
        f"Date range: {df['date_str'].iloc[0]} to {df['date_str'].iloc[-1]}\n"
        f"Close range: ${df['close'].min():.2f} – ${df['close'].max():.2f} | "
        f"Avg volume: {df['volume_m'].mean():.1f}M shares\n"
        f"Sample (last 5 rows):\n"
        f"{df[['date_str','close','volume_m','ma5','high','low']].tail(5).to_string(index=False)}"
    )


def prompt_iter1(ticker: str, df: pd.DataFrame) -> str:
    return f"""Generate a BASIC, intentionally minimal matplotlib chart for {ticker} stock.

{_data_summary(ticker, df)}

Requirements — keep this simple on purpose (it will be improved in later iterations):
- Single line chart of close price only (use date_str on x-axis, rotate 45 degrees)
- No gridlines, no legend, no axis labels
- Default matplotlib blue line, no custom styling
- Title: "{ticker} Stock Price"
- Figure size: (12, 5)"""


def prompt_critique_1(ticker: str) -> str:
    return f"""You are a VLM (Vision-Language Model) acting as a financial chart quality reviewer.

Critique this {ticker} stock chart as if reviewing it for a professional equity research report.

Evaluate these four dimensions:
1. Information density — what key financial data is missing?
2. Label clarity — are axes, units, and series properly labeled?
3. Visual quality — is the styling appropriate for a professional report?
4. Missing standard elements — what do equity research charts normally include?

List exactly 3-4 specific, actionable issues. Start each with "❌".
Total response: 3-5 sentences. Plain text only."""


def prompt_iter2(ticker: str, prev_code: str, critique: str) -> str:
    return f"""Improve this {ticker} chart based on the VLM critique below.

Previous chart code:
{prev_code}

VLM Critique:
{critique}

Apply these specific improvements:
- Add volume_m as semi-transparent gray bars on a secondary Y-axis (right side, label "Volume (M)")
- Add ma5 as a dashed orange line (color="#ff7f0e", linewidth=1.5, label="MA5")
- Add gridlines (alpha=0.3, linestyle="--")
- Label the left Y-axis "Price (USD)"
- Add a legend (loc="upper left", fontsize=9)
- Use a professional blue for close price: color="#1f77b4"
- Keep figure size (12, 5), use ax.twinx() for the second axis"""


def prompt_critique_2(ticker: str) -> str:
    return f"""You are a VLM re-evaluating an improved {ticker} stock chart.

First, briefly acknowledge 1-2 clear improvements from the previous version.
Then identify 1-2 remaining gaps with "⚠️" — focus specifically on what would make
this chart publication-ready for a professional equity research report.

Total response: 2-4 sentences. Plain text only."""


def prompt_iter3(ticker: str, prev_code: str, critique: str) -> str:
    return f"""Create a PROFESSIONAL, publication-ready {ticker} stock chart.

Previous chart code:
{prev_code}

VLM Critique:
{critique}

Make it publication-ready. Apply all of these:
- Close price as a filled area (color="#2563eb", alpha=0.15 fill, linewidth=2)
- MA5 as a dashed amber line (color="#f59e0b", linewidth=2, dashes=(5,3))
- High/Low as a very subtle shaded band: ax.fill_between(df["date"], df["low"], df["high"], alpha=0.06, color="gray", label="High/Low range")
- Volume bars on right axis: color="#94a3b8", alpha=0.3
- Set ax.set_facecolor("#f8f9fa") and figure facecolor "white"
- Gridlines: color="#e0e0e0", alpha=0.7, linestyle="--", linewidth=0.5
- Font sizes: title=14 (fontweight="bold"), axis labels=11, tick labels=9
- Add a small text annotation in the upper-right of the price axis showing the date range
- Legend: loc="upper left", fontsize=9, framealpha=0.9
- Rotate x-axis labels 30 degrees, show only every 10th date label to avoid crowding
- Figure size (14, 6) for more breathing room"""


def prompt_final_review(ticker: str) -> str:
    return f"""You are a senior equity research analyst giving final sign-off on a {ticker} chart for client publication.

Review this chart against professional equity research report standards:
- Does it show price, volume, and a trend indicator (MA)?
- Are all axes, labels, and the legend clear and properly formatted?
- Is the visual quality appropriate for a professional PDF report?

If it meets the standard, start with: "✅ APPROVED —" followed by one sentence summarizing why.
If it still needs work, start with: "⚠️ NEEDS REVISION —" and state one specific fix.

Total response: 1-2 sentences. Plain text only."""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# Runs the full 3-iteration loop and saves all outputs.
# ══════════════════════════════════════════════════════════════════════════════

def run(ticker: str, days: int = 90) -> dict:
    banner = f"  FinSage — Iterative Vision-Enhanced Chart Generator  "
    print(f"\n{'═' * len(banner)}")
    print(banner)
    print(f"{'═' * len(banner)}")
    print(f"  Ticker: {ticker}  |  Days: {days}  |  Output: {OUTPUT_DIR}\n")

    # ── 1. Fetch data ──────────────────────────────────────────────────────────
    print("[ 1 / 7 ]  Fetching data from Snowflake...")
    df = fetch_stock_data(ticker, days)

    # Create a timestamped run directory so runs don't overwrite each other
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{ticker}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "ticker": ticker,
        "run_at": ts,
        "data_rows": len(df),
        "date_range": {
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end":   df["date"].max().strftime("%Y-%m-%d"),
        },
        "iterations": [],
    }

    # ── 2. Iteration 1 — Basic ─────────────────────────────────────────────────
    print("[ 2 / 7 ]  Iteration 1: Generating basic chart (LLM)...")
    code1 = claude_text(prompt_iter1(ticker, df), system=CHART_CODE_SYSTEM)
    path1 = str(run_dir / "iter1_basic.png")
    execute_chart_code(code1, df, path1)
    print(f"           Chart saved → iter1_basic.png")

    # ── 3. Critique 1 — VLM looks at the actual rendered image ────────────────
    print("[ 3 / 7 ]  VLM Critique #1 (Claude Vision reviewing rendered chart)...")
    critique1 = claude_vision(path1, prompt_critique_1(ticker))
    print(f"\n  ┌─ VLM Critique 1 ────────────────────────────────────────")
    for line in critique1.strip().splitlines():
        print(f"  │ {line}")
    print(f"  └─────────────────────────────────────────────────────────\n")

    results["iterations"].append({
        "label": "Iteration 1 — Basic",
        "chart_file": path1,
        "critique": critique1,
    })

    # ── 4. Iteration 2 — Improved ─────────────────────────────────────────────
    print("[ 4 / 7 ]  Iteration 2: Improving chart based on critique (LLM)...")
    code2 = claude_text(prompt_iter2(ticker, code1, critique1), system=CHART_CODE_SYSTEM)
    path2 = str(run_dir / "iter2_improved.png")
    execute_chart_code(code2, df, path2)
    print(f"           Chart saved → iter2_improved.png")

    # ── 5. Critique 2 ─────────────────────────────────────────────────────────
    print("[ 5 / 7 ]  VLM Critique #2 (Claude Vision)...")
    critique2 = claude_vision(path2, prompt_critique_2(ticker))
    print(f"\n  ┌─ VLM Critique 2 ────────────────────────────────────────")
    for line in critique2.strip().splitlines():
        print(f"  │ {line}")
    print(f"  └─────────────────────────────────────────────────────────\n")

    results["iterations"].append({
        "label": "Iteration 2 — Improved",
        "chart_file": path2,
        "critique": critique2,
    })

    # ── 6. Iteration 3 — Professional ─────────────────────────────────────────
    print("[ 6 / 7 ]  Iteration 3: Creating publication-ready chart (LLM)...")
    code3 = claude_text(prompt_iter3(ticker, code2, critique2), system=CHART_CODE_SYSTEM)
    path3 = str(run_dir / "iter3_professional.png")
    execute_chart_code(code3, df, path3)
    print(f"           Chart saved → iter3_professional.png")

    # ── 7. Final review ────────────────────────────────────────────────────────
    print("[ 7 / 7 ]  VLM Final Review (Claude Vision)...")
    final_review = claude_vision(path3, prompt_final_review(ticker))
    print(f"\n  ┌─ Final Review ───────────────────────────────────────────")
    for line in final_review.strip().splitlines():
        print(f"  │ {line}")
    print(f"  └─────────────────────────────────────────────────────────\n")

    results["iterations"].append({
        "label": "Iteration 3 — Professional",
        "chart_file": path3,
        "critique": final_review,
    })

    # ── Save summary JSON ──────────────────────────────────────────────────────
    summary_path = run_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    # ── Print final summary ────────────────────────────────────────────────────
    print(f"{'═' * len(banner)}")
    print(f"  ✅  Complete!  Run directory: {run_dir}")
    print(f"      iter1_basic.png          ← intentionally bad")
    print(f"      iter2_improved.png       ← partially improved")
    print(f"      iter3_professional.png   ← publication-ready")
    print(f"      summary.json             ← all critiques + metadata")
    print(f"{'═' * len(banner)}\n")

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
              python scripts/iterative_chart_generator.py
              python scripts/iterative_chart_generator.py --ticker TSLA
              python scripts/iterative_chart_generator.py --ticker MSFT --days 60

            Available tickers in your Snowflake DB: AAPL, TSLA, MSFT
        """),
    )
    parser.add_argument(
        "--ticker",
        default="AAPL",
        help="Stock ticker symbol (default: AAPL)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of trading days to fetch (default: 90)",
    )
    args = parser.parse_args()

    run(args.ticker.upper(), args.days)