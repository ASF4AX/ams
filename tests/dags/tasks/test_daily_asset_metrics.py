"""Tests for the daily asset metrics task helpers."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy.engine import create_engine as sqla_create_engine
from sqlalchemy.orm import Session, sessionmaker

from dags.tasks import daily_asset_metrics
from models import models


@pytest.fixture()
def db_session() -> Session:
    """Provide an isolated in-memory database session for each test."""
    engine = sqla_create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        models.Base.metadata.drop_all(engine)
        engine.dispose()


def test_fetch_previous_metrics_returns_lookup_and_revision(db_session: Session) -> None:
    platform = models.Platform(name="Binance", category="거래소")
    db_session.add(platform)
    db_session.flush()

    metric_prev_a = models.DailyAssetMetrics(
        platform_id=platform.id,
        exchange="Binance",
        symbol="BTC",
        revision=1,
        after_value=100.0,
        after_value_krw=120_000.0,
    )
    metric_prev_b = models.DailyAssetMetrics(
        platform_id=platform.id,
        exchange="Binance",
        symbol="USDT",
        revision=1,
        after_value=180.0,
        after_value_krw=200_000.0,
    )
    db_session.add_all([metric_prev_a, metric_prev_b])
    db_session.flush()

    previous_lookup, new_revision = daily_asset_metrics._fetch_previous_metrics(
        db_session, platform.id
    )

    assert new_revision == 2
    assert previous_lookup.keys() == {
        ("Binance", "BTC"),
        ("Binance", "USDT"),
    }
    assert previous_lookup[("Binance", "BTC")] == pytest.approx((100.0, 120_000.0))
    assert previous_lookup[("Binance", "USDT")] == pytest.approx((180.0, 200_000.0))

    empty_lookup, initial_revision = daily_asset_metrics._fetch_previous_metrics(
        db_session, platform.id + 1
    )
    assert empty_lookup == {}
    assert initial_revision == 1


def test_process_metrics_persists_changes_for_latest_assets(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform = models.Platform(name="Binance", category="거래소")
    db_session.add(platform)
    db_session.flush()

    crypto_asset = models.Asset(
        name="Bitcoin",
        symbol="BTC",
        exchange="Binance",
        category=models.AssetCategory.CRYPTO.value,
        platform_id=platform.id,
        evaluation_amount=150.0,
        eval_amount_krw=160_000.0,
        quantity=0.25,
        revision=2,
    )
    stable_asset = models.Asset(
        name="Tether",
        symbol="USDT",
        exchange="Binance",
        category=models.AssetCategory.STABLE_COIN.value,
        platform_id=platform.id,
        evaluation_amount=200.0,
        eval_amount_krw=260_000.0,
        quantity=200.0,
        revision=2,
    )
    db_session.add_all([crypto_asset, stable_asset])

    previous_metrics = [
        models.DailyAssetMetrics(
            platform_id=platform.id,
            exchange="Binance",
            symbol="BTC",
            revision=1,
            after_value=100.0,
            after_value_krw=120_000.0,
        ),
        models.DailyAssetMetrics(
            platform_id=platform.id,
            exchange="Binance",
            symbol="USDT",
            revision=1,
            after_value=180.0,
            after_value_krw=200_000.0,
        ),
    ]
    db_session.add_all(previous_metrics)
    db_session.flush()

    @contextmanager
    def _session_override():
        yield db_session

    monkeypatch.setattr(daily_asset_metrics, "get_db_session", _session_override)

    daily_asset_metrics.process_metrics(platform.name)

    metrics = (
        db_session.query(models.DailyAssetMetrics)
        .filter(models.DailyAssetMetrics.revision == 2)
        .order_by(models.DailyAssetMetrics.symbol)
        .all()
    )

    assert len(metrics) == 2

    metrics_by_symbol = {metric.symbol: metric for metric in metrics}

    btc_metric = metrics_by_symbol["BTC"]
    assert btc_metric.after_value == pytest.approx(150.0)
    assert btc_metric.before_value == pytest.approx(100.0)
    assert btc_metric.change_amount == pytest.approx(50.0)
    assert btc_metric.return_rate == pytest.approx(0.5)
    assert btc_metric.after_value_krw == pytest.approx(160_000.0)
    assert btc_metric.before_value_krw == pytest.approx(120_000.0)
    assert btc_metric.change_amount_krw == pytest.approx(40_000.0)
    assert btc_metric.return_rate_krw == pytest.approx(1 / 3)

    usdt_metric = metrics_by_symbol["USDT"]
    assert usdt_metric.after_value == pytest.approx(200.0)
    assert usdt_metric.before_value == pytest.approx(180.0)
    assert usdt_metric.change_amount == pytest.approx(20.0)
    assert usdt_metric.return_rate == pytest.approx(20 / 180)
    assert usdt_metric.after_value_krw == pytest.approx(260_000.0)
    assert usdt_metric.before_value_krw == pytest.approx(200_000.0)
    assert usdt_metric.change_amount_krw == pytest.approx(60_000.0)
    assert usdt_metric.return_rate_krw == pytest.approx(0.3)
