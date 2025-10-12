from __future__ import annotations

import pytest

from app.crud import metrics as metrics_mod
from app.crud import crud
from models.models import AssetCategory
from datetime import datetime, timedelta, time
from sqlalchemy.orm import Session


def day_n_days_ago(days: int) -> datetime:
    """Return a datetime at midnight N days ago (date-only semantics)."""
    return datetime.combine((datetime.now() - timedelta(days=days)).date(), time.min)


@pytest.fixture()
def stub_total(monkeypatch: pytest.MonkeyPatch) -> float:
    """Stub current snapshot total to a fixed value for reproducible returns."""
    monkeypatch.setattr(metrics_mod, "get_total_asset_value", lambda _db: 1000.0)
    return 1000.0


def test_period_return_uses_first_day_on_or_after_cutoff(
    sample_data_factory, db_session: Session, stub_total: float
):
    """Selects the earliest day >= cutoff and aggregates latest revision per platform for that day."""

    factory = sample_data_factory

    # Two platforms
    p1 = factory.platform(name="P1")
    p2 = factory.platform(name="P2")

    # Two calendar days (date-only)
    d1 = day_n_days_ago(10)
    d2 = day_n_days_ago(5)

    # Seed multiple revisions for the chosen day (d2); only latest should count per platform
    # Platform 1
    factory.daily_metric(
        platform=p1, symbol="BTC", revision=1, after_value_krw=100.0, created_at=d2
    )
    factory.daily_metric(
        platform=p1, symbol="BTC", revision=2, after_value_krw=200.0, created_at=d2
    )
    # Platform 2
    factory.daily_metric(
        platform=p2, symbol="ETH", revision=1, after_value_krw=250.0, created_at=d2
    )
    factory.daily_metric(
        platform=p2, symbol="ETH", revision=3, after_value_krw=300.0, created_at=d2
    )

    # Older day (d1) should be ignored when cutoff is 7 days
    factory.daily_metric(
        platform=p1, symbol="BTC", revision=1, after_value_krw=9999.0, created_at=d1
    )
    factory.daily_metric(
        platform=p2, symbol="ETH", revision=1, after_value_krw=9999.0, created_at=d1
    )

    # days=7 -> cutoff = now-7 -> target day should be d2 only
    result = metrics_mod.get_portfolio_period_return(db_session, days=7)

    # Expected return = 100%
    assert result == pytest.approx(100.0)


def test_period_return_none_when_no_day_on_or_after_cutoff(
    sample_data_factory, db_session: Session, stub_total: float
):
    """Returns None if no DailyAssetMetrics day exists on/after cutoff_date."""

    factory = sample_data_factory
    p = factory.platform(name="OnlyOld")

    # Only an old day 30 days ago (date-only)
    old_day = day_n_days_ago(30)
    factory.daily_metric(
        platform=p, symbol="X", revision=1, after_value_krw=100.0, created_at=old_day
    )

    # days=7 -> cutoff is now-7; no day >= cutoff exists
    assert metrics_mod.get_portfolio_period_return(db_session, days=7) is None


def test_period_return_none_when_days_non_positive(db_session: Session):
    assert metrics_mod.get_portfolio_period_return(db_session, days=0) is None
    assert metrics_mod.get_portfolio_period_return(db_session, days=-5) is None


# --- Flow-adjusted return tests (reflect_flows=True) ---


def _make_krw_asset(db: Session):
    platform = crud.create_platform(db, name="Upbit", category="거래소")
    asset = crud.create_asset(
        db,
        name="KRW",
        symbol="KRW",
        category=AssetCategory.CASH.value,
        platform_id=platform.id,
        current_price=1.0,
        quantity=0.0,
        revision=1,
    )
    return platform, asset


@pytest.mark.parametrize(
    "flows, expected_adjusted",
    [
        # within window: +200, -50 => net +150; adjusted = 35%
        (
            [(3, "입금", 200.0), (1, "출금", 50.0)],
            35.0,
        ),
        # outside window (8 days), cutoff-day (7 days) ignored, inside counted (+100 on day 6); adjusted = 40%
        (
            [(8, "입금", 999.0), (7, "입금", 70.0), (6, "입금", 100.0)],
            40.0,
        ),
    ],
)
def test_period_return_with_flows_parametrized(
    sample_data_factory,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    flows,
    expected_adjusted,
):
    # Stub current snapshot to 1500 for this test
    monkeypatch.setattr(metrics_mod, "get_total_asset_value", lambda _db: 1500.0)

    # Ensure target day within 7 days has past_total = 1000
    p1 = sample_data_factory.platform(name="P1")
    p2 = sample_data_factory.platform(name="P2")
    recent_day = day_n_days_ago(5)
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="BTC",
        revision=1,
        after_value_krw=400.0,
        created_at=recent_day,
    )
    sample_data_factory.daily_metric(
        platform=p2,
        symbol="ETH",
        revision=1,
        after_value_krw=600.0,
        created_at=recent_day,
    )

    # Create KRW asset and parameterized flows
    _, krw_asset = _make_krw_asset(db_session)
    for days_ago, tx_type, qty in flows:
        crud.create_transaction(
            db_session,
            asset_id=krw_asset.id,
            transaction_type=tx_type,
            price=1.0,
            quantity=float(qty),
            transaction_date=day_n_days_ago(int(days_ago)),
            flow_fx_to_krw=1.0,
        )

    # Plain return (no reflection) should remain 50%
    plain = metrics_mod.get_portfolio_period_return(
        db_session, days=7, reflect_flows=False
    )
    assert plain == pytest.approx(50.0)

    # Adjusted return matches expected per flow set
    adjusted = metrics_mod.get_portfolio_period_return(
        db_session, days=7, reflect_flows=True
    )
    assert adjusted == pytest.approx(expected_adjusted)
