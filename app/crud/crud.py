import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.sql import Subquery, select
from datetime import datetime, timedelta

from models.models import (
    Platform,
    Asset,
    Transaction,
    DailyAssetMetrics,
    StableCoin,
    AssetCategory,
)

# 로깅 설정
logger = logging.getLogger(__name__)


# --- Helper Functions --- START ---


def _get_latest_assets_by_platform_revision(db: Session) -> Subquery:
    """플랫폼 별로 최신 revision에 존재하는 자산 목록을 반환하는 서브쿼리"""

    # 1. platform_id별 최신 revision 번호 구하기
    latest_revision_subquery = (
        db.query(Asset.platform_id, func.max(Asset.revision).label("latest_revision"))
        .group_by(Asset.platform_id)
        .subquery("latest_revision")  # 서브쿼리에 별칭 추가
    )

    # 2. 해당 revision에 존재하는 자산들의 ID를 조회하는 서브쿼리
    latest_asset_ids_subquery = (
        db.query(Asset.id)
        .join(
            latest_revision_subquery,
            (Asset.platform_id == latest_revision_subquery.c.platform_id)
            & (Asset.revision == latest_revision_subquery.c.latest_revision),
        )
        .subquery("latest_asset_ids")  # 서브쿼리에 별칭 추가
    )

    return latest_asset_ids_subquery


def _get_latest_metric_revision_per_platform(db: Session) -> dict[int, int]:
    """각 플랫폼 ID별 최신 메트릭 리비전 번호를 딕셔너리로 반환합니다."""
    results = (
        db.query(DailyAssetMetrics.platform_id, func.max(DailyAssetMetrics.revision))
        .group_by(DailyAssetMetrics.platform_id)
        .all()
    )
    return {platform_id: max_revision for platform_id, max_revision in results}


# --- Helper Functions --- END ---


# Platform CRUD 작업
def get_all_platforms(db: Session):
    """모든 플랫폼 목록 조회"""
    return db.query(Platform).all()


def get_platform_by_id(db: Session, platform_id: int):
    """ID로 플랫폼 조회"""
    return db.query(Platform).filter(Platform.id == platform_id).first()


def get_platform_by_name(db: Session, name: str):
    """이름으로 플랫폼 조회"""
    return db.query(Platform).filter(Platform.name == name).first()


def create_platform(db: Session, name: str, category: str):
    """플랫폼 생성"""
    platform = Platform(name=name, category=category)
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


# Asset CRUD 작업
def get_all_assets(db: Session):
    """모든 자산의 최신 상태를 조회합니다.

    각 플랫폼(platform_id)의 가장 최신 리비전(created_at 기준)에
    존재하는 자산 데이터를 조회합니다.
    """
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)

    # 최신 리비전 시점의 자산 ID를 사용하여 Asset 테이블 필터링
    latest_assets = (
        db.query(Asset).filter(Asset.id.in_(latest_asset_ids_subquery)).all()
    )

    return latest_assets


def get_asset_by_id(db: Session, asset_id: int):
    """ID로 자산 조회 (최신 버전 보장 안 함 - ID는 고유하므로 특정 시점 조회용)"""
    # 참고: 이 함수는 특정 ID의 레코드를 직접 조회하므로, '최신' 개념을 적용하지 않습니다.
    # 만약 특정 심볼/플랫폼의 '최신' 자산을 ID로 조회해야 한다면 다른 로직이 필요합니다.
    return db.query(Asset).filter(Asset.id == asset_id).first()


def get_assets_by_category(db: Session, category: str):
    """카테고리별 최신 자산 목록 조회"""
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)

    # 최신 리비전 시점의 자산 ID를 사용하여 Asset 테이블 필터링 + 카테고리 필터링
    latest_assets_in_category = (
        db.query(Asset)
        .filter(Asset.id.in_(latest_asset_ids_subquery))
        .filter(Asset.category == category)
        .all()
    )
    return latest_assets_in_category


def get_assets_by_platform(db: Session, platform_id: int):
    """플랫폼별 최신 자산 목록 조회"""
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)

    # 최신 리비전 시점의 자산 ID를 사용하여 Asset 테이블 필터링 + 플랫폼 필터링
    latest_assets_on_platform = (
        db.query(Asset)
        .filter(Asset.id.in_(latest_asset_ids_subquery))
        .filter(Asset.platform_id == platform_id)
        .all()
    )
    return latest_assets_on_platform


def create_asset(
    db: Session,
    name: str,
    symbol: str,
    category: str,
    platform_id: int,
    current_price: float,
    quantity: float,
    revision: int,  # 리비전 번호 추가
):
    """자산 생성"""
    evaluation_amount = current_price * quantity
    asset = Asset(
        name=name,
        symbol=symbol,
        category=category,
        platform_id=platform_id,
        current_price=current_price,
        quantity=quantity,
        evaluation_amount=evaluation_amount,
        revision=revision,  # 리비전 번호 설정
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(db: Session, asset_id: int, **kwargs):
    """자산 정보 업데이트"""
    asset = get_asset_by_id(db, asset_id)
    if not asset:
        return None

    for key, value in kwargs.items():
        if hasattr(asset, key):
            setattr(asset, key, value)

    # 평가금액 재계산
    if "current_price" in kwargs or "quantity" in kwargs:
        asset.evaluation_amount = asset.current_price * asset.quantity

    asset.updated_at = datetime.now()
    db.commit()
    db.refresh(asset)
    return asset


# Transaction CRUD 작업
def get_all_transactions(db: Session, skip: int = 0, limit: int = 100):
    """모든 거래 내역 조회"""
    return (
        db.query(Transaction)
        .order_by(Transaction.transaction_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_transaction_by_id(db: Session, transaction_id: int):
    """ID로 거래 내역 조회"""
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def get_transactions_by_asset(db: Session, asset_id: int):
    """자산별 거래 내역 조회"""
    return (
        db.query(Transaction)
        .filter(Transaction.asset_id == asset_id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )


def get_transactions_by_type(db: Session, transaction_type: str):
    """거래 유형별 거래 내역 조회"""
    return (
        db.query(Transaction)
        .filter(Transaction.transaction_type == transaction_type)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )


def get_recent_transactions(db: Session, days: int = 30):
    """최근 N일 동안의 거래 내역 조회"""
    date_limit = datetime.now() - timedelta(days=days)
    return (
        db.query(Transaction)
        .filter(Transaction.transaction_date >= date_limit)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )


def create_transaction(
    db: Session,
    asset_id: int,
    transaction_type: str,
    price: float,
    quantity: float,
    memo: str = None,
    transaction_date: datetime = None,
):
    """거래 내역 생성"""
    if transaction_date is None:
        transaction_date = datetime.now()

    amount = price * quantity
    transaction = Transaction(
        asset_id=asset_id,
        transaction_type=transaction_type,
        price=price,
        quantity=quantity,
        amount=amount,
        memo=memo,
        transaction_date=transaction_date,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # 자산 수량 업데이트
    asset = get_asset_by_id(db, asset_id)
    if transaction_type == "매수":
        new_qty = asset.quantity + quantity
    elif transaction_type == "매도":
        new_qty = asset.quantity - quantity
    else:
        new_qty = asset.quantity

    update_asset(db, asset_id, quantity=new_qty)

    return transaction


# 통계 및 요약 함수
def get_total_asset_value(db: Session) -> float:
    """최신 자산 기준 총 자산 가치 합계 (원화)"""
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)

    # 최신 리비전 시점의 자산 ID를 사용하여 eval_amount_krw 합산
    result = (
        db.query(func.sum(Asset.eval_amount_krw))
        .filter(Asset.id.in_(latest_asset_ids_subquery))
        .scalar()
    )
    return result or 0.0


def get_daily_change_percentage(db: Session) -> float:
    """플랫폼별 최신 리비전 기준 일일 자산 가치 변화율(%)을 반환합니다."""
    latest_revisions = _get_latest_metric_revision_per_platform(db)
    if not latest_revisions:
        return 0.0

    total_before_all = 0.0
    total_after_all = 0.0
    can_calculate = False

    for platform_id, latest_rev in latest_revisions.items():
        if latest_rev == 1:  # 해당 플랫폼의 첫번째 메트릭이면 이전 값이 없음
            continue

        metrics_summary = (
            db.query(
                func.sum(DailyAssetMetrics.before_value_krw).label("platform_before"),
                func.sum(DailyAssetMetrics.after_value_krw).label("platform_after"),
            )
            .filter(
                DailyAssetMetrics.platform_id == platform_id,
                DailyAssetMetrics.revision == latest_rev,
            )
            .first()
        )

        if (
            metrics_summary
            and metrics_summary.platform_before is not None
            and metrics_summary.platform_after is not None
        ):
            total_before_all += metrics_summary.platform_before
            total_after_all += metrics_summary.platform_after
            can_calculate = True  # 계산 가능한 데이터가 하나라도 있으면 True

    if not can_calculate or total_before_all == 0:
        return 0.0  # 계산할 데이터가 없거나 이전 값 합계가 0이면 변화율 0

    daily_change = ((total_after_all - total_before_all) / total_before_all) * 100
    return daily_change


def get_asset_distribution_by_category(db: Session) -> list[dict]:
    """최신 자산 기준, 카테고리별 자산 분포 (KRW 기준)"""
    # 이 함수는 DailyAssetMetrics가 아닌 현재 Asset 스냅샷 기준이므로 유지합니다.
    # 단, evaluation_amount 대신 eval_amount_krw 를 사용하도록 수정
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)

    results = (
        db.query(Asset.category, func.sum(Asset.eval_amount_krw).label("total_amount"))
        .filter(Asset.id.in_(latest_asset_ids_subquery))
        .group_by(Asset.category)
        .all()
    )

    return [
        {"category": category, "amount": amount}
        for category, amount in results
        if amount is not None and amount > 0
    ]


def get_asset_distribution_by_platform(db: Session) -> list[dict]:
    """최신 자산 기준, 플랫폼별 자산 분포 (KRW 기준)"""
    # 이 함수는 DailyAssetMetrics가 아닌 현재 Asset 스냅샷 기준이므로 유지합니다.
    # 단, evaluation_amount 대신 eval_amount_krw 를 사용하도록 수정
    latest_asset_ids_subquery = _get_latest_assets_by_platform_revision(db)
    results = (
        db.query(Platform.name, func.sum(Asset.eval_amount_krw).label("total_amount"))
        .join(Asset, Platform.id == Asset.platform_id)
        .filter(Asset.id.in_(latest_asset_ids_subquery))
        .group_by(Platform.name)
        .all()
    )
    return [
        {"platform": name, "amount": amount}
        for name, amount in results
        if amount is not None and amount > 0
    ]


# StableCoin CRUD 작업
def get_all_stable_coins(db: Session):
    """모든 스테이블코인 목록 조회"""
    return db.query(StableCoin).all()


def get_active_stable_coins(db: Session):
    """활성화된 스테이블코인 목록 조회"""
    return db.query(StableCoin).filter(StableCoin.is_active == True).all()


def get_stable_coin_by_symbol(db: Session, symbol: str):
    """심볼로 스테이블코인 조회"""
    return db.query(StableCoin).filter(StableCoin.symbol == symbol).first()


def create_stable_coin(db: Session, symbol: str):
    """스테이블코인 생성"""
    # 이미 존재하는지 확인
    existing_coin = get_stable_coin_by_symbol(db, symbol)
    if existing_coin:
        return existing_coin

    stable_coin = StableCoin(symbol=symbol)
    db.add(stable_coin)
    db.commit()
    db.refresh(stable_coin)
    return stable_coin


def update_stable_coin_status(db: Session, symbol: str, is_active: bool):
    """스테이블코인 활성화 상태 업데이트"""
    stable_coin = get_stable_coin_by_symbol(db, symbol)
    if stable_coin:
        stable_coin.is_active = is_active
        stable_coin.updated_at = datetime.now()
        db.commit()
        db.refresh(stable_coin)
        return True
    return False


def delete_stable_coin(db: Session, symbol: str):
    """스테이블코인 삭제"""
    stable_coin = get_stable_coin_by_symbol(db, symbol)
    if stable_coin:
        db.delete(stable_coin)
        db.commit()
        return True
    return False


def get_latest_cash_equivalent_annual_interest_info(db: Session):
    """
    최신 리비전의 현금 및 스테이블 코인 자산에 대한 연간 예상 금리 정보를 반환합니다.
    DailyAssetMetrics.return_rate (일일 수익률) * 365 로 계산합니다.
    """
    latest_metric_revisions = _get_latest_metric_revision_per_platform(db)
    if not latest_metric_revisions:
        return []

    results = []
    for platform_id, latest_revision in latest_metric_revisions.items():
        metrics = (
            db.query(
                Platform.name.label("platform_name"),
                Asset.symbol,
                Asset.category,
                Asset.exchange,
                DailyAssetMetrics.return_rate,
            )
            .join(
                Asset,
                (Asset.platform_id == DailyAssetMetrics.platform_id)
                & (Asset.symbol == DailyAssetMetrics.symbol),
            )
            .join(Platform, Platform.id == DailyAssetMetrics.platform_id)
            .filter(DailyAssetMetrics.platform_id == platform_id)
            .filter(DailyAssetMetrics.revision == latest_revision)
            .filter(
                (Asset.category == AssetCategory.CASH.value)
                | (Asset.category == AssetCategory.STABLE_COIN.value)
            )
            .filter(
                Asset.revision
                == select(func.max(Asset.revision))
                .where(Asset.platform_id == platform_id)
                .scalar_subquery()
            )  # 각 플랫폼의 최신 Asset 리비전과 매칭
            .all()
        )
        for metric in metrics:
            annual_yield_decimal = (metric.return_rate or 0) * 365
            results.append(
                {
                    "platform_name": metric.platform_name,
                    "symbol": metric.symbol,
                    "category": metric.category,
                    "exchange": metric.exchange,
                    "annual_yield_decimal": annual_yield_decimal,
                }
            )
    return results
