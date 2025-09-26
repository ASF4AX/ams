"""Shared fixtures and stubs for DAG task tests."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace


def _ensure_airflow_stub() -> None:
    """Provide a lightweight Airflow stub for module imports."""
    airflow_module = sys.modules.setdefault("airflow", ModuleType("airflow"))
    hooks_module = sys.modules.setdefault("airflow.hooks", ModuleType("airflow.hooks"))
    models_module = sys.modules.setdefault("airflow.models", ModuleType("airflow.models"))

    airflow_module.hooks = hooks_module
    airflow_module.models = models_module

    if "airflow.hooks.base" not in sys.modules:
        base_module = ModuleType("airflow.hooks.base")

        class _StubBaseHook:  # pragma: no cover - trivial container
            @staticmethod
            def get_connection(conn_id: str) -> SimpleNamespace:
                return SimpleNamespace(
                    login="user",
                    password="pass",
                    host="localhost",
                    port=5432,
                    schema="test_db",
                    extra_dejson={"password": "pass"},
                )

        base_module.BaseHook = _StubBaseHook
        sys.modules["airflow.hooks.base"] = base_module
        hooks_module.base = base_module
    else:  # pragma: no cover - executed when stub already present
        hooks_module.base = sys.modules["airflow.hooks.base"]

    if not hasattr(models_module, "Variable"):

        class _StubVariable:  # pragma: no cover - trivial container
            _storage: dict[str, str] = {}

            @classmethod
            def get(cls, key: str, default_var: str | None = None):
                return cls._storage.get(key, default_var)

            @classmethod
            def set(cls, key: str, value: str) -> None:
                cls._storage[key] = value

        models_module.Variable = _StubVariable


_ensure_airflow_stub()


if "utils.db" not in sys.modules:
    dags_utils_db = importlib.import_module("dags.utils.db")
    utils_module = sys.modules.setdefault("utils", ModuleType("utils"))
    sys.modules["utils.db"] = dags_utils_db
    setattr(utils_module, "db", dags_utils_db)
