from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.models import DailyAssetMetrics, Platform


def _compute_cutoff_and_day_expr(days: int):
    """Return cutoff date and SQLAlchemy day expression for created_at.

    Using a dedicated helper keeps the cutoff anchor logic consistent across
    aggregation variants (total vs. per-platform) and avoids drift.
    """
    anchor = datetime.now()
    cutoff_date = (anchor - timedelta(days=days)).date()
    day_expr = func.date(DailyAssetMetrics.created_at)
    return cutoff_date, day_expr


def _latest_revision_per_day_subquery(db: Session, *, cutoff_date, day_expr):
    """Build subquery selecting the latest revision per (platform, day).

    This captures the intended semantics of "latest revision snapshot per day"
    regardless of future revision-policy changes.
    """
    return (
        db.query(
            DailyAssetMetrics.platform_id.label("platform_id"),
            day_expr.label("day"),
            func.max(DailyAssetMetrics.revision).label("latest_revision"),
        )
        .filter(day_expr >= cutoff_date)
        .group_by(DailyAssetMetrics.platform_id, day_expr)
        .subquery()
    )


def _to_date(day) -> datetime.date:
    """Normalize DB-returned day into a date instance.

    SQLite returns strings for func.date, while PostgreSQL may return datetime/date.
    This helper keeps result-shaping uniform across backends.
    """
    if isinstance(day, str):
        return datetime.fromisoformat(day).date()
    if isinstance(day, datetime):
        return day.date()
    return day


def get_portfolio_timeseries(db: Session, days: int = 30) -> list[dict]:
    """일자별 총 자산 가치(원화) 시계열을 반환합니다."""

    if days <= 0:
        return []

    # 캘린더 일자 기준 컷오프(오늘로부터 N일 전의 '날짜')
    cutoff_date, day_expr = _compute_cutoff_and_day_expr(days)

    latest_revision_per_day = _latest_revision_per_day_subquery(
        db, cutoff_date=cutoff_date, day_expr=day_expr
    )

    # 날짜(day) 일치 조건은 현재 리비전 정책(플랫폼별 전역 증가)하에서는
    # 기능상 중복이지만, '해당 일자의 최신 리비전'이라는 의도를 명확히 하고
    # 향후 리비전 정책 변경/백필 등에도 안전하도록 유지합니다.
    query = (
        db.query(
            latest_revision_per_day.c.day.label("day"),
            func.sum(DailyAssetMetrics.after_value_krw).label("total_krw"),
        )
        .join(
            DailyAssetMetrics,
            (DailyAssetMetrics.platform_id == latest_revision_per_day.c.platform_id)
            & (func.date(DailyAssetMetrics.created_at) == latest_revision_per_day.c.day)
            & (DailyAssetMetrics.revision == latest_revision_per_day.c.latest_revision),
        )
        .filter(DailyAssetMetrics.after_value_krw.isnot(None))
        .group_by(latest_revision_per_day.c.day)
        .order_by(latest_revision_per_day.c.day)
    )

    results: list[dict] = []
    for day, total in query.all():
        if total is None:
            continue
        results.append({"date": _to_date(day), "total_krw": float(total)})

    return results


def get_portfolio_timeseries_by_platform(db: Session, days: int = 30) -> list[dict]:
    """일자별·플랫폼별 자산 가치(원화) 시계열을 반환합니다.

    반환 형식:
    [{"date": date, "platform": Platform.name, "total_krw": float}, ...]
    """
    if days <= 0:
        return []

    cutoff_date, day_expr = _compute_cutoff_and_day_expr(days)

    latest_revision_per_day = _latest_revision_per_day_subquery(
        db, cutoff_date=cutoff_date, day_expr=day_expr
    )

    query = (
        db.query(
            latest_revision_per_day.c.day.label("day"),
            Platform.name.label("platform_name"),
            func.sum(DailyAssetMetrics.after_value_krw).label("total_krw"),
        )
        .join(
            DailyAssetMetrics,
            (DailyAssetMetrics.platform_id == latest_revision_per_day.c.platform_id)
            & (func.date(DailyAssetMetrics.created_at) == latest_revision_per_day.c.day)
            & (DailyAssetMetrics.revision == latest_revision_per_day.c.latest_revision),
        )
        .join(Platform, Platform.id == DailyAssetMetrics.platform_id)
        .filter(DailyAssetMetrics.after_value_krw.isnot(None))
        .group_by(latest_revision_per_day.c.day, Platform.name)
        .order_by(latest_revision_per_day.c.day, Platform.name)
    )

    results: list[dict] = []
    for day, platform_name, total in query.all():
        if total is None:
            continue
        results.append(
            {"date": _to_date(day), "platform": platform_name, "total_krw": float(total)}
        )

    return results
