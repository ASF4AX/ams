from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.models import Asset, DailyAssetMetrics, Platform, Transaction
from .timeseries import get_portfolio_timeseries


def get_daily_metrics_for_api(
    db: Session,
    *,
    days: int,
    platform: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Return daily metrics shaped for read-only API responses."""
    cutoff = datetime.now() - timedelta(days=days)
    query = (
        db.query(DailyAssetMetrics, Platform.name)
        .join(Platform, Platform.id == DailyAssetMetrics.platform_id)
        .filter(DailyAssetMetrics.created_at >= cutoff)
    )
    if platform:
        query = query.filter(Platform.name == platform)

    rows = (
        query.order_by(DailyAssetMetrics.created_at.desc(), DailyAssetMetrics.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": metric.id,
            "platform": platform_name,
            "exchange": metric.exchange,
            "symbol": metric.symbol,
            "revision": metric.revision,
            "before_value": metric.before_value,
            "after_value": metric.after_value,
            "change_amount": metric.change_amount,
            "return_rate": metric.return_rate,
            "before_value_krw": metric.before_value_krw,
            "after_value_krw": metric.after_value_krw,
            "change_amount_krw": metric.change_amount_krw,
            "return_rate_krw": metric.return_rate_krw,
            "created_at": metric.created_at,
        }
        for metric, platform_name in rows
    ]


def get_transactions_for_api(
    db: Session,
    *,
    days: int,
    transaction_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return transactions with asset/platform context for read-only API responses."""
    cutoff = datetime.now() - timedelta(days=days)
    query = (
        db.query(Transaction, Asset, Platform)
        .outerjoin(Asset, Asset.id == Transaction.asset_id)
        .outerjoin(Platform, Platform.id == Asset.platform_id)
        .filter(Transaction.transaction_date >= cutoff)
    )
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)

    rows = (
        query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": transaction.id,
            "asset_id": transaction.asset_id,
            "asset_symbol": asset.symbol if asset else None,
            "asset_name": asset.name if asset else None,
            "platform": platform.name if platform else None,
            "transaction_type": transaction.transaction_type,
            "price": transaction.price,
            "quantity": transaction.quantity,
            "amount": transaction.amount,
            "flow_amount_krw": transaction.flow_amount_krw,
            "flow_fx_to_krw": transaction.flow_fx_to_krw,
            "memo": transaction.memo,
            "transaction_date": transaction.transaction_date,
        }
        for transaction, asset, platform in rows
    ]


def get_portfolio_mdd(db: Session, *, days: int) -> dict:
    """Calculate maximum drawdown over the portfolio total-value series."""
    series = get_portfolio_timeseries(db, days=days)
    if not series:
        return {
            "days": days,
            "currency": "KRW",
            "maximum_drawdown_pct": None,
            "peak_date": None,
            "trough_date": None,
            "peak_value_krw": None,
            "trough_value_krw": None,
        }

    peak_value = float(series[0]["total_krw"])
    peak_date = series[0]["date"]
    max_drawdown_pct = 0.0
    mdd_peak_date = peak_date
    mdd_peak_value = peak_value
    trough_date = peak_date
    trough_value = peak_value

    for point in series:
        value = float(point["total_krw"])
        point_date = point["date"]
        if value > peak_value:
            peak_value = value
            peak_date = point_date
        if peak_value <= 0:
            continue

        drawdown_pct = ((value / peak_value) - 1.0) * 100.0
        if drawdown_pct < max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
            mdd_peak_date = peak_date
            mdd_peak_value = peak_value
            trough_date = point_date
            trough_value = value

    return {
        "days": days,
        "currency": "KRW",
        "maximum_drawdown_pct": max_drawdown_pct,
        "peak_date": mdd_peak_date,
        "trough_date": trough_date,
        "peak_value_krw": mdd_peak_value,
        "trough_value_krw": trough_value,
    }
