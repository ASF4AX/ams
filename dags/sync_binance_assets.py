from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from tasks.binance import sync_binance_assets

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "sync_binance_assets",
    default_args=default_args,
    description="바이낸스 거래소의 자산 정보를 동기화합니다.",
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["binance", "assets", "sync"],
)

sync_task = PythonOperator(
    task_id="sync_binance_assets",
    python_callable=sync_binance_assets,
    dag=dag,
)
