import pytest

from app.crud import crud
from models.models import AssetCategory


def _create_platform_and_asset(db_session):
    platform = crud.create_platform(db_session, name="Upbit", category="거래소")
    asset = crud.create_asset(
        db_session,
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
    "transaction_type,fx,price,qty,expected_flow",
    [
        ("입금", 1.0, 1.0, 1000.0, 1000.0),
        ("입금", 1200.0, 1.0, 1.0, 1200.0),
        ("출금", 1400.0, 1.0, 2.0, -2800.0),
        ("입금", None, 1.0, 100.0, None),  # 환율 미제공 → 미계산
        ("매수", 1000.0, 1.0, 10.0, None),  # 입출금 외 유형 → 미계산
    ],
)
def test_create_transaction_flow_krw_calculation(
    db_session, transaction_type, fx, price, qty, expected_flow
):
    _, asset = _create_platform_and_asset(db_session)

    tx = crud.create_transaction(
        db_session,
        asset_id=asset.id,
        transaction_type=transaction_type,
        price=price,
        quantity=qty,
        flow_fx_to_krw=fx,
    )

    assert tx.amount == pytest.approx(price * qty)

    if fx is None:
        assert tx.flow_fx_to_krw is None
    else:
        assert tx.flow_fx_to_krw == pytest.approx(fx)

    if expected_flow is None:
        assert tx.flow_amount_krw is None
    else:
        assert tx.flow_amount_krw == pytest.approx(expected_flow)
