"""Smoke tests ensuring DAG modules import with expected metadata."""

from __future__ import annotations

import importlib
from datetime import timedelta

import pytest


@pytest.mark.parametrize(
    (
        "module_name",
        "dag_id",
        "expected_task_ids",
        "expected_schedule",
        "expected_tags",
        "expected_retries",
    ),
    [
        (
            "dags.binance_daily_metrics",
            "binance_daily_metrics",
            {"calculate_binance_metrics"},
            "0 0 * * *",
            {"binance", "metrics", "daily"},
            1,
        ),
        (
            "dags.bitget_daily_metrics",
            "bitget_daily_metrics",
            {"calculate_bitget_metrics"},
            "0 0 * * *",
            {"bitget", "metrics", "daily"},
            1,
        ),
        (
            "dags.bithumb_daily_metrics",
            "bithumb_daily_metrics",
            {"calculate_bithumb_metrics"},
            "0 0 * * *",
            {"bithumb", "metrics", "daily"},
            1,
        ),
        (
            "dags.kis_daily_metrics",
            "kis_daily_metrics",
            {"calculate_kis_metrics"},
            "0 0 * * *",
            {"kis", "metrics", "daily"},
            1,
        ),
        (
            "dags.sync_binance_assets",
            "sync_binance_assets",
            {"sync_binance_assets"},
            timedelta(hours=1),
            {"binance", "assets", "sync"},
            3,
        ),
        (
            "dags.sync_bitget_assets",
            "sync_bitget_assets",
            {"sync_bitget_assets"},
            timedelta(hours=1),
            {"bitget", "assets", "sync"},
            3,
        ),
        (
            "dags.sync_bithumb_assets",
            "sync_bithumb_assets",
            {"sync_bithumb_assets"},
            timedelta(hours=1),
            {"bithumb", "assets", "sync"},
            3,
        ),
        (
            "dags.sync_kis_assets",
            "sync_kis_assets",
            {"sync_kis_assets"},
            timedelta(hours=1),
            {"kis", "assets", "sync"},
            3,
        ),
    ],
)
def test_dag_modules_expose_expected_metadata(
    module_name: str,
    dag_id: str,
    expected_task_ids: set[str],
    expected_schedule,
    expected_tags: set[str],
    expected_retries: int,
) -> None:
    """Import each DAG module and confirm the exported DAG metadata."""

    module = importlib.import_module(module_name)

    dag = getattr(module, "dag")
    assert dag.dag_id == dag_id
    assert dag.schedule_interval == expected_schedule
    assert set(dag.tags) == expected_tags
    assert dag.catchup is False
    assert dag.default_args.get("owner") == "airflow"
    assert dag.default_args.get("retries") == expected_retries

    task_ids = {task.task_id for task in dag.tasks}
    assert task_ids == expected_task_ids
    assert len(dag.tasks) == len(expected_task_ids)
