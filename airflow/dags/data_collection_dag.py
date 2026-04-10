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
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Add project paths for modular loader imports
sys.path.insert(0, '/opt/airflow')

DBT_DIR = '/opt/airflow/dbt_finsage'
TICKERS = ['AAPL', 'MSFT', 'GOOGL']

# Default arguments for all tasks
default_args = {
    'owner': 'finsage',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
}

# Define the DAG
dag = DAG(
    'data_collection_dag',
    default_args=default_args,
    description='Collect financial data from all sources and run dbt transformations',
    schedule='0 17 * * 1-5',  # 5 PM weekdays
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['finsage', 'data-collection'],
)


# ── Task callables using modular loaders ─────────────────────

def fetch_stock_prices():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.stock_loader import StockPriceLoader
    sf = SnowflakeClient()
    loader = StockPriceLoader(sf)
    for ticker in TICKERS:
        loader.load(ticker)
    sf.close()


def fetch_fundamentals():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.fundamentals_loader import FundamentalsLoader
    sf = SnowflakeClient()
    loader = FundamentalsLoader(sf)
    for ticker in TICKERS:
        loader.load(ticker)
    sf.close()


def fetch_news():
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.news_loader import NewsLoader
    sf = SnowflakeClient()
    loader = NewsLoader(sf)
    for ticker in TICKERS:
        loader.load(ticker)
    sf.close()


def fetch_sec_data():
    """Fetch both full-text SEC filings and XBRL structured data"""
    from src.utils.snowflake_client import SnowflakeClient
    from src.data_loaders.sec_loader import SECFilingLoader
    from src.data_loaders.xbrl_loader import XBRLLoader
    sf = SnowflakeClient()
    text_loader = SECFilingLoader(sf)
    xbrl_loader = XBRLLoader(sf)
    for ticker in TICKERS:
        text_loader.load(ticker, max_filings=2)
        xbrl_loader.load(ticker)
    sf.close()


def fetch_s3_filings():
    """Download SEC filings from EDGAR to S3 and extract text sections (MD&A, Risk Factors)."""
    try:
        from sec_filings.filing_downloader import download_filings_for_ticker
        from sec_filings.text_extractor import extract_pending_filings

        for ticker in TICKERS:
            for form_type in ["10-K", "10-Q"]:
                download_filings_for_ticker(ticker, form_type, count=2)
            extract_pending_filings(ticker=ticker)
    except ImportError:
        print("S3 filing modules not available — skipping")
    except Exception as e:
        print(f"S3 filing pipeline error: {e}")
        raise


def data_quality_check():
    """Basic data quality checks on analytics tables"""
    from src.utils.snowflake_client import SnowflakeClient
    sf = SnowflakeClient()
    tables = [
        'FINSAGE_DB.ANALYTICS.FCT_STOCK_METRICS',
        'FINSAGE_DB.ANALYTICS.FCT_FUNDAMENTALS_GROWTH',
        'FINSAGE_DB.ANALYTICS.FCT_NEWS_SENTIMENT_AGG',
        'FINSAGE_DB.ANALYTICS.FCT_SEC_FINANCIAL_SUMMARY',
        'FINSAGE_DB.ANALYTICS.DIM_COMPANY',
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
    >> task_run_dbt_staging \
    >> task_run_dbt_analytics \
    >> task_quality_check
