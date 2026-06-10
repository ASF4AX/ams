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

    for asset in sorted(
        current_assets,
        key=lambda row: float(row.get("eval_amount_krw") or 0),
        reverse=True,
    ):
        value_krw = _krw_int(asset.get("eval_amount_krw"))
        if value_krw <= 0:
            continue
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
            }
        )

    return {
        "as_of": as_of or _iso_now(),
        "source": source,
        "base_currency": "KRW",
        "summary": {
            "as_of_date": summary.get("as_of"),
            "total_assets_krw": total_assets_krw,
            "item_count": len(positions),
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
