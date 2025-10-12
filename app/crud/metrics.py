from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.models import DailyAssetMetrics, Transaction
from .crud import get_total_asset_value


def get_portfolio_period_return(
    db: Session, days: int, *, reflect_flows: bool = False
) -> float | None:
    """
    최근 N일 구간 수익률(%)을 계산합니다.
    - 과거값: cutoff_date(오늘-N일) 이후의 첫 달력 일자 1일만 사용
    - 집계: 해당 일자의 플랫폼별 최신 리비전 after_value_krw 합계
    - 현재값: get_total_asset_value 스냅샷 합계
    """
    if days <= 0:
        return None

    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    day_expr = func.date(DailyAssetMetrics.created_at)

    # cutoff 이후(포함) 중 가장 이른 날짜를 하나만 선택
    target_day = (
        db.query(func.min(day_expr)).filter(day_expr >= cutoff_date).scalar_subquery()
    )

    # 후보 날짜의 플랫폼별 최신 리비전을 합산하여 과거 총액 계산
    latest_rev = (
        db.query(
            DailyAssetMetrics.platform_id.label("pid"),
            func.max(DailyAssetMetrics.revision).label("rev"),
        )
        .filter(func.date(DailyAssetMetrics.created_at) == target_day)
        .group_by(DailyAssetMetrics.platform_id)
        .subquery()
    )

    past_total = (
        db.query(func.sum(DailyAssetMetrics.after_value_krw))
        .join(
            latest_rev,
            (DailyAssetMetrics.platform_id == latest_rev.c.pid)
            & (DailyAssetMetrics.revision == latest_rev.c.rev),
        )
        .filter(func.date(DailyAssetMetrics.created_at) == target_day)
        .filter(DailyAssetMetrics.after_value_krw.isnot(None))
        .scalar()
    ) or 0.0

    if past_total <= 0:
        return None

    current_total = float(get_total_asset_value(db) or 0.0)

    if reflect_flows:
        # 기간 내 순입출금(입금+/출금−)을 현재값에서 제외, 경계일 보정: (cutoff_date, today]
        sum_flow = (
            db.query(func.sum(Transaction.flow_amount_krw))
            .filter(Transaction.flow_amount_krw.isnot(None))
            .filter(Transaction.transaction_type.in_(["입금", "출금"]))
            .filter(func.date(Transaction.transaction_date) > cutoff_date)
            .scalar()
        ) or 0.0
        current_total -= float(sum_flow)

    return ((current_total / float(past_total)) - 1.0) * 100.0
