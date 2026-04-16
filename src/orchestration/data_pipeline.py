"""
FinSage Data Collection Pipeline
Master orchestrator for all data loaders
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import time

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.snowflake_client import SnowflakeClient
from src.utils.logger import setup_logger
from src.data_loaders.stock_loader import StockPriceLoader
from src.data_loaders.fundamentals_loader import FundamentalsLoader
from src.data_loaders.news_loader import NewsLoader
from src.data_loaders.sec_loader import SECFilingLoader
from src.data_loaders.xbrl_loader import XBRLLoader

logger = setup_logger(__name__, 'data_pipeline.log')

def load_tickers():
    """Load ticker list from config file"""
    config_path = project_root / 'config' / 'tickers.yaml'

    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return ['AAPL', 'MSFT', 'GOOGL']  # Only fallback if no config

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config.get('tickers', [])

def run_pipeline(tickers=None, load_stocks=True, load_fundamentals=True,
                 load_news=True, load_sec=True, load_xbrl=True,
                 load_s3_filings=False, run_dbt=False):
    """
    Run complete data collection pipeline

    Args:
        tickers: List of tickers to process (None = load from config)
        load_stocks: Load stock prices
        load_fundamentals: Load company fundamentals
        load_news: Load news articles (requires NewsAPI key)
        load_sec: Load SEC filings (10-K, 10-Q)
        load_xbrl: Load XBRL structured financial data
        load_s3_filings: Download SEC filings to S3 + extract text (requires AWS credentials)
        run_dbt: Run dbt transformations after loading
    """
    logger.info("="*60)
    logger.info("🚀 FinSage Data Collection Pipeline Starting")
    logger.info("="*60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Warn about missing optional env vars upfront
    if not os.getenv("NEWSAPI_KEY"):
        logger.warning("ENV: NEWSAPI_KEY not set — news loading will return empty results")
    if not os.getenv("SEC_USER_AGENT"):
        logger.warning("ENV: SEC_USER_AGENT not set — using fallback value")
    if not os.getenv("ALPHA_VANTAGE_API_KEY"):
        logger.warning("ENV: ALPHA_VANTAGE_API_KEY not set — fundamentals may be limited")

    # Load tickers
    if tickers is None:
        tickers = load_tickers()

    logger.info(f"📊 Processing {len(tickers)} tickers")
    logger.info(f"Tickers: {', '.join(tickers)}")
    logger.info(f"Loading: stocks={load_stocks}, fundamentals={load_fundamentals}, news={load_news}, sec={load_sec}, xbrl={load_xbrl}")

    # Initialize Snowflake client
    sf_client = SnowflakeClient()

    # Initialize loaders
    loaders = {}
    if load_stocks:
        loaders['stocks'] = StockPriceLoader(sf_client)
    if load_fundamentals:
        loaders['fundamentals'] = FundamentalsLoader(sf_client)
    if load_news:
        loaders['news'] = NewsLoader(sf_client)
    if load_sec:
        loaders['sec'] = SECFilingLoader(sf_client)
    if load_xbrl:
        loaders['xbrl'] = XBRLLoader(sf_client)

    # Track results
    results = {
        'success': [],
        'partial': [],
        'failed': []
    }

    def _process_ticker(ticker, idx, total):
        """Process a single ticker through all enabled loaders."""
        logger.info(f"\n{'='*60}")
        logger.info(f"[{idx}/{total}] Processing {ticker}")
        logger.info(f"{'='*60}")

        loader_results = {}

        try:
            if load_stocks:
                logger.info(f"Loading stock prices for {ticker}...")
                loader_results['stocks'] = loaders['stocks'].load(ticker)

            if load_fundamentals:
                logger.info(f"Loading fundamentals for {ticker}...")
                loader_results['fundamentals'] = loaders['fundamentals'].load(ticker)

            if load_news:
                logger.info(f"Loading news for {ticker}...")
                loader_results['news'] = loaders['news'].load(ticker)

            if load_sec:
                logger.info(f"Loading SEC filings for {ticker}...")
                loader_results['sec'] = loaders['sec'].load(ticker, max_filings=2)

            if load_xbrl:
                logger.info(f"Loading XBRL data for {ticker}...")
                loader_results['xbrl'] = loaders['xbrl'].load(ticker)

            if load_s3_filings:
                logger.info(f"Downloading + extracting SEC filings for {ticker} via S3...")
                try:
                    from sec_filings.filing_downloader import download_filings_for_ticker
                    from sec_filings.text_extractor import extract_pending_filings

                    for form_type in ["10-K", "10-Q"]:
                        download_filings_for_ticker(ticker, form_type, count=2)
                    extract_pending_filings(ticker=ticker)
                    loader_results['s3_filings'] = True
                except ImportError:
                    logger.warning("S3 filing modules not available")
                    loader_results['s3_filings'] = False
                except Exception as e:
                    logger.error(f"S3 filing pipeline failed for {ticker}: {e}")
                    loader_results['s3_filings'] = False

            if all(loader_results.values()):
                return ('success', ticker)
            elif any(loader_results.values()):
                return ('partial', ticker)
            else:
                return ('failed', ticker)

        except Exception as e:
            logger.error(f"{ticker} - Exception: {e}")
            return ('failed', ticker)

    # Process tickers in parallel (max 5 concurrent to respect API rate limits)
    with ThreadPoolExecutor(max_workers=min(5, len(tickers))) as executor:
        futures = {
            executor.submit(_process_ticker, ticker, idx, len(tickers)): ticker
            for idx, ticker in enumerate(tickers, 1)
        }
        for future in as_completed(futures):
            status, ticker = future.result()
            results[status].append(ticker)

    # Close connection
    sf_client.close()

    # Run dbt transformations if requested
    if run_dbt:
        dbt_dir = project_root / 'dbt_finsage'
        logger.info("Running dbt transformations...")
        try:
            result = subprocess.run(
                ['dbt', 'run'],
                cwd=str(dbt_dir),
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("dbt run completed successfully")
            else:
                logger.error(f"dbt run failed:\n{result.stderr}")
        except FileNotFoundError:
            logger.warning("dbt not found in PATH — install with: pip install dbt-snowflake")
        except subprocess.TimeoutExpired:
            logger.error("dbt run timed out after 5 minutes")
        except Exception as e:
            logger.error(f"dbt execution failed: {e}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 PIPELINE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Fully Successful: {len(results['success'])}")
    if results['success']:
        logger.info(f"   {', '.join(results['success'])}")

    logger.info(f"⚠️  Partial Success: {len(results['partial'])}")
    if results['partial']:
        logger.info(f"   {', '.join(results['partial'])}")

    logger.info(f"❌ Failed: {len(results['failed'])}")
    if results['failed']:
        logger.info(f"   {', '.join(results['failed'])}")

    logger.info(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}")

    return results

if __name__ == "__main__":
    # Test with small set first
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']

    results = run_pipeline(
        tickers=test_tickers,
        load_stocks=True,
        load_fundamentals=True,
        load_news=True,   # Requires NEWSAPI_KEY environment variable
        load_sec=True,    # Full-text filings for LLM analysis
        load_xbrl=True,   # XBRL structured data for analytics layer
        run_dbt=True      # Run dbt staging + analytics after loading
    )

    print(f"\n🎉 Pipeline complete! {len(results['success'])} successful")