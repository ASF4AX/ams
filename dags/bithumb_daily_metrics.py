from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from tasks.daily_asset_metrics import process_metrics

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def calculate_bithumb_metrics():
    process_metrics("Bithumb")


with DAG(
    "bithumb_daily_metrics",
    default_args=default_args,
    description="Calculate daily asset metrics for Bithumb",
    schedule_interval="0 0 * * *",  # 매일 자정에 실행
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bithumb", "metrics", "daily"],
) as dag:

    calculate_metrics = PythonOperator(
        task_id="calculate_bithumb_metrics",
        python_callable=calculate_bithumb_metrics,
    )
