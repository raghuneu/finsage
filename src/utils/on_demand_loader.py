"""
On-demand data loader for FinSage.

Checks data readiness for a ticker and loads only what is missing,
then runs dbt to populate the ANALYTICS layer.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def ensure_data_for_ticker(
    ticker: str,
    session=None,
    include_news: bool = True,
    include_sec: bool = True,
    include_s3_filings: bool = True,
    run_dbt: bool = True,
    progress_callback: Optional[callable] = None,
) -> dict:
    """Load missing data for a ticker and refresh the ANALYTICS layer.

    This is the main entry-point called from the frontend before report
    generation.  It:

    1. Checks what data already exists (RAW + ANALYTICS).
    2. Runs the data pipeline only for missing sources.
    3. Runs ``dbt run`` to refresh ANALYTICS tables.
    4. Re-checks readiness and returns the result.

    Args:
        ticker: Uppercase ticker symbol.
        session: Optional Snowpark session (for readiness checks).
                 If None, a temporary session is created.
        include_news: Whether to load news data if missing.
        include_sec: Whether to load SEC filing data if missing.
        include_s3_filings: Whether to run the S3 filing pipeline
                     (download from EDGAR → S3 → extract MD&A/Risk text).
                     Defaults to True. Degrades gracefully if AWS creds
                     are missing.
        run_dbt: Whether to run dbt after RAW loading.
        progress_callback: Optional ``fn(stage: str, detail: str)`` for
            live UI updates.

    Returns:
        dict with keys:
            readiness   – final readiness dict from ``check_data_readiness``
            pipeline    – pipeline result dict (or None if nothing loaded)
            dbt_success – bool (or None if dbt was skipped)
            loaded      – list of source names that were loaded
    """
    ticker = ticker.upper().strip()

    def _progress(stage: str, detail: str = "") -> None:
        if progress_callback:
            progress_callback(stage, detail)

    # --- lazy imports so this module stays light ----------------------
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from utils.data_readiness import check_data_readiness, check_raw_data_exists

    # Create a session if one wasn't provided
    owns_session = False
    if session is None:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from snowflake_connection import get_session
        session = get_session()
        owns_session = True

    try:
        # ── Step 1: check current state ──────────────────────────
        _progress("checking", f"Checking data readiness for {ticker}")
        readiness = check_data_readiness(session, ticker)
        raw_counts = check_raw_data_exists(session, ticker)

        if readiness["ready"]:
            _progress("ready", "All data sources available")
            return {
                "readiness": readiness,
                "pipeline": None,
                "dbt_success": None,
                "loaded": [],
            }

        # ── Step 2: determine what to load ───────────────────────
        missing = readiness["missing"]
        load_stocks = "stock" in missing
        load_fundamentals = "fundamentals" in missing
        load_news = include_news and "news" in missing
        load_sec = include_sec and "sec" in missing

        # Also check RAW: if RAW has data but ANALYTICS doesn't,
        # we only need dbt, not a fresh API fetch.
        raw_has_stock = raw_counts.get("stock", 0) > 0
        raw_has_fund = raw_counts.get("fundamentals", 0) > 0
        raw_has_sec_docs = raw_counts.get("sec_docs", 0) > 0

        # Skip S3 filing pipeline if docs already exist in RAW
        actually_load_s3 = include_s3_filings and not raw_has_sec_docs

        need_api_fetch = (
            (load_stocks and not raw_has_stock)
            or (load_fundamentals and not raw_has_fund)
            or load_news
            or load_sec
            or actually_load_s3
        )

        loaded = []
        pipeline_result = None

        if need_api_fetch:
            _progress("loading", f"Loading data for {ticker}: {', '.join(missing)}")

            from orchestration.data_pipeline import run_pipeline

            pipeline_result = run_pipeline(
                tickers=[ticker],
                load_stocks=load_stocks and not raw_has_stock,
                load_fundamentals=load_fundamentals and not raw_has_fund,
                load_news=load_news,
                load_sec=load_sec,
                load_xbrl=load_sec,
                load_s3_filings=actually_load_s3,
                run_dbt=False,  # we'll run dbt separately below
            )

            if ticker in pipeline_result.get("success", []):
                loaded = [s for s in missing]
            elif ticker in pipeline_result.get("partial", []):
                loaded = [s for s in missing]  # partial is still progress

        # ── Step 3: run dbt to refresh ANALYTICS ─────────────────
        dbt_success = None
        if run_dbt:
            _progress("dbt", "Running dbt transformations")
            dbt_success = _run_dbt()

        # ── Step 4: re-check readiness ───────────────────────────
        _progress("verifying", "Verifying data readiness")
        final_readiness = check_data_readiness(session, ticker)

        _progress("done", "Data loading complete")
        return {
            "readiness": final_readiness,
            "pipeline": pipeline_result,
            "dbt_success": dbt_success,
            "loaded": loaded,
        }

    finally:
        if owns_session:
            try:
                session.close()
            except Exception:
                pass


def _run_dbt() -> bool:
    """Run ``dbt run`` in the dbt_finsage project directory.

    Returns True on success, False otherwise.
    """
    dbt_dir = PROJECT_ROOT / "dbt_finsage"
    try:
        result = subprocess.run(
            ["dbt", "run"],
            cwd=str(dbt_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("dbt run completed successfully")
            return True
        else:
            logger.error("dbt run failed:\n%s", result.stderr)
            return False
    except FileNotFoundError:
        logger.warning("dbt not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        logger.error("dbt run timed out after 5 minutes")
        return False
    except Exception as exc:
        logger.error("dbt execution failed: %s", exc)
        return False
