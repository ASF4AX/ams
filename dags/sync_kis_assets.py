from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from tasks.kis import sync_kis_assets

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "sync_kis_assets",
    default_args=default_args,
    description="한국투자증권의 자산 정보를 동기화합니다.",
    schedule_interval=timedelta(hours=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["kis", "assets", "sync"],
)

sync_task = PythonOperator(
    task_id="sync_kis_assets",
    python_callable=sync_kis_assets,
    dag=dag,
)
