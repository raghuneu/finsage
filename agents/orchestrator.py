"""
FinSage Orchestrator
====================
Single entry point for the full CAVM pipeline.

Flow:
    1. chart_agent     → generate 6 charts (3-iteration VLM refinement)
    2. validation_agent → validate all charts
    3. analysis_agent  → Cortex analysis per chart + SEC summarization
    4. report_agent    → assemble branded PDF

Usage:
    python agents/orchestrator.py --ticker AAPL
    python agents/orchestrator.py --ticker AAPL --debug
    python agents/orchestrator.py --ticker AAPL --skip-charts --charts-dir outputs/AAPL_20260403_154219
"""

import os
import re
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Path setup — works when called from project root or agents/
# Path setup — works when called from project root or agents/
PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from snowflake_connection import get_session
from chart_agent import generate_charts
from validation_agent import validate_all_charts
from analysis_agent import run_analysis
from report_agent import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Known company names for cover page
COMPANY_NAMES = {
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corporation",
    "TSLA":  "Tesla Inc.",
    "GOOGL": "Alphabet Inc.",
    "JPM":   "JPMorgan Chase & Co.",
    "AMZN":  "Amazon.com Inc.",
    "NVDA":  "NVIDIA Corporation",
    "META":  "Meta Platforms Inc.",
    "BAC":   "Bank of America Corp.",
    "GS":    "Goldman Sachs Group Inc.",
}


# ──────────────────────────────────────────────────────────────
# Pipeline stages
# ──────────────────────────────────────────────────────────────

def stage_charts(session, ticker: str, output_dir: str,
                 debug: bool = False) -> list:
    """Stage 1 — Generate charts via chart_agent."""
    logger.info("━" * 50)
    logger.info("STAGE 1: Chart Generation")
    logger.info("━" * 50)
    charts = generate_charts(session, ticker, output_dir=output_dir, debug=debug)
    logger.info("Stage 1 complete: %d charts generated", len(charts))
    return charts


def stage_validation(session, charts: list) -> list:
    """Stage 2 — Validate charts via validation_agent."""
    logger.info("━" * 50)
    logger.info("STAGE 2: Chart Validation")
    logger.info("━" * 50)
    validated = validate_all_charts(session, charts)
    passed = sum(1 for c in validated if c["validated"])
    logger.info("Stage 2 complete: %d/%d charts passed validation",
                passed, len(validated))
    return validated


def stage_analysis(session, charts: list, ticker: str) -> dict:
    """Stage 3 — Generate analysis via analysis_agent."""
    logger.info("━" * 50)
    logger.info("STAGE 3: LLM Analysis")
    logger.info("━" * 50)
    analysis = run_analysis(session, charts, ticker)
    logger.info("Stage 3 complete: %d chart analyses + SEC summaries",
                len(analysis.get("chart_analyses", [])))
    return analysis


def stage_report(ticker: str, charts: list, analysis: dict,
                 output_dir: str) -> str:
    """Stage 4 — Build PDF via report_agent."""
    logger.info("━" * 50)
    logger.info("STAGE 4: PDF Report Generation")
    logger.info("━" * 50)
    company_name = COMPANY_NAMES.get(ticker.upper(), ticker)
    pdf_path = generate_report(
        ticker=ticker,
        charts=charts,
        analysis=analysis,
        output_dir=output_dir,
        company_name=company_name,
    )
    logger.info("Stage 4 complete: %s", pdf_path)
    return pdf_path


# ──────────────────────────────────────────────────────────────
# Chart loader (for --skip-charts mode)
# ──────────────────────────────────────────────────────────────

def load_existing_charts(charts_dir: str) -> list:
    """
    Load charts from a previous chart_agent run.
    Reads chart_manifest.json and re-attaches file paths.
    """
    manifest_path = os.path.join(charts_dir, "chart_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"No chart_manifest.json found in {charts_dir}. "
            f"Run without --skip-charts first."
        )

    with open(manifest_path) as f:
        charts = json.load(f)

    # Re-attach file paths
    for chart in charts:
        chart["file_path"] = os.path.join(charts_dir, f"{chart['chart_id']}.png")

    logger.info("Loaded %d charts from %s", len(charts), charts_dir)
    return charts


def find_latest_charts_dir(ticker: str) -> str:
    """Find the most recent chart output folder for a ticker."""
    folders = sorted(
        [
            f for f in OUTPUT_DIR.glob(f"{ticker.upper()}_*")
            if (f / "chart_manifest.json").exists()
        ],
        reverse=True
    )
    if not folders:
        raise FileNotFoundError(
            f"No chart output found for {ticker}. "
            f"Run without --skip-charts first."
        )
    return str(folders[0])


# ──────────────────────────────────────────────────────────────
# Pipeline result saver
# ──────────────────────────────────────────────────────────────

def save_pipeline_result(ticker: str, charts: list, analysis: dict,
                          pdf_path: str, output_dir: str,
                          elapsed_seconds: float):
    """Save a pipeline run summary JSON for audit trail."""
    result = {
        "ticker": ticker,
        "run_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed_seconds, 1),
        "pdf_path": pdf_path,
        "charts_summary": [
            {
                "chart_id": c["chart_id"],
                "validated": c.get("validated", False),
                "refinement_count": c.get("refinement_count", 0),
            }
            for c in charts
        ],
        "analysis_summary": {
            "chart_analyses_count": len(analysis.get("chart_analyses", [])),
            "mda_summary_length": len(analysis.get("mda_summary", "")),
            "risk_summary_length": len(analysis.get("risk_summary", "")),
        },
    }

    result_path = os.path.join(output_dir, "pipeline_result.json")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Pipeline result saved: %s", result_path)
    return result


# ──────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────

def generate_report_pipeline(
    ticker: str,
    debug: bool = False,
    skip_charts: bool = False,
    charts_dir: str = None,
) -> dict:
    """
    Full FinSage CAVM pipeline for a single ticker.

    Args:
        ticker:       Stock ticker symbol (e.g. 'AAPL')
        debug:        If True, saves all 3 chart iterations + prints critiques
        skip_charts:  If True, loads charts from a previous run instead of
                      regenerating (saves ~10 minutes during development)
        charts_dir:   Path to previous chart output dir (used with skip_charts)

    Returns:
        Dict with pdf_path, elapsed_seconds, and stage summaries
    """
    ticker = ticker.upper().strip()
    if not re.match(r"^[A-Z]{1,5}$", ticker):
        raise ValueError(f"Invalid ticker symbol: {ticker!r}. Must be 1-5 uppercase letters.")

    start_time = datetime.now()

    print("\n" + "═" * 60)
    print(f"  FinSage CAVM Pipeline")
    print(f"  Ticker: {ticker}  |  {COMPANY_NAMES.get(ticker, ticker)}")
    print(f"  Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if debug:
        print(f"  Mode: DEBUG (all chart iterations saved)")
    if skip_charts:
        print(f"  Mode: SKIP CHARTS (using existing charts)")
    print("═" * 60 + "\n")

    # Create run output directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = str(OUTPUT_DIR / f"{ticker}_{ts}")
    os.makedirs(run_dir, exist_ok=True)

    session = get_session()

    try:
        # ── Stage 1: Charts ──────────────────────────────────
        if skip_charts:
            if charts_dir:
                charts = load_existing_charts(charts_dir)
            else:
                charts_dir = find_latest_charts_dir(ticker)
                charts = load_existing_charts(charts_dir)
                run_dir = charts_dir  # use existing dir for output
            logger.info("Skipped chart generation — using %s", charts_dir)
        else:
            charts = stage_charts(session, ticker, run_dir, debug=debug)

        if not charts:
            raise RuntimeError("No charts generated — cannot proceed")

        # ── Stage 2: Validation ──────────────────────────────
        validated_charts = stage_validation(session, charts)

        # Filter failed charts — only pass validated ones to analysis/report
        passing_charts = [c for c in validated_charts if c.get("validated")]
        failed = [c for c in validated_charts if not c.get("validated")]

        if failed:
            logger.warning(
                "%d chart(s) failed validation and will be excluded: %s",
                len(failed), [c["chart_id"] for c in failed]
            )

        if not passing_charts:
            raise RuntimeError(
                f"All {len(validated_charts)} charts failed validation — cannot generate report"
            )

        # ── Stage 3: Analysis (only passing charts) ──────────
        analysis = stage_analysis(session, passing_charts, ticker)

        # ── Stage 4: Report (only passing charts) ────────────
        pdf_path = stage_report(ticker, passing_charts, analysis, run_dir)

    finally:
        session.close()

    # ── Summary ──────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    result = save_pipeline_result(
        ticker, validated_charts, analysis, pdf_path, run_dir, elapsed
    )

    print("\n" + "═" * 60)
    print(f"  ✅ FinSage Pipeline Complete!")
    print(f"  Ticker:   {ticker}")
    print(f"  Elapsed:  {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Charts:   {len(validated_charts)} generated")
    print(f"  PDF:      {pdf_path}")
    print(f"\n  Open report:")
    print(f"  open \"{pdf_path}\"")
    print("═" * 60 + "\n")

    return {
        "ticker": ticker,
        "pdf_path": pdf_path,
        "elapsed_seconds": elapsed,
        "charts": validated_charts,
        "analysis": analysis,
    }


# ──────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FinSage CAVM Pipeline — Generate a financial research report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline — generate charts + analysis + PDF
  python agents/orchestrator.py --ticker AAPL

  # Full pipeline with debug chart iterations saved
  python agents/orchestrator.py --ticker AAPL --debug

  # Skip chart generation — reuse most recent charts (fast, for testing)
  python agents/orchestrator.py --ticker AAPL --skip-charts

  # Skip charts and specify exact folder
  python agents/orchestrator.py --ticker AAPL --skip-charts --charts-dir outputs/AAPL_20260403_154219
        """
    )
    parser.add_argument(
        "--ticker", default="AAPL",
        help="Stock ticker symbol (default: AAPL)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Save all 3 chart iterations + print VLM critiques"
    )
    parser.add_argument(
        "--skip-charts", action="store_true",
        help="Skip chart generation, reuse most recent charts for this ticker"
    )
    parser.add_argument(
        "--charts-dir", type=str, default=None,
        help="Specific chart output folder to use with --skip-charts"
    )
    args = parser.parse_args()

    generate_report_pipeline(
        ticker=args.ticker,
        debug=args.debug,
        skip_charts=args.skip_charts,
        charts_dir=args.charts_dir,
    )
