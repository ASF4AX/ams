from __future__ import annotations

import math
import pytest

from sqlalchemy.orm import Session
from app.crud.manual_assets import apply_manual_assets_state, _compute_amounts
from app.crud.crud import get_assets_by_platform
from models.models import Asset


def test_get_assets_by_platform_empty(db_session: Session, sample_data_factory) -> None:
    platform = sample_data_factory.platform(name="수동등록")
    assets = get_assets_by_platform(db_session, platform.id)
    assert assets == []


def test_upsert_creates_new_asset_with_usd_conversion(
    db_session: Session, sample_data_factory
) -> None:
    platform = sample_data_factory.platform(name="수동등록")
    # USD -> KRW 환율 1300
    sample_data_factory.exchange_rate(
        base_currency="USD", target_currency="KRW", rate=1300.0
    )

    state = {
        "edited_rows": {},
        "added_rows": [
            {
                "이름": "Bitcoin",
                "심볼": "BTC",
                "카테고리": "암호화폐",
                "통화": "USD",
                "가격": 70000.0,
                "수량": 0.5,
                "거래소": "Manual",
            }
        ],
        "deleted_rows": [],
    }

    apply_manual_assets_state(db_session, state=state)

    assets = db_session.query(Asset).filter(Asset.platform_id == platform.id).all()
    assert len(assets) == 1
    a = assets[0]
    assert a.name == "Bitcoin"
    assert a.symbol == "BTC"
    assert a.category == "암호화폐"
    assert a.currency == "USD"
    assert math.isclose(a.evaluation_amount, 70000.0 * 0.5)
    assert math.isclose(a.eval_amount_krw, (70000.0 * 0.5) * 1300.0)
    assert a.revision == 1


def test_upsert_updates_existing_asset(
    db_session: Session, sample_data_factory
) -> None:
    platform = sample_data_factory.platform(name="수동등록")
    asset = sample_data_factory.asset(
        platform=platform,
        name="Cash",
        symbol="KRW",
        category="현금",
        current_price=1.0,
        quantity=1000.0,
        revision=1,
        currency="KRW",
    )

    state = {
        "edited_by_id": {str(asset.id): {"수량": 2000.0}},
        "added_rows": [],
        "deleted_ids": [],
    }

    apply_manual_assets_state(db_session, state=state)

    refreshed = db_session.query(Asset).filter(Asset.id == asset.id).first()
    assert refreshed.quantity == pytest.approx(2000.0)
    assert refreshed.evaluation_amount == pytest.approx(2000.0)
    assert refreshed.eval_amount_krw == pytest.approx(2000.0)


def test_upsert_deletes_via_deleted_rows_state(
    db_session: Session, sample_data_factory
) -> None:
    platform = sample_data_factory.platform(name="수동등록")
    a1 = sample_data_factory.asset(platform=platform, name="A", symbol="A", revision=1)
    a2 = sample_data_factory.asset(platform=platform, name="B", symbol="B", revision=1)

    state = {"edited_by_id": {}, "added_rows": [], "deleted_ids": [a1.id]}

    apply_manual_assets_state(db_session, state=state)
    remaining = db_session.query(Asset).filter(Asset.platform_id == platform.id).all()
    assert len(remaining) == 1
    assert remaining[0].id == a2.id
    assert remaining[0].symbol == "B"


def test_upsert_skips_empty_new_row(db_session: Session, sample_data_factory) -> None:
    platform = sample_data_factory.platform(name="수동등록")

    state = {"edited_rows": {}, "added_rows": [{}], "deleted_rows": []}

    with pytest.raises(ValueError):
        apply_manual_assets_state(db_session, state=state)


@pytest.mark.parametrize(
    "price,qty,currency,rates,ev,ev_krw",
    [
        (10.0, 2.0, "KRW", {"KRW": 1.0, "USD": 1300.0}, 20.0, 20.0),
        (1.5, 2.0, "usd", {"KRW": 1.0, "USD": 1300.0}, 3.0, 3.0 * 1300.0),
        (5.0, 2.0, "ABC", {"KRW": 1.0}, 10.0, None),
        (None, None, None, {"KRW": 1.0}, 0.0, None),
    ],
)
def test_compute_amounts_cases(price, qty, currency, rates, ev, ev_krw):
    out_ev, out_krw = _compute_amounts(price, qty, currency, rates)
    assert out_ev == pytest.approx(ev)
    if ev_krw is None:
        assert out_krw is None
    else:
        assert out_krw == pytest.approx(ev_krw)
