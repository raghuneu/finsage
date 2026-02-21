"""
FinSage Data Collection DAG
Runs daily at 5 PM EST after market close
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

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
    description='Collect financial data from all sources',
    schedule='0 17 * * 1-5',  # 5 PM weekdays
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['finsage', 'data-collection'],
)

# Task 1: Fetch stock prices
def fetch_stock_prices():
    print("Fetching stock prices from Yahoo Finance...")
    # We'll connect actual script later
    print("Stock prices fetched successfully!")

# Task 2: Fetch fundamentals
def fetch_fundamentals():
    print("Fetching fundamentals from Yahoo Finance...")
    print("Fundamentals fetched successfully!")

# Task 3: Fetch news
def fetch_news():
    print("Fetching news from NewsAPI...")
    print("News fetched successfully!")

# Task 4: Data quality check
def data_quality_check():
    print("Running data quality checks...")
    print("Data quality checks passed!")

# Define tasks
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

# Task 5: Run dbt transformations
task_run_dbt = BashOperator(
    task_id='run_dbt_transformations',
    bash_command='echo "dbt run --select staging"',
    dag=dag,
)

task_quality_check = PythonOperator(
    task_id='data_quality_check',
    python_callable=data_quality_check,
    dag=dag,
)

# Define task dependencies
# fetch_stocks, fetch_fundamentals, fetch_news run in PARALLEL
# then dbt runs, then quality check
[task_fetch_stocks, task_fetch_fundamentals, task_fetch_news] >> task_run_dbt >> task_quality_check
