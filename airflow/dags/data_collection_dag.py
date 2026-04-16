"""
FinSage Data Collection DAG
Runs daily at 5 PM EST after market close.

Pipeline:
    1. Fetch data from all sources (parallel)
    2. Run dbt staging transformations
    3. Run dbt analytics transformations
    4. Data quality checks
"""

import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.exceptions import AirflowException

# Add project paths for modular loader imports
sys.path.insert(0, '/opt/airflow')

DBT_DIR = '/opt/airflow/dbt_finsage'

# Batch processing config for 50-ticker workload
BATCH_SIZE = 10
BATCH_DELAYS = {
    'news': 30,      # NewsAPI: 5 req/min — need longer pauses between batches
    'default': 5,    # yfinance, SEC EDGAR — shorter courtesy delay
}
# Minimum ticker coverage required for loader gate to pass (50%)
MIN_TICKER_COVERAGE = 25


def _load_tickers():
    """Load ticker list from config/tickers.yaml, falling back to defaults."""
    config_path = Path('/opt/airflow/config/tickers.yaml')
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config.get('tickers', ['AAPL', 'MSFT', 'GOOGL'])
    return ['AAPL', 'MSFT', 'GOOGL']


TICKERS = _load_tickers()
print(f"Loaded {len(TICKERS)} tickers from config")

# Default arguments for all tasks
default_args = {
    'owner': 'finsage',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

# Define the DAG
dag = DAG(
    'data_collection_dag',
    default_args=default_args,
    description='Collect financial data from all sources and run dbt transformations',
    schedule='0 22 * * 1-5',  # 5 PM EST / 10 PM UTC weekdays
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['finsage', 'data-collection'],
)


# ── Batch helper ──────────────────────────────────────────────

def _run_in_batches(tickers: list, loader, delay_key: str = 'default', **load_kwargs):
    """Process tickers in batches with delays between batches.

    Returns list of (ticker, success_bool) tuples.
    """
    delay = BATCH_DELAYS.get(delay_key, BATCH_DELAYS['default'])
    results = []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        for ticker in batch:
            try:
                loader.load(ticker, **load_kwargs)
                results.append((ticker, True))
            except Exception as e:
                print(f"WARNING: {ticker} failed: {e}")
                results.append((ticker, False))
        # Delay between batches (skip after last batch)
        if i + BATCH_SIZE < len(tickers):
            print(f"Batch {i // BATCH_SIZE + 1} complete — sleeping {delay}s for rate limits")
            time.sleep(delay)
    succeeded = sum(1 for _, ok in results if ok)
    print(f"Finished: {succeeded}/{len(results)} tickers succeeded")
    return results


# ── Task callables using modular loaders ─────────────────────

def fetch_stock_prices():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.stock_loader import StockPriceLoader
    sf = SnowflakeClient()
    loader = StockPriceLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='default')
    sf.close()


def fetch_fundamentals():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.fundamentals_loader import FundamentalsLoader
    sf = SnowflakeClient()
    loader = FundamentalsLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='default')
    sf.close()


def fetch_news():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.news_loader import NewsLoader
    sf = SnowflakeClient()
    loader = NewsLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='news')
    sf.close()


def fetch_sec_data():
    """Fetch both full-text SEC filings and XBRL structured data"""
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.sec_loader import SECFilingLoader
    from src.data_loaders.xbrl_loader import XBRLLoader
    sf = SnowflakeClient()
    text_loader = SECFilingLoader(sf)
    xbrl_loader = XBRLLoader(sf)
    delay = BATCH_DELAYS['default']
    for i in range(0, len(TICKERS), BATCH_SIZE):
        batch = TICKERS[i:i + BATCH_SIZE]
        for ticker in batch:
            try:
                text_loader.load(ticker, max_filings=2)
            except Exception as e:
                print(f"WARNING: SEC text for {ticker} failed: {e}")
            try:
                xbrl_loader.load(ticker)
            except Exception as e:
                print(f"WARNING: XBRL for {ticker} failed: {e}")
        if i + BATCH_SIZE < len(TICKERS):
            print(f"SEC batch {i // BATCH_SIZE + 1} complete — sleeping {delay}s")
            time.sleep(delay)
    sf.close()


def fetch_s3_filings():
    """Download SEC filings from EDGAR to S3 and extract text sections (MD&A, Risk Factors)."""
    try:
        from scripts.sec_filings.filing_downloader import download_filings_for_ticker
        from scripts.sec_filings.text_extractor import extract_pending_filings

        delay = BATCH_DELAYS['default']
        for i in range(0, len(TICKERS), BATCH_SIZE):
            batch = TICKERS[i:i + BATCH_SIZE]
            for ticker in batch:
                try:
                    for form_type in ["10-K", "10-Q"]:
                        download_filings_for_ticker(ticker, form_type, count=2)
                    extract_pending_filings(ticker=ticker)
                except Exception as e:
                    print(f"WARNING: S3 filings for {ticker} failed: {e}")
            if i + BATCH_SIZE < len(TICKERS):
                print(f"S3 batch {i // BATCH_SIZE + 1} complete — sleeping {delay}s")
                time.sleep(delay)
    except ImportError:
        print("S3 filing modules not available — skipping")
    except Exception as e:
        print(f"S3 filing pipeline error: {e}")
        raise


def check_loaders_success():
    """Gate: ensure RAW tables have sufficient ticker coverage before running dbt.

    With 50 tickers, partial failures are expected (API limits, transient errors).
    We require at least MIN_TICKER_COVERAGE distinct tickers with new data today.
    """
    from src.utils.snowflake_client import SnowflakeClient
    sf = SnowflakeClient()
    raw_tables = [
        'RAW.RAW_STOCK_PRICES',
        'RAW.RAW_FUNDAMENTALS',
        'RAW.RAW_NEWS',
        'RAW.RAW_SEC_FILINGS',
    ]
    low_coverage = []
    try:
        for table in raw_tables:
            df = sf.query_to_dataframe(
                f"SELECT COUNT(DISTINCT TICKER) AS cnt FROM {table} "
                f"WHERE ingested_at >= CURRENT_DATE()"
            )
            count = int(df.iloc[0]['CNT']) if not df.empty else 0
            print(f"  {table}: {count} distinct tickers with new data today")
            if count < MIN_TICKER_COVERAGE:
                low_coverage.append(f"{table} ({count}/{MIN_TICKER_COVERAGE})")
    finally:
        sf.close()

    if low_coverage:
        raise AirflowException(
            f"Loader gate failed — insufficient ticker coverage: {', '.join(low_coverage)}"
        )
    print(f"All tables have >= {MIN_TICKER_COVERAGE} tickers with fresh data — proceeding to dbt.")


def data_quality_check():
    """Basic data quality checks on analytics tables"""
    from src.utils.snowflake_client import SnowflakeClient
    sf = SnowflakeClient()
    tables = [
        'ANALYTICS.FCT_STOCK_METRICS',
        'ANALYTICS.FCT_FUNDAMENTALS_GROWTH',
        'ANALYTICS.FCT_NEWS_SENTIMENT_AGG',
        'ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY',
        'ANALYTICS.DIM_COMPANY',
    ]
    for table in tables:
        try:
            result = sf.query_to_dataframe(f"SELECT COUNT(*) AS cnt FROM {table}")
            count = result.iloc[0]['CNT'] if not result.empty else 0
            print(f"  {table}: {count} rows")
            if count == 0:
                print(f"  WARNING: {table} is empty!")
        except Exception as e:
            print(f"  ERROR checking {table}: {e}")
    sf.close()
    print("Data quality checks complete.")


# ── Task definitions ─────────────────────────────────────────

task_fetch_stocks = PythonOperator(
    task_id='fetch_stock_prices',
    python_callable=fetch_stock_prices,
    dag=dag,
)

task_fetch_fundamentals = PythonOperator(
    task_id='fetch_fundamentals',
    python_callable=fetch_fundamentals,
    dag=dag,
)

task_fetch_news = PythonOperator(
    task_id='fetch_news',
    python_callable=fetch_news,
    dag=dag,
)

task_fetch_sec = PythonOperator(
    task_id='fetch_sec_data',
    python_callable=fetch_sec_data,
    dag=dag,
)

task_fetch_s3_filings = PythonOperator(
    task_id='fetch_s3_filings',
    python_callable=fetch_s3_filings,
    dag=dag,
)

task_check_loaders = PythonOperator(
    task_id='check_loaders_success',
    python_callable=check_loaders_success,
    dag=dag,
)

task_run_dbt_staging = BashOperator(
    task_id='run_dbt_staging',
    bash_command=f'cd {DBT_DIR} && dbt run --select staging',
    dag=dag,
)

task_run_dbt_analytics = BashOperator(
    task_id='run_dbt_analytics',
    bash_command=f'cd {DBT_DIR} && dbt run --select analytics',
    dag=dag,
)

task_quality_check = PythonOperator(
    task_id='data_quality_check',
    python_callable=data_quality_check,
    dag=dag,
)

# ── Task dependencies ────────────────────────────────────────
# All data fetchers run in parallel, then dbt staging, then analytics, then QC
[task_fetch_stocks, task_fetch_fundamentals, task_fetch_news, task_fetch_sec, task_fetch_s3_filings] \
    >> task_check_loaders \
    >> task_run_dbt_staging \
    >> task_run_dbt_analytics \
    >> task_quality_check
