"""
FinSage Data Collection DAG
Runs daily at 5 PM EST after market close
"""

from datetime import datetime, timedelta
import subprocess
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

SCRIPTS_DIR = "/opt/airflow/scripts"
PYTHON = sys.executable  # uses Airflow's own Python interpreter

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

def run_script(script_name):
    """Helper to run a script and raise on failure."""
    result = subprocess.run(
        [PYTHON, f"{SCRIPTS_DIR}/{script_name}"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise Exception(f"{script_name} failed with return code {result.returncode}")
    print(f"{script_name} completed successfully!")

def fetch_stock_prices():
    run_script("load_sample_stock_data.py")

def fetch_fundamentals():
    run_script("load_sample_fundamentals.py")

def fetch_news():
    run_script("load_sample_news.py")

def fetch_sec_data():
    run_script("load_sec_data.py")

def data_quality_check():
    print("Running data quality checks...")
    # Placeholder — will wire to real checks in analytics layer
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

task_fetch_sec = PythonOperator(
    task_id='fetch_sec_data',
    python_callable=fetch_sec_data,
    dag=dag,
)

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
# fetch_stocks, fetch_fundamentals, fetch_news, task_fetch_sec run in PARALLEL
# then dbt runs, then quality check
[task_fetch_stocks, task_fetch_fundamentals, task_fetch_news, task_fetch_sec] >> task_run_dbt >> task_quality_check
