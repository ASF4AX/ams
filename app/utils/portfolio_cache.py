from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


SEOUL_TZ = ZoneInfo("Asia/Seoul")
MDD_NOTE = "API 원시 MDD는 결측 보정 이력으로 장기 판단 불가"


def _krw_int(value: Any) -> int:
    return int(round(float(value or 0)))


def _pct(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _iso_now() -> str:
    return datetime.now(SEOUL_TZ).isoformat(timespec="seconds")


def _cost_basis_krw(asset: dict[str, Any], value_krw: int) -> int | None:
    avg_price = asset.get("avg_price")
    quantity = asset.get("quantity")
    evaluation_amount = asset.get("evaluation_amount")
    if avg_price is None or not quantity or not evaluation_amount:
        return None
    fx_rate = float(asset.get("eval_amount_krw") or 0) / float(evaluation_amount)
    return _krw_int(float(avg_price) * float(quantity) * fx_rate)


def build_portfolio_cache(
    *,
    summary: dict[str, Any],
    current_assets: list[dict[str, Any]],
    return_7d: dict[str, Any],
    return_30d: dict[str, Any],
    mdd_30d: dict[str, Any],
    as_of: str | None = None,
    source: str = "AMS API @ http://replace-me:8003",
) -> dict[str, Any]:
    positions = []
    total_assets_krw = _krw_int(summary.get("total_krw"))
    total_cost_krw = 0
    total_unrealized_pnl_krw = 0

    for asset in sorted(
        current_assets,
        key=lambda row: float(row.get("eval_amount_krw") or 0),
        reverse=True,
    ):
        value_krw = _krw_int(asset.get("eval_amount_krw"))
        if value_krw <= 0:
            continue
        cost_basis_krw = _cost_basis_krw(asset, value_krw)
        unrealized_pnl_krw = None
        return_pct = None
        if cost_basis_krw is not None:
            unrealized_pnl_krw = value_krw - cost_basis_krw
            if cost_basis_krw > 0:
                return_pct = round((unrealized_pnl_krw / cost_basis_krw) * 100, 2)
            total_cost_krw += cost_basis_krw
            total_unrealized_pnl_krw += unrealized_pnl_krw
        weight_pct = None
        if total_assets_krw > 0:
            weight_pct = round((value_krw / total_assets_krw) * 100, 2)
        positions.append(
            {
                "ticker": asset.get("symbol"),
                "name": asset.get("name"),
                "platform": asset.get("platform"),
                "asset_class": asset.get("category"),
                "shares": float(asset.get("quantity") or 0),
                "value_krw": value_krw,
                "weight_pct": weight_pct,
                "cost_basis_krw": cost_basis_krw,
                "avg_price": asset.get("avg_price"),
                "unrealized_pnl_krw": unrealized_pnl_krw,
                "return_pct": return_pct,
            }
        )

    total_return_pct = None
    if total_cost_krw > 0:
        total_return_pct = round((total_unrealized_pnl_krw / total_cost_krw) * 100, 2)

    return {
        "as_of": as_of or _iso_now(),
        "source": source,
        "base_currency": "KRW",
        "summary": {
            "as_of_date": summary.get("as_of"),
            "total_assets_krw": total_assets_krw,
            "item_count": len(positions),
            "total_cost_krw": total_cost_krw or None,
            "total_unrealized_pnl_krw": total_unrealized_pnl_krw
            if total_cost_krw > 0
            else None,
            "total_return_pct": total_return_pct,
        },
        "returns": {
            "d7_pct": _pct(return_7d.get("return_rate_pct")),
            "d30_pct": _pct(return_30d.get("return_rate_pct")),
        },
        "mdd": {
            "measured_30d_pct": _pct(mdd_30d.get("maximum_drawdown_pct")),
            "api_raw_pct": None,
            "note": MDD_NOTE,
        },
        "by_platform": [
            {
                "platform": row.get("platform"),
                "value_krw": _krw_int(row.get("amount_krw")),
            }
            for row in summary.get("by_platform", [])
        ],
        "by_asset_class": [
            {
                "class": row.get("category"),
                "value_krw": _krw_int(row.get("amount_krw")),
            }
            for row in summary.get("by_category", [])
        ],
        "positions": positions,
    }
