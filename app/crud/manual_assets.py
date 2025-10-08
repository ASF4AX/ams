from __future__ import annotations

from enum import Enum
from models.models import Asset
from sqlalchemy.orm import Session
from typing import List, Optional, Dict

from .crud import (
    get_platform_by_name,
    create_platform,
    get_assets_by_platform,
    get_exchange_rates_to_krw,
)


MANUAL_PLATFORM_NAME = "수동등록"
MANUAL_PLATFORM_CATEGORY = "기타"
MANUAL_REVISION = 1


class Col(str, Enum):
    ID = "ID"
    NAME = "이름"
    SYMBOL = "심볼"
    CATEGORY = "카테고리"
    CURRENCY = "통화"
    PRICE = "가격"
    QTY = "수량"
    EXCHANGE = "거래소"
    EVAL_KRW = "평가금액(KRW)"
    UPDATED_AT = "수정일"


def get_manual_assets(db: Session) -> List[Asset]:
    """Return latest assets for the manual platform."""
    platform = _ensure_manual_platform(db)
    return get_assets_by_platform(db, platform.id)


def apply_manual_assets_state(
    db: Session,
    *,
    state: Optional[dict],
) -> None:
    """Apply editor state atomically and manage commit/rollback internally.

    Expected state schema (from UI):
    - deleted_ids: list[int]
    - edited_by_id: dict[str|int, dict]
    - added_rows: list[dict]
    Raises on any validation or DB error; the session is rolled back.
    """

    editor_state: Dict = state or {}
    platform = _ensure_manual_platform(db)
    rates = get_exchange_rates_to_krw(db)

    try:
        deleted_ids = editor_state.get("deleted_ids")
        if deleted_ids:
            targets = db.query(Asset).filter(Asset.id.in_(deleted_ids)).all()
            for t in targets:
                db.delete(t)

        edited_by_id = editor_state.get("edited_by_id")
        if edited_by_id:
            ids = [int(k) for k in edited_by_id.keys()]
            assets_map = {
                a.id: a for a in db.query(Asset).filter(Asset.id.in_(ids)).all()
            }
            for sid, change in edited_by_id.items():
                aid = int(sid)
                a = assets_map.get(aid)
                if not a:
                    continue
                if Col.NAME in change:
                    a.name = _norm_str(change[Col.NAME])
                if Col.SYMBOL in change:
                    a.symbol = _norm_str(change[Col.SYMBOL])
                if Col.CATEGORY in change:
                    a.category = _norm_str(change[Col.CATEGORY])
                if Col.EXCHANGE in change:
                    a.exchange = _norm_str(change[Col.EXCHANGE]) or None
                if Col.CURRENCY in change:
                    a.currency = _norm_upper(change[Col.CURRENCY])
                if Col.PRICE in change:
                    a.current_price = _norm_float(change[Col.PRICE])
                if Col.QTY in change:
                    a.quantity = _norm_float(change[Col.QTY])

                ev, ev_krw = _compute_amounts(
                    a.current_price, a.quantity, a.currency, rates
                )
                a.evaluation_amount = ev
                a.eval_amount_krw = ev_krw

        inserts: List[Dict] = []
        for row in editor_state.get("added_rows", []):
            name = _norm_str(row.get(Col.NAME))
            symbol = _norm_str(row.get(Col.SYMBOL))
            category = _norm_str(row.get(Col.CATEGORY))
            exchange = _norm_str(row.get(Col.EXCHANGE)) or None
            currency = _norm_upper(row.get(Col.CURRENCY))
            price = _norm_float(row.get(Col.PRICE))
            qty = _norm_float(row.get(Col.QTY))
            if not any([name, symbol, category, exchange, currency, price, qty]):
                raise ValueError("빈 행은 저장할 수 없습니다.")
            if qty <= 0 or price < 0:
                raise ValueError("가격은 >= 0, 수량은 > 0 이어야 합니다.")
            evaluation_amount, eval_amount_krw = _compute_amounts(
                price, qty, currency, rates
            )
            inserts.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "category": category,
                    "platform_id": platform.id,
                    "current_price": price,
                    "quantity": qty,
                    "currency": currency,
                    "exchange": exchange,
                    "evaluation_amount": evaluation_amount,
                    "eval_amount_krw": eval_amount_krw,
                    "revision": MANUAL_REVISION,
                }
            )
        if inserts:
            db.bulk_insert_mappings(Asset, inserts)

        db.commit()
    except Exception:
        db.rollback()
        raise


# Internal helpers


def _norm_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _norm_upper(val) -> Optional[str]:
    s = _norm_str(val)
    return s.upper() if s else None


def _norm_float(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def _ensure_manual_platform(db: Session):
    """Return the manual platform, creating it if missing (internal)."""
    platform = get_platform_by_name(db, MANUAL_PLATFORM_NAME)
    if platform is None:
        platform = create_platform(
            db, name=MANUAL_PLATFORM_NAME, category=MANUAL_PLATFORM_CATEGORY
        )
    return platform


def _compute_amounts(
    price: Optional[float],
    qty: Optional[float],
    currency: Optional[str],
    rates: Dict[str, float],
) -> tuple[float, Optional[float]]:
    """Compute evaluation_amount and KRW-converted amount.

    - Handles None price/qty as 0.0
    - Upper-cases currency if string
    - If FX rate is missing/unknown, KRW amount is None (unknown)
    """
    p = price or 0.0
    q = qty or 0.0
    evaluation_amount = p * q
    cur = currency.upper() if isinstance(currency, str) else currency
    rate = rates.get(cur) if cur else None
    eval_amount_krw: Optional[float]
    if rate is None:
        eval_amount_krw = None
    else:
        eval_amount_krw = evaluation_amount * float(rate)
    return evaluation_amount, eval_amount_krw
