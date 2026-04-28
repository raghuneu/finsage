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
# Per-table minimum ticker coverage for the loader gate.
# SEC filings are sparse (companies file quarterly), so we use a 14-day lookback
# window instead of daily, while keeping daily checks for the other sources.
MIN_TICKER_COVERAGE = {
    'RAW.RAW_STOCK_PRICES':  {'min_tickers': 25, 'lookback_days': 0},
    'RAW.RAW_FUNDAMENTALS':  {'min_tickers': 25, 'lookback_days': 0},
    'RAW.RAW_NEWS':          {'min_tickers': 15, 'lookback_days': 0},
    'RAW.RAW_SEC_FILINGS':   {'min_tickers': 25, 'lookback_days': 14},
}


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
    'email_on_failure': True,
    'email_on_retry': False,
    'email': [os.environ.get('AIRFLOW_ALERT_EMAIL', 'finsage-alerts@northeastern.edu')],
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
    dagrun_timeout=timedelta(hours=4),
)


# ── Batch helper ──────────────────────────────────────────────

def _run_in_batches(tickers: list, loader, delay_key: str = 'default', **load_kwargs):
    """Process tickers in batches with delays between batches.

    Returns list of (ticker, success_bool) tuples.
    """
    total = len(tickers)
    delay = BATCH_DELAYS.get(delay_key, BATCH_DELAYS['default'])
    results = []
    for i in range(0, total, BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        batch = tickers[i:i + BATCH_SIZE]
        for j, ticker in enumerate(batch):
            idx = i + j + 1
            print(f"[{idx}/{total}] (batch {batch_num}/{total_batches}) >>> {ticker}")
            try:
                loader.load(ticker, **load_kwargs)
                results.append((ticker, True))
            except Exception as e:
                print(f"WARNING: {ticker} failed: {e}")
                results.append((ticker, False))
        # Delay between batches (skip after last batch)
        if i + BATCH_SIZE < total:
            print(f"Batch {batch_num}/{total_batches} complete — sleeping {delay}s for rate limits")
            time.sleep(delay)
    succeeded = sum(1 for _, ok in results if ok)
    print(f"Finished: {succeeded}/{total} tickers succeeded")
    return results


# ── Task callables using modular loaders ─────────────────────

def fetch_stock_prices():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.stock_loader import StockPriceLoader
    sf = SnowflakeClient(component="airflow_stock_loader")
    loader = StockPriceLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='default')
    sf.close()


def fetch_fundamentals():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.fundamentals_loader import FundamentalsLoader
    sf = SnowflakeClient(component="airflow_fundamentals_loader")
    loader = FundamentalsLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='default')
    sf.close()


def fetch_news():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.news_loader import NewsLoader
    sf = SnowflakeClient(component="airflow_news_loader")
    loader = NewsLoader(sf)
    _run_in_batches(TICKERS, loader, delay_key='news')
    sf.close()


def fetch_sec_data():
    """Fetch both full-text SEC filings and XBRL structured data"""
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.sec_loader import SECFilingLoader
    from src.data_loaders.xbrl_loader import XBRLLoader
    sf = SnowflakeClient(component="airflow_sec_loader")
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
    Each table has its own minimum threshold and lookback window configured in
    MIN_TICKER_COVERAGE.  SEC filings use a 7-day window because companies only
    file quarterly — on most days very few tickers will have brand-new rows.
    """
    from src.utils.snowflake_client import SnowflakeClient
    sf = SnowflakeClient(component="airflow_loader_gate")
    low_coverage = []
    try:
        for table, cfg in MIN_TICKER_COVERAGE.items():
            lookback = cfg['lookback_days']
            threshold = cfg['min_tickers']
            date_expr = f"CURRENT_DATE() - {lookback}" if lookback else "CURRENT_DATE()"
            df = sf.query_to_dataframe(
                f"SELECT COUNT(DISTINCT TICKER) AS cnt FROM {table} "
                f"WHERE ingested_at >= {date_expr}"
            )
            count = int(df.iloc[0]['CNT']) if not df.empty else 0
            window = f"last {lookback}d" if lookback else "today"
            print(f"  {table}: {count} distinct tickers ({window})")
            if count < threshold:
                low_coverage.append(f"{table} ({count}/{threshold})")
    finally:
        sf.close()

    if low_coverage:
        raise AirflowException(
            f"Loader gate failed — insufficient ticker coverage: {', '.join(low_coverage)}"
        )
    print("All tables meet ticker coverage thresholds — proceeding to dbt.")


def data_quality_check():
    """Basic data quality checks on analytics tables"""
    from src.utils.snowflake_client import SnowflakeClient
    sf = SnowflakeClient(component="airflow_quality_check")
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


def snapshot_quality_metrics():
    """Capture data quality scores from RAW tables into FCT_DATA_QUALITY_HISTORY."""
    from src.utils.snowflake_client import SnowflakeClient
    from src.utils.observability import snapshot_data_quality
    sf = SnowflakeClient(component="airflow_quality_snapshot")
    rows = snapshot_data_quality(sf.session)
    print(f"Quality snapshot captured: {rows} table-ticker groups recorded")
    sf.close()


task_quality_snapshot = PythonOperator(
    task_id='snapshot_quality_metrics',
    python_callable=snapshot_quality_metrics,
    dag=dag,
)

# ── Task dependencies ────────────────────────────────────────
# All data fetchers run in parallel, then dbt staging, then analytics, then QC
[task_fetch_stocks, task_fetch_fundamentals, task_fetch_news, task_fetch_sec, task_fetch_s3_filings] \
    >> task_check_loaders \
    >> task_run_dbt_staging \
    >> task_run_dbt_analytics \
    >> task_quality_check \
    >> task_quality_snapshot
