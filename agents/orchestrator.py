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
import concurrent.futures
from datetime import datetime
from pathlib import Path

# Path setup — works when called from project root or agents/
PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from snowflake_connection import get_session
from chart_agent import generate_charts, regenerate_single_chart
from chart_specs import CANONICAL_CHART_ORDER
from validation_agent import validate_all_charts, validate_chart
from analysis_agent import run_analysis, generate_company_overview, generate_peer_comparison, generate_financial_deep_dive, generate_valuation_analysis
from report_agent import generate_report
from src.utils.observability import RunContext, PipelineTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "outputs"

# In-memory company-name cache, seeded with well-known tickers.
# resolve_company_name() populates this dynamically for unknown tickers.
_COMPANY_NAME_CACHE = {
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


def resolve_company_name(ticker: str, session=None) -> str:
    """Resolve a ticker to its full company name.

    Resolution order:
        1. In-memory cache
        2. DIM_COMPANY table in Snowflake (if session provided)
        3. yfinance ``shortName`` lookup
        4. Return the ticker itself as a last resort
    """
    ticker = ticker.upper().strip()

    # Method 1: cache
    if ticker in _COMPANY_NAME_CACHE:
        return _COMPANY_NAME_CACHE[ticker]

    # Method 2: Snowflake DIM_COMPANY
    if session is not None:
        try:
            rows = session.sql(
                f"SELECT COMPANY_NAME FROM ANALYTICS.DIM_COMPANY WHERE TICKER = '{ticker}'"
            ).collect()
            if rows and rows[0]["COMPANY_NAME"]:
                name = rows[0]["COMPANY_NAME"]
                _COMPANY_NAME_CACHE[ticker] = name
                logger.info("Resolved company name for %s from DIM_COMPANY: %s", ticker, name)
                return name
        except Exception as exc:
            logger.debug("DIM_COMPANY lookup failed for %s: %s", ticker, exc)

    # Method 3: yfinance
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName")
        if name:
            _COMPANY_NAME_CACHE[ticker] = name
            logger.info("Resolved company name for %s from yfinance: %s", ticker, name)
            return name
    except Exception as exc:
        logger.debug("yfinance lookup failed for %s: %s", ticker, exc)

    # Fallback: return ticker as-is
    return ticker


def _first_failure_reason(chart: dict) -> str:
    """Extract the first failed validation note for logging."""
    for note in chart.get("validation_notes", []):
        if not note.get("passed", True):
            return note.get("message") or note.get("feedback") or note.get("check", "unknown")
    return "unknown"


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
    """Stage 3 — Generate analysis via analysis_agent.

    Stage 3a (run_analysis) is serial due to Chain-of-Analysis cross-references.
    Stage 3b/3c (overview, peer, deep dive, valuation) are independent and run
    in parallel with per-thread Snowflake sessions.
    """
    logger.info("━" * 50)
    logger.info("STAGE 3a: LLM Analysis (Chain-of-Analysis — serial)")
    logger.info("━" * 50)
    analysis = run_analysis(session, charts, ticker)
    logger.info("Stage 3a complete: %d chart analyses + SEC summaries",
                len(analysis.get("chart_analyses", [])))

    # Stage 3b/3c: 4 independent LLM tasks — run in parallel
    logger.info("━" * 50)
    logger.info("STAGE 3b/3c: Overview, Peer, Deep Dive, Valuation (parallel)")
    logger.info("━" * 50)

    # Default fallback values for each task
    _defaults = {
        "company_overview": {
            "company_description": f"Company overview not available for {ticker}.",
            "key_facts": {},
            "business_segments": "",
        },
        "peer_comparison": {
            "ticker": ticker,
            "peers": [],
            "comparison_summary": f"Peer comparison not available for {ticker}.",
        },
        "financial_deep_dive": {
            "quarterly_data": [],
            "narrative": "Financial deep dive not available.",
            "balance_sheet_summary": "Balance sheet analysis not available.",
        },
        "valuation": {
            "ticker_metrics": {},
            "peer_metrics": [],
            "valuation_narrative": "Valuation analysis not available.",
        },
    }

    def _run_task(name, fn, tick):
        worker_session = get_session()
        try:
            result = fn(worker_session, tick)
            logger.info("%s generated for %s", name, tick)
            return name, result
        except Exception as e:
            logger.warning("%s failed for %s: %s", name, tick, e)
            return name, _defaults[name]
        finally:
            try:
                worker_session.close()
            except Exception:
                pass

    tasks = [
        ("company_overview",    generate_company_overview),
        ("peer_comparison",     generate_peer_comparison),
        ("financial_deep_dive", generate_financial_deep_dive),
        ("valuation",           generate_valuation_analysis),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_run_task, name, fn, ticker): name
            for name, fn in tasks
        }

        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                task_name, task_result = future.result()
                analysis[task_name] = task_result
            except Exception:
                logger.exception("Unexpected failure in %s", name)
                analysis[name] = _defaults[name]

    return analysis


def stage_report(ticker: str, charts: list, analysis: dict,
                 output_dir: str) -> str:
    """Stage 4 — Build PDF via report_agent."""
    logger.info("━" * 50)
    logger.info("STAGE 4: PDF Report Generation")
    logger.info("━" * 50)
    company_name = resolve_company_name(ticker)
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
    """Save pipeline run summary (pipeline_result.json) and full analysis text
    (analysis_result.json) for the evaluation system."""

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

    # Save full analysis text for evaluator (separate file — keeps pipeline_result lean)
    _save_analysis_result(analysis, output_dir)

    return result


def _save_analysis_result(analysis: dict, output_dir: str) -> None:
    """Write analysis_result.json with all LLM-generated text for the evaluator."""
    # Pull only serialisable / text-bearing keys
    _text_keys = (
        "chart_analyses", "mda_summary", "risk_summary", "investment_thesis",
        "company_overview", "peer_comparison", "financial_deep_dive", "valuation",
    )
    payload = {k: analysis[k] for k in _text_keys if k in analysis}
    path = os.path.join(output_dir, "analysis_result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Analysis result saved: %s", path)


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

    # ── Observability: create run context and tracker ─────
    ctx = RunContext(pipeline_type="CAVM", ticker=ticker)
    logger.info("Pipeline run_id=%s for %s", ctx.run_id, ticker)

    print("\n" + "═" * 60)
    print(f"  FinSage CAVM Pipeline")
    print(f"  Ticker: {ticker}  |  {resolve_company_name(ticker)}")
    print(f"  Run ID: {ctx.run_id}")
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

    # Tag all Snowflake queries with run_id for ACCOUNT_USAGE attribution
    try:
        query_tag = json.dumps({"app": "finsage", "component": "cavm_pipeline", "run_id": ctx.run_id})
        session.sql(f"ALTER SESSION SET QUERY_TAG = '{query_tag}'").collect()
    except Exception:
        logger.warning("Could not set QUERY_TAG on session")

    tracker = PipelineTracker(session, ctx)
    pdf_path = None

    try:
        # ── Stage 1: Charts ──────────────────────────────────
        tracker.start_stage("chart_generation")
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
            tracker.end_stage("chart_generation", status="FAILED",
                              error_message="No charts generated")
            raise RuntimeError("No charts generated — cannot proceed")
        tracker.end_stage("chart_generation", status="SUCCESS",
                          rows_affected=len(charts))

        # ── Stage 2: Validation with retry ───────────────────
        tracker.start_stage("validation")
        validated_charts = stage_validation(session, charts)

        MAX_ATTEMPTS = 3
        skipped = []
        for i, chart in enumerate(validated_charts):
            if chart.get("validated"):
                continue
            chart_id = chart.get("chart_id", "unknown")
            reason = _first_failure_reason(chart)
            attempt = 1  # initial generation already counts
            while not chart.get("validated") and attempt < MAX_ATTEMPTS:
                attempt += 1
                logger.info(
                    "Retrying chart %s, attempt %d/%d, reason: %s",
                    chart_id, attempt, MAX_ATTEMPTS, reason
                )
                try:
                    new_chart = regenerate_single_chart(
                        session, ticker, chart_id, run_dir, debug=debug
                    )
                    new_chart = validate_chart(session, new_chart)
                    validated_charts[i] = new_chart
                    chart = new_chart
                    reason = _first_failure_reason(chart)
                except Exception as e:
                    logger.warning("Retry exception for %s: %s", chart_id, e)
                    reason = f"retry exception: {e}"
            if not chart.get("validated"):
                chart["skipped_reason"] = reason
                skipped.append((chart_id, reason))
                logger.warning("Chart %s skipped after %d attempts: %s",
                               chart_id, MAX_ATTEMPTS, reason)

        passing_charts = [c for c in validated_charts if c.get("validated")]

        # ── Restore canonical chart ordering for deterministic PDF ──
        chart_order_map = {cid: idx for idx, cid in enumerate(CANONICAL_CHART_ORDER)}
        passing_charts.sort(key=lambda c: chart_order_map.get(c.get("chart_id", ""), 99))

        tracker.end_stage("validation", status="SUCCESS",
                          rows_affected=len(passing_charts),
                          metadata={"skipped": len(skipped), "total": len(validated_charts)})

        if len(skipped) > 2:
            details = "; ".join(f"{cid}: {r}" for cid, r in skipped)
            raise RuntimeError(
                f"Pipeline aborted — {len(skipped)} charts failed after retries: {details}"
            )

        if not passing_charts:
            raise RuntimeError(
                f"All {len(validated_charts)} charts failed validation — cannot generate report"
            )

        # ── Stage 3: Analysis (only passing charts) ──────────
        tracker.start_stage("analysis")
        analysis = stage_analysis(session, passing_charts, ticker)
        tracker.end_stage("analysis", status="SUCCESS",
                          rows_affected=len(analysis.get("chart_analyses", [])))

        # ── Stage 4: Report (only passing charts) ────────────
        tracker.start_stage("report_generation")
        pdf_path = stage_report(ticker, passing_charts, analysis, run_dir)
        tracker.end_stage("report_generation", status="SUCCESS")

    except Exception as e:
        # Record failure for whichever stage was in-flight
        for stage_name in list(tracker._stage_starts.keys()):
            tracker.end_stage(stage_name, status="FAILED",
                              error_message=str(e)[:500])
        logger.error("Pipeline failed: %s", e, exc_info=True)
        raise
    finally:
        session.close()

    # ── Summary ──────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    result = save_pipeline_result(
        ticker, validated_charts, analysis, pdf_path, run_dir, elapsed
    )
    result["run_id"] = ctx.run_id

    print("\n" + "═" * 60)
    print(f"  FinSage Pipeline Complete!")
    print(f"  Ticker:   {ticker}")
    print(f"  Run ID:   {ctx.run_id}")
    print(f"  Elapsed:  {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Charts:   {len(validated_charts)} generated")
    print(f"  PDF:      {pdf_path}")
    print(f"\n  Open report:")
    print(f"  open \"{pdf_path}\"")
    print("═" * 60 + "\n")

    return {
        "ticker": ticker,
        "run_id": ctx.run_id,
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
