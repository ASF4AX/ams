from datetime import datetime, timedelta, date, time as dt_time

import pytest

from app.crud import crud
from models.models import (
    Asset,
    AssetCategory,
    DailyAssetMetrics,
    Transaction,
)


def _create_platform(session, name="Binance", category="거래소"):
    return crud.create_platform(session, name=name, category=category)


def _create_asset(
    session,
    platform_id,
    name="Bitcoin",
    symbol="BTC",
    category=AssetCategory.CRYPTO.value,
    current_price=100.0,
    quantity=2.0,
    revision=1,
):
    return crud.create_asset(
        session,
        name=name,
        symbol=symbol,
        category=category,
        platform_id=platform_id,
        current_price=current_price,
        quantity=quantity,
        revision=revision,
    )


def _set_eval_amount(asset: Asset, amount: float, session):
    asset.eval_amount_krw = amount
    session.add(asset)
    session.commit()


def test_create_and_get_platform_by_name(db_session):
    platform = crud.create_platform(db_session, name="Upbit", category="거래소")

    fetched = crud.get_platform_by_name(db_session, "Upbit")

    assert platform.id == fetched.id
    assert fetched.category == "거래소"


def test_create_asset_sets_evaluation_and_revision(db_session):
    platform = _create_platform(db_session)

    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        current_price=250.0,
        quantity=1.5,
        revision=3,
    )

    assert asset.evaluation_amount == pytest.approx(375.0)
    assert asset.revision == 3
    assert asset.platform_id == platform.id


def test_get_all_assets_returns_latest_revision_per_platform(db_session):
    platform = _create_platform(db_session)
    old_asset = _create_asset(
        db_session,
        platform_id=platform.id,
        name="Bitcoin",
        symbol="BTC",
        revision=1,
    )
    latest_asset = _create_asset(
        db_session,
        platform_id=platform.id,
        name="Bitcoin",
        symbol="BTC",
        revision=2,
    )
    other_platform = _create_platform(db_session, name="Coinbase")
    other_asset = _create_asset(
        db_session,
        platform_id=other_platform.id,
        name="Ethereum",
        symbol="ETH",
        revision=1,
    )

    assets = crud.get_all_assets(db_session)

    assert {asset.id for asset in assets} == {latest_asset.id, other_asset.id}
    assert old_asset.id not in {asset.id for asset in assets}


def test_update_asset_recalculates_evaluation_amount(db_session):
    platform = _create_platform(db_session)
    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        current_price=100.0,
        quantity=2.0,
    )

    updated = crud.update_asset(
        db_session,
        asset.id,
        current_price=200.0,
        quantity=3.0,
    )

    assert updated.evaluation_amount == pytest.approx(600.0)
    assert updated.quantity == pytest.approx(3.0)


def test_create_transaction_updates_asset_quantity(db_session):
    platform = _create_platform(db_session)
    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        current_price=100.0,
        quantity=10.0,
    )

    buy_tx = crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=50.0,
        quantity=5.0,
        transaction_date=datetime(2023, 1, 1),
    )
    sell_tx = crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매도",
        price=70.0,
        quantity=3.0,
        transaction_date=datetime(2023, 1, 2),
    )

    refreshed_asset = crud.get_asset_by_id(db_session, asset.id)
    assert isinstance(buy_tx, Transaction)
    assert isinstance(sell_tx, Transaction)
    assert refreshed_asset.quantity == pytest.approx(12.0)


def test_get_all_transactions_applies_order_limit_offset(db_session):
    platform = _create_platform(db_session)
    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        quantity=50.0,
    )

    crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=10.0,
        quantity=1.0,
        transaction_date=datetime(2023, 1, 1),
    )
    middle_tx = crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=12.0,
        quantity=1.0,
        transaction_date=datetime(2023, 2, 1),
    )
    crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=14.0,
        quantity=1.0,
        transaction_date=datetime(2023, 3, 1),
    )

    results = crud.get_all_transactions(db_session, skip=1, limit=1)

    assert len(results) == 1
    assert results[0].id == middle_tx.id


def test_get_recent_transactions_filters_by_days(db_session):
    platform = _create_platform(db_session)
    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        quantity=20.0,
    )

    within_range = crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=10.0,
        quantity=1.0,
        transaction_date=datetime.now() - timedelta(days=1),
    )
    crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type="매수",
        price=10.0,
        quantity=1.0,
        transaction_date=datetime.now() - timedelta(days=30),
    )

    recent_transactions = crud.get_recent_transactions(db_session, days=7)

    assert [tx.id for tx in recent_transactions] == [within_range.id]


def test_get_total_asset_value_aggregates_latest_revisions(db_session):
    platform1 = _create_platform(db_session, name="Binance")
    platform2 = _create_platform(db_session, name="Upbit")

    old_asset = _create_asset(
        db_session,
        platform_id=platform1.id,
        revision=1,
    )
    latest_asset = _create_asset(
        db_session,
        platform_id=platform1.id,
        revision=2,
    )
    other_asset = _create_asset(
        db_session,
        platform_id=platform2.id,
        revision=1,
    )

    _set_eval_amount(old_asset, 100.0, db_session)
    _set_eval_amount(latest_asset, 250.0, db_session)
    _set_eval_amount(other_asset, 300.0, db_session)

    total_value = crud.get_total_asset_value(db_session)

    assert total_value == pytest.approx(250.0 + 300.0)


def test_get_daily_change_percentage_uses_latest_metrics(db_session):
    platform = _create_platform(db_session)

    metric_rev1 = DailyAssetMetrics(
        platform_id=platform.id,
        revision=1,
        before_value_krw=100.0,
        after_value_krw=110.0,
    )
    metric_rev2 = DailyAssetMetrics(
        platform_id=platform.id,
        revision=2,
        before_value_krw=200.0,
        after_value_krw=260.0,
    )
    db_session.add_all([metric_rev1, metric_rev2])
    db_session.commit()

    change_percentage = crud.get_daily_change_percentage(db_session)

    expected = ((260.0 - 200.0) / 200.0) * 100
    assert change_percentage == pytest.approx(expected)


def test_get_asset_distribution_by_category_excludes_zero_amounts(db_session):
    platform = _create_platform(db_session)

    latest_crypto = _create_asset(
        db_session,
        platform_id=platform.id,
        category=AssetCategory.CRYPTO.value,
        revision=2,
    )
    zero_amount_asset = _create_asset(
        db_session,
        platform_id=platform.id,
        category=AssetCategory.STABLE_COIN.value,
        revision=2,
        symbol="USDT",
    )

    _set_eval_amount(latest_crypto, 500.0, db_session)
    _set_eval_amount(zero_amount_asset, 0.0, db_session)

    distribution = crud.get_asset_distribution_by_category(db_session)

    assert distribution == [{"category": AssetCategory.CRYPTO.value, "amount": 500.0}]


def test_get_asset_distribution_by_platform(db_session):
    binance = _create_platform(db_session, name="Binance")
    upbit = _create_platform(db_session, name="Upbit")

    binance_asset = _create_asset(
        db_session,
        platform_id=binance.id,
        symbol="BTC",
        revision=2,
    )
    upbit_asset = _create_asset(
        db_session,
        platform_id=upbit.id,
        symbol="ETH",
        revision=1,
    )

    _set_eval_amount(binance_asset, 400.0, db_session)
    _set_eval_amount(upbit_asset, 600.0, db_session)

    distribution = crud.get_asset_distribution_by_platform(db_session)

    assert sorted(distribution, key=lambda item: item["platform"]) == [
        {"platform": "Binance", "amount": 400.0},
        {"platform": "Upbit", "amount": 600.0},
    ]


@pytest.fixture
def two_day_timeseries_setup(db_session, sample_data_factory):
    # Arrange: build two-day scenario at midnight (date-only semantics)
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
    series = crud.get_portfolio_timeseries(db_session, days=30)

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
    series = crud.get_portfolio_timeseries(db_session, days=days)
    assert [row["date"] for row in series] == expected_dates(two_days_ago, one_day_ago)


def test_stable_coin_crud_flow(db_session):
    crud.create_stable_coin(db_session, symbol="USDT")

    retrieved = crud.get_stable_coin_by_symbol(db_session, "USDT")
    assert retrieved is not None
    assert retrieved.is_active is True

    active_coins = crud.get_active_stable_coins(db_session)
    assert [coin.symbol for coin in active_coins] == ["USDT"]

    updated = crud.update_stable_coin_status(db_session, "USDT", False)
    assert updated is True
    assert crud.get_active_stable_coins(db_session) == []

    deleted = crud.delete_stable_coin(db_session, "USDT")
    assert deleted is True
    assert crud.get_stable_coin_by_symbol(db_session, "USDT") is None


def test_get_latest_cash_equivalent_annual_interest_info(db_session):
    platform = _create_platform(db_session)
    asset = _create_asset(
        db_session,
        platform_id=platform.id,
        symbol="USDT",
        category=AssetCategory.STABLE_COIN.value,
        revision=1,
    )

    metric = DailyAssetMetrics(
        platform_id=platform.id,
        symbol="USDT",
        revision=1,
        return_rate=0.01,
    )
    db_session.add(metric)
    db_session.commit()

    results = crud.get_latest_cash_equivalent_annual_interest_info(db_session)

    assert results == [
        {
            "platform_name": platform.name,
            "symbol": "USDT",
            "category": AssetCategory.STABLE_COIN.value,
            "exchange": asset.exchange,
            "annual_yield_decimal": pytest.approx(0.01 * 365),
        }
    ]
