from __future__ import annotations

import pytest

from app.crud import metrics as metrics_mod
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
