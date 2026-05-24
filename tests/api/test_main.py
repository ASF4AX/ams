from __future__ import annotations

from datetime import datetime, timedelta, time, timezone

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_db
from api import main as api_main
from api.main import app
from app.crud import crud
from models.models import AssetCategory


@pytest.fixture()
def api_client(db_session):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _day(days_ago: int) -> datetime:
    return datetime.combine(
        (datetime.now(timezone.utc) - timedelta(days=days_ago)).date(), time.min
    )


def test_health_returns_database_status(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["database"] is True


@pytest.mark.anyio
async def test_lifespan_warns_without_initializing_schema(monkeypatch, caplog):
    class _Inspector:
        def get_table_names(self):
            return []

    schema_initialization_calls = []

    def _fail_if_called(*_args, **_kwargs):
        schema_initialization_calls.append(True)

    monkeypatch.setattr(api_main, "inspect", lambda _engine: _Inspector())
    monkeypatch.setattr(api_main.Base.metadata, "create_all", _fail_if_called)
    monkeypatch.setattr(api_main.Base.metadata, "drop_all", _fail_if_called)

    with caplog.at_level("WARNING", logger=api_main.logger.name):
        async with api_main.lifespan(app):
            pass

    assert schema_initialization_calls == []
    assert "missing DB tables" in caplog.text
    assert "assets" in caplog.text


def test_assets_summary_and_current_assets(api_client, db_session, sample_data_factory):
    kis = sample_data_factory.platform(name="KIS", category="증권사")
    binance = sample_data_factory.platform(name="Binance", category="거래소")
    sample_data_factory.asset(
        platform=kis,
        name="삼성전자",
        symbol="005930",
        category=AssetCategory.DOMESTIC_STOCK.value,
        revision=1,
        eval_amount_krw=1000.0,
        currency="KRW",
    )
    sample_data_factory.asset(
        platform=binance,
        name="Bitcoin",
        symbol="BTC",
        category=AssetCategory.CRYPTO.value,
        revision=1,
        eval_amount_krw=2000.0,
        currency="USD",
    )
    db_session.commit()

    summary = api_client.get("/v1/assets/summary").json()
    assert summary["currency"] == "KRW"
    assert summary["total_krw"] == pytest.approx(3000.0)
    assert {row["platform"]: row["amount_krw"] for row in summary["by_platform"]} == {
        "KIS": 1000.0,
        "Binance": 2000.0,
    }

    current = api_client.get("/v1/assets/current").json()
    assert {row["symbol"] for row in current} == {"005930", "BTC"}
    assert all("flow_amount_krw" not in row for row in current)


def test_period_return_and_timeseries_endpoints(
    api_client, db_session, sample_data_factory
):
    platform = sample_data_factory.platform(name="KIS")
    sample_data_factory.asset(
        platform=platform,
        symbol="CASH",
        category=AssetCategory.CASH.value,
        revision=1,
        eval_amount_krw=1500.0,
    )
    sample_data_factory.daily_metric(
        platform=platform,
        symbol="CASH",
        revision=1,
        after_value_krw=1000.0,
        created_at=_day(5),
    )
    db_session.commit()

    response = api_client.get("/v1/returns/period", params={"days": 7})
    assert response.status_code == 200
    assert response.json()["return_rate_pct"] == pytest.approx(50.0)

    portfolio = api_client.get("/v1/timeseries/portfolio", params={"days": 7}).json()
    assert portfolio == [{"date": _day(5).date().isoformat(), "total_krw": 1000.0}]

    platforms = api_client.get("/v1/timeseries/platforms", params={"days": 7}).json()
    assert platforms == [
        {
            "date": _day(5).date().isoformat(),
            "platform": "KIS",
            "total_krw": 1000.0,
        }
    ]


def test_daily_metrics_and_transactions_filters(
    api_client, db_session, sample_data_factory
):
    platform = sample_data_factory.platform(name="KIS")
    asset = sample_data_factory.asset(
        platform=platform,
        symbol="KRW",
        category=AssetCategory.CASH.value,
        revision=1,
        eval_amount_krw=1000.0,
    )
    sample_data_factory.daily_metric(
        platform=platform,
        symbol="KRW",
        revision=1,
        before_value_krw=900.0,
        after_value_krw=1000.0,
        created_at=_day(1),
    )
    crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="입금",
        price=1.0,
        quantity=100.0,
        transaction_date=_day(1),
        flow_fx_to_krw=1.0,
    )
    db_session.commit()

    metrics = api_client.get(
        "/v1/metrics/daily", params={"days": 7, "platform": "KIS"}
    ).json()
    assert len(metrics) == 1
    assert metrics[0]["platform"] == "KIS"
    assert metrics[0]["symbol"] == "KRW"

    transactions = api_client.get(
        "/v1/transactions", params={"days": 7, "type": "입금"}
    ).json()
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "입금"
    assert transactions[0]["asset_symbol"] == "KRW"
    assert transactions[0]["platform"] == "KIS"


def test_mdd_endpoint_calculates_maximum_drawdown(
    api_client, db_session, sample_data_factory
):
    platform = sample_data_factory.platform(name="KIS")
    for days_ago, value in [(3, 100.0), (2, 120.0), (1, 90.0)]:
        sample_data_factory.daily_metric(
            platform=platform,
            symbol="TOTAL",
            revision=1,
            after_value_krw=value,
            created_at=_day(days_ago),
        )
    db_session.commit()

    payload = api_client.get("/v1/risk/mdd", params={"days": 7}).json()
    assert payload["currency"] == "KRW"
    assert payload["maximum_drawdown_pct"] == pytest.approx(-25.0)
    assert payload["peak_value_krw"] == pytest.approx(120.0)
    assert payload["trough_value_krw"] == pytest.approx(90.0)
