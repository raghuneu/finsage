"""
FinSage Data Collection Pipeline
Master orchestrator for all data loaders
"""

import sys
from pathlib import Path
from datetime import datetime
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

logger = setup_logger(__name__, 'data_pipeline.log')

def load_tickers():
    """Load ticker list from config file"""
    config_path = project_root / 'config' / 'tickers.yaml'

    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return ['AAPL', 'MSFT', 'GOOGL']

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config.get('tickers', [])

def run_pipeline(tickers=None, load_stocks=True, load_fundamentals=True,
                 load_news=False, load_sec=True):
    """
    Run complete data collection pipeline

    Args:
        tickers: List of tickers to process (None = load from config)
        load_stocks: Load stock prices
        load_fundamentals: Load company fundamentals
        load_news: Load news articles (requires NewsAPI key)
        load_sec: Load SEC filings (10-K, 10-Q)
    """
    logger.info("="*60)
    logger.info("🚀 FinSage Data Collection Pipeline Starting")
    logger.info("="*60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load tickers
    if tickers is None:
        tickers = load_tickers()

    logger.info(f"📊 Processing {len(tickers)} tickers")
    logger.info(f"Tickers: {', '.join(tickers)}")
    logger.info(f"Loading: stocks={load_stocks}, fundamentals={load_fundamentals}, news={load_news}, sec={load_sec}")

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

    # Track results
    results = {
        'success': [],
        'partial': [],
        'failed': []
    }

    # Process each ticker
    for idx, ticker in enumerate(tickers, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{idx}/{len(tickers)}] Processing {ticker}")
        logger.info(f"{'='*60}")

        loader_results = {}

        try:
            # Stock prices
            if load_stocks:
                logger.info(f"📈 Loading stock prices for {ticker}...")
                loader_results['stocks'] = loaders['stocks'].load(ticker)

            # Fundamentals
            if load_fundamentals:
                logger.info(f"💼 Loading fundamentals for {ticker}...")
                loader_results['fundamentals'] = loaders['fundamentals'].load(ticker)

            # News
            if load_news:
                logger.info(f"📰 Loading news for {ticker}...")
                loader_results['news'] = loaders['news'].load(ticker)

            # SEC filings (10-K, 10-Q)
            if load_sec:
                logger.info(f"📄 Loading SEC filings for {ticker}...")
                loader_results['sec'] = loaders['sec'].load(ticker, max_filings=2)

            # Categorize result
            if all(loader_results.values()):
                results['success'].append(ticker)
                logger.info(f"✅ {ticker} - ALL loaders successful")
            elif any(loader_results.values()):
                results['partial'].append(ticker)
                logger.warning(f"⚠️  {ticker} - PARTIAL success")
            else:
                results['failed'].append(ticker)
                logger.error(f"❌ {ticker} - ALL loaders failed")

        except Exception as e:
            results['failed'].append(ticker)
            logger.error(f"❌ {ticker} - Exception: {e}")
            continue

        # Small delay between tickers
        if idx < len(tickers):
            time.sleep(1)

    # Close connection
    sf_client.close()

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
        load_news=False,  # Set to True if you have NewsAPI key
        load_sec=True     # CRITICAL for LLM phase!
    )

    print(f"\n🎉 Pipeline complete! {len(results['success'])} successful")