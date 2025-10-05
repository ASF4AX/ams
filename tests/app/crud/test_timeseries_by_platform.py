import pytest

from app.crud import timeseries as ts
from datetime import datetime, timedelta, date, time as dt_time


@pytest.fixture
def two_day_platform_setup(db_session, sample_data_factory):
    """Build two days of data across two platforms with revision semantics."""

    def _midnight(days_ago: int) -> datetime:
        return datetime.combine(date.today() - timedelta(days=days_ago), dt_time.min)

    d2, d1 = _midnight(2), _midnight(1)
    p1 = sample_data_factory.platform(name="Upbit")
    p2 = sample_data_factory.platform(name="Binance")

    # d2: latest revisions summed
    sample_data_factory.daily_metric(
        platform=p1, symbol="BTC", revision=1, after_value_krw=10.0, created_at=d2
    )
    sample_data_factory.daily_metric(
        platform=p1, symbol="BTC", revision=2, after_value_krw=20.0, created_at=d2
    )
    sample_data_factory.daily_metric(
        platform=p2, symbol="TSLA", revision=1, after_value_krw=30.0, created_at=d2
    )

    # d1: latest only
    sample_data_factory.daily_metric(
        platform=p1, symbol="BTC", revision=2, after_value_krw=40.0, created_at=d1
    )
    sample_data_factory.daily_metric(
        platform=p1, symbol="BTC", revision=3, after_value_krw=50.0, created_at=d1
    )
    sample_data_factory.daily_metric(
        platform=p2, symbol="TSLA", revision=3, after_value_krw=60.0, created_at=d1
    )

    db_session.commit()
    return {"dates": (d2.date(), d1.date()), "platforms": (p1.name, p2.name)}


def test_by_platform_latest_and_sorted(db_session, two_day_platform_setup):
    d2, d1 = two_day_platform_setup["dates"]
    p1, p2 = two_day_platform_setup["platforms"]

    rows = ts.get_portfolio_timeseries_by_platform(db_session, days=30)
    got = [(r["date"], r["platform"], r["total_krw"]) for r in rows]
    # Query orders by day, then Platform.name ascending: Binance, Upbit
    expected = [
        (d2, p2, pytest.approx(30.0)),
        (d2, p1, pytest.approx(20.0)),
        (d1, p2, pytest.approx(60.0)),
        (d1, p1, pytest.approx(50.0)),
    ]
    assert got == expected


def test_by_platform_cutoff_days(db_session, two_day_platform_setup):
    d2, d1 = two_day_platform_setup["dates"]
    p1, p2 = two_day_platform_setup["platforms"]

    rows = ts.get_portfolio_timeseries_by_platform(db_session, days=1)
    assert {(r["date"], r["platform"]) for r in rows} == {(d1, p1), (d1, p2)}


def test_by_platform_excludes_nulls(db_session, sample_data_factory):
    today = datetime.combine(date.today(), dt_time.min)
    p1 = sample_data_factory.platform(name="Upbit")
    # One None entry should be excluded from the sum
    sample_data_factory.daily_metric(
        platform=p1, symbol="A", revision=1, after_value_krw=None, created_at=today
    )
    sample_data_factory.daily_metric(
        platform=p1, symbol="B", revision=1, after_value_krw=123.0, created_at=today
    )
    db_session.commit()

    rows = ts.get_portfolio_timeseries_by_platform(db_session, days=7)
    assert len(rows) == 1
    assert rows[0]["platform"] == "Upbit"
    assert rows[0]["total_krw"] == pytest.approx(123.0)


@pytest.mark.parametrize("func", [ts.get_portfolio_timeseries, ts.get_portfolio_timeseries_by_platform])
@pytest.mark.parametrize("days", [0, -1])
def test_days_non_positive_returns_empty(db_session, func, days):
    assert func(db_session, days=days) == []


def test_by_platform_returns_date_objects(db_session, sample_data_factory):
    # Ensure 'date' field is a date object even if backend returns strings
    today = datetime.combine(date.today(), dt_time.min)
    p1 = sample_data_factory.platform(name="Upbit")
    sample_data_factory.daily_metric(
        platform=p1, symbol="X", revision=1, after_value_krw=1.0, created_at=today
    )
    db_session.commit()

    rows = ts.get_portfolio_timeseries_by_platform(db_session, days=1)
    assert all(isinstance(r["date"], date) for r in rows)
