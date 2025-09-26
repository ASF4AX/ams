"""Shared DAG-level fixtures for Airflow smoke testing."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

from tests.dags.tasks.conftest import _ensure_airflow_stub


_ensure_airflow_stub()

_airflow_module = sys.modules.setdefault("airflow", ModuleType("airflow"))
_operators_module = sys.modules.setdefault("airflow.operators", ModuleType("airflow.operators"))
_python_module = sys.modules.setdefault("airflow.operators.python", ModuleType("airflow.operators.python"))


_current_dag = None


class _StubDAG:  # pragma: no cover - simple container
    """Minimal DAG stub capturing metadata for assertions."""

    def __init__(
        self,
        dag_id: str,
        default_args: dict | None = None,
        description: str | None = None,
        schedule_interval=None,
        start_date=None,
        catchup: bool = False,
        tags: list[str] | None = None,
    ) -> None:
        self.dag_id = dag_id
        self.default_args = default_args or {}
        self.description = description
        self.schedule_interval = schedule_interval
        self.start_date = start_date
        self.catchup = catchup
        self.tags = tags or []
        self.tasks: list[_StubPythonOperator] = []
        self._previous = None

    def __enter__(self) -> "_StubDAG":
        global _current_dag
        self._previous = _current_dag
        _current_dag = self
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        global _current_dag
        _current_dag = self._previous
        self._previous = None
        return False

    def add_task(self, task: "_StubPythonOperator") -> None:
        self.tasks.append(task)


class _StubPythonOperator:  # pragma: no cover - simple container
    """Minimal PythonOperator stub storing task metadata."""

    def __init__(self, *, task_id: str, python_callable, dag: _StubDAG | None = None, **_: object) -> None:
        self.task_id = task_id
        self.python_callable = python_callable
        self.dag = dag or _current_dag
        if self.dag is None:
            raise RuntimeError("PythonOperator requires a DAG context")
        self.dag.add_task(self)


_airflow_module.DAG = _StubDAG
setattr(_operators_module, "python", _python_module)
_python_module.PythonOperator = _StubPythonOperator

_tasks_module = sys.modules.setdefault("tasks", ModuleType("tasks"))
for _submodule in (
    "daily_asset_metrics",
    "binance",
    "bitget",
    "bithumb",
    "kis",
):
    _module = importlib.import_module(f"dags.tasks.{_submodule}")
    sys.modules[f"tasks.{_submodule}"] = _module
    setattr(_tasks_module, _submodule, _module)
