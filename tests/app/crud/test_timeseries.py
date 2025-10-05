import pytest

from app.crud import timeseries as ts
from datetime import datetime, timedelta, date, time as dt_time


@pytest.fixture
def two_day_timeseries_setup(db_session, sample_data_factory):
    """Build a two-day window of DailyAssetMetrics with latest-revision semantics."""

    def _midnight(days_ago: int) -> datetime:
        return datetime.combine(date.today() - timedelta(days=days_ago), dt_time.min)

    two_days_ago, one_day_ago = _midnight(2), _midnight(1)
    p1 = sample_data_factory.platform(name="Upbit", category="거래소")
    p2 = sample_data_factory.platform(name="Binance", category="거래소")

    # Two days ago - older revs (ignored)
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="BTC",
        revision=1,
        after_value_krw=100.0,
        created_at=two_days_ago,
    )
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="ETH",
        revision=1,
        after_value_krw=50.0,
        created_at=two_days_ago,
    )
    # Two days ago - latest revs (summed)
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="BTC",
        revision=2,
        after_value_krw=200.0,
        created_at=two_days_ago,
    )
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="ETH",
        revision=2,
        after_value_krw=80.0,
        created_at=two_days_ago,
    )
    sample_data_factory.daily_metric(
        platform=p2,
        symbol="TSLA",
        revision=1,
        after_value_krw=300.0,
        created_at=two_days_ago,
    )
    # One day ago - intermediate and latest revisions
    sample_data_factory.daily_metric(
        platform=p2,
        symbol="TSLA",
        revision=2,
        after_value_krw=320.0,
        created_at=one_day_ago,
    )
    sample_data_factory.daily_metric(
        platform=p2,
        symbol="TSLA",
        revision=3,
        after_value_krw=340.0,
        created_at=one_day_ago,
    )
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="BTC",
        revision=3,
        after_value_krw=220.0,
        created_at=one_day_ago,
    )
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="ETH",
        revision=3,
        after_value_krw=90.0,
        created_at=one_day_ago,
    )
    # Outside window
    sample_data_factory.daily_metric(
        platform=p1,
        symbol="BTC",
        revision=4,
        after_value_krw=260.0,
        created_at=datetime.now() - timedelta(days=190),
    )

    db_session.commit()
    return two_days_ago, one_day_ago


def test_get_portfolio_timeseries_returns_latest_daily_totals(
    db_session, two_day_timeseries_setup
):
    # Act
    two_days_ago, one_day_ago = two_day_timeseries_setup
    series = ts.get_portfolio_timeseries(db_session, days=30)

    # Assert
    assert [row["date"] for row in series] == [two_days_ago.date(), one_day_ago.date()]
    assert [row["total_krw"] for row in series] == pytest.approx([580.0, 650.0])


@pytest.mark.parametrize(
    "days, expected_dates",
    [
        (1, lambda _, one_day_ago: [one_day_ago.date()]),
        (
            30,
            lambda two_days_ago, one_day_ago: [two_days_ago.date(), one_day_ago.date()],
        ),
    ],
)
def test_timeseries_respects_cutoff_days(
    db_session, two_day_timeseries_setup, days, expected_dates
):
    two_days_ago, one_day_ago = two_day_timeseries_setup
    series = ts.get_portfolio_timeseries(db_session, days=days)
    assert [row["date"] for row in series] == expected_dates(two_days_ago, one_day_ago)
