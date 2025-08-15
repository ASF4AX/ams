from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from tasks.bithumb import sync_bithumb_assets

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "sync_bithumb_assets",
    default_args=default_args,
    description="빗썸 거래소의 자산 정보를 동기화합니다.",
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bithumb", "assets", "sync"],
)

sync_task = PythonOperator(
    task_id="sync_bithumb_assets",
    python_callable=sync_bithumb_assets,
    dag=dag,
)
