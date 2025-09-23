"""Tests for ``dags.utils.db`` helper functions.

The DAG utility module depends on Airflow's ``BaseHook`` at import time to
resolve connection information. The tests below provide a lightweight stub so
the module can be imported without requiring Airflow.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from models import models


def _ensure_airflow_stub() -> None:
    """Inject a minimal Airflow stub so the module under test can import."""
    if "airflow" in sys.modules and hasattr(sys.modules["airflow"], "hooks"):
        base_module = getattr(sys.modules["airflow"].hooks, "base", None)
        if base_module and hasattr(base_module, "BaseHook"):
            return

    airflow_module = sys.modules.setdefault("airflow", ModuleType("airflow"))
    hooks_module = sys.modules.setdefault("airflow.hooks", ModuleType("airflow.hooks"))
    airflow_module.hooks = hooks_module

    base_module = ModuleType("airflow.hooks.base")

    class _StubBaseHook:  # pragma: no cover - simple namespace container
        @staticmethod
        def get_connection(conn_id: str) -> SimpleNamespace:
            return SimpleNamespace(
                login="user",
                password="pass",
                host="localhost",
                port=5432,
                schema="test_db",
            )

    base_module.BaseHook = _StubBaseHook
    sys.modules["airflow.hooks.base"] = base_module
    hooks_module.base = base_module


_ensure_airflow_stub()
db = importlib.import_module("dags.utils.db")
def test_insert_asset_creates_platform_and_asset(db_session: Session) -> None:
    asset_data = {
        "symbol": "BTC",
        "quantity": 1.25,
        "category": models.AssetCategory.CRYPTO.value,
        "revision": 1,
        "platform": "Binance",
        "current_price": 100.0,
        "evaluation_amount": 125.0,
        "eval_amount_krw": 150000.0,
    }

    asset = db.insert_asset(db_session, dict(asset_data))
    db_session.flush()

    platform = db_session.query(models.Platform).one()
    assert platform.name == "Binance"
    assert platform.category == "거래소"

    stored_asset = db_session.query(models.Asset).one()
    assert stored_asset.id == asset.id
    assert stored_asset.name == "BTC"  # defaults to symbol when absent
    assert stored_asset.platform_id == platform.id
    assert stored_asset.revision == 1
    assert stored_asset.evaluation_amount == pytest.approx(125.0)
    assert stored_asset.eval_amount_krw == pytest.approx(150000.0)


def test_insert_asset_requires_mandatory_fields(db_session: Session) -> None:
    with pytest.raises(ValueError, match="필수 필드 누락: symbol"):
        db.insert_asset(
            db_session,
            {
                "quantity": 1,
                "category": models.AssetCategory.CRYPTO.value,
                "revision": 1,
            },
        )


def test_get_latest_revision_helpers(db_session: Session) -> None:
    assert db.get_latest_revision(db_session, "Upbit") == 0

    first = db.insert_asset(
        db_session,
        {
            "symbol": "ETH",
            "quantity": 2,
            "category": models.AssetCategory.CRYPTO.value,
            "revision": 1,
            "platform": "Upbit",
        },
    )
    db_session.flush()

    db.insert_asset(
        db_session,
        {
            "symbol": "ETH",
            "quantity": 3,
            "category": models.AssetCategory.CRYPTO.value,
            "revision": 2,
            "platform": "Upbit",
        },
    )
    db_session.flush()

    platform_id = first.platform_id
    assert db.get_latest_asset_revision_by_platform_id(db_session, platform_id) == 2
    assert db.get_latest_revision(db_session, "Upbit") == 2


def test_upsert_exchange_rate_and_lookup(db_session: Session) -> None:
    rate = db.upsert_exchange_rate(
        db_session,
        {"base_currency": "USD", "target_currency": "KRW", "rate": 1325.0},
    )
    db_session.flush()
    assert rate.rate == pytest.approx(1325.0)

    updated = db.upsert_exchange_rate(
        db_session,
        {"base_currency": "USD", "target_currency": "KRW", "rate": 1300.0},
    )
    db_session.flush()
    assert updated.id == rate.id
    assert updated.rate == pytest.approx(1300.0)

    db_session.commit()
    rates = db.get_exchange_rates(db_session)
    assert rates["KRW"] == pytest.approx(1.0)
    assert rates["USD"] == pytest.approx(1300.0)


def test_get_active_stable_coins(
    db_session: Session, sample_data_factory
) -> None:
    sample_data_factory.stable_coin(symbol="USDT", is_active=True)
    sample_data_factory.stable_coin(symbol="USDC", is_active=True)
    sample_data_factory.stable_coin(symbol="DAI", is_active=False)
    db_session.commit()

    active = db.get_active_stable_coins(db_session)
    assert active == {"USDT", "USDC"}
