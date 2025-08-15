from sqlalchemy import func
from datetime import datetime

from models.models import Asset, Platform, DailyAssetMetrics, AssetCategory
from utils.db import (
    get_db_session,
    get_latest_asset_revision_by_platform_id,
)


def _fetch_previous_metrics(db, platform_id: int):
    """이전 메트릭 값 딕셔너리, 새 리비전 번호를 가져옵니다."""
    # 이전 메트릭 리비전 조회
    prev_metric_rev = (
        db.query(func.max(DailyAssetMetrics.revision))
        .filter(DailyAssetMetrics.platform_id == platform_id)
        .scalar()
    )

    prev_metrics_lookup = {}
    if prev_metric_rev is not None:
        prev_metrics_data = (
            db.query(
                DailyAssetMetrics.exchange,
                DailyAssetMetrics.symbol,
                DailyAssetMetrics.after_value,
                DailyAssetMetrics.after_value_krw,
            )
            .filter(
                DailyAssetMetrics.platform_id == platform_id,
                DailyAssetMetrics.revision == prev_metric_rev,
            )
            .all()
        )
        prev_metrics_lookup = {
            (m.exchange, m.symbol): (m.after_value, m.after_value_krw)
            for m in prev_metrics_data
        }

    # 새 메트릭 리비전 계산
    new_metric_revision = (prev_metric_rev or 0) + 1

    return prev_metrics_lookup, new_metric_revision


def process_metrics(platform_name: str) -> None:
    """플랫폼의 자산 지표를 처리합니다."""
    with get_db_session() as session:
        platform = (
            session.query(Platform).filter(Platform.name == platform_name).first()
        )

        if not platform:
            print(f"Platform not found: {platform_name}")
            return

        platform_id = platform.id

        # --- calculate_and_save_asset_metrics 로직 시작 ---
        latest_asset_rev = get_latest_asset_revision_by_platform_id(
            session, platform_id
        )

        if latest_asset_rev is None:
            print(
                f"[INFO] Platform ID {platform_id}: 최신 자산 데이터가 없어 메트릭 계산을 건너뛰었습니다."
            )
            return

        # 최신 자산 목록 조회
        latest_assets = (
            session.query(Asset)
            .filter(
                Asset.platform_id == platform_id, Asset.revision == latest_asset_rev
            )
            .all()
        )

        prev_metrics_lookup, new_metric_revision = _fetch_previous_metrics(
            session, platform_id
        )

        metrics_to_save = []
        latest_asset_keys = set()

        # Step 1: 최신 자산을 기준으로 생성(created) 또는 업데이트(updated)된 메트릭 계산
        for asset in latest_assets:
            key = (asset.exchange, asset.symbol)
            latest_asset_keys.add(key)

            before_value_tuple = prev_metrics_lookup.get(key)
            before_value = before_value_tuple[0] if before_value_tuple else None
            before_value_krw = before_value_tuple[1] if before_value_tuple else None

            # 스테이블 코인 여부 확인
            is_stable_coin = asset.category == AssetCategory.STABLE_COIN.value

            if is_stable_coin:
                # 스테이블 코인의 경우 after_value를 코인 수량으로 설정
                after_value = asset.quantity if asset.quantity is not None else 0
            else:
                # 그 외 자산은 기존 로직대로 평가금액을 사용
                after_value = (
                    asset.evaluation_amount
                    if asset.evaluation_amount is not None
                    else 0
                )

            after_value_krw = (
                asset.eval_amount_krw if asset.eval_amount_krw is not None else 0
            )

            change_amount, return_rate = None, None
            change_amount_krw, return_rate_krw = None, None

            if before_value is not None:
                change_amount = after_value - before_value
                if before_value != 0:
                    return_rate = (after_value - before_value) / before_value

            if before_value_krw is not None:
                change_amount_krw = after_value_krw - before_value_krw
                if before_value_krw != 0:
                    return_rate_krw = (
                        after_value_krw - before_value_krw
                    ) / before_value_krw

            metrics_to_save.append(
                DailyAssetMetrics(
                    platform_id=platform_id,
                    exchange=asset.exchange,
                    symbol=asset.symbol,
                    revision=new_metric_revision,
                    before_value=before_value,
                    after_value=after_value,
                    change_amount=change_amount,
                    return_rate=return_rate,
                    before_value_krw=before_value_krw,
                    after_value_krw=after_value_krw,
                    change_amount_krw=change_amount_krw,
                    return_rate_krw=return_rate_krw,
                    created_at=datetime.now(),
                )
            )

        # Step 2: 계산된 메트릭 저장
        if metrics_to_save:
            try:
                session.bulk_save_objects(metrics_to_save)
                # session.commit() # 세션 관리자에서 처리
                print(
                    f"[INFO] Platform ID {platform_id}: {len(metrics_to_save)}개 메트릭 저장 완료 (Revision: {new_metric_revision})"
                )
            except Exception as e:
                # session.rollback() # 세션 관리자에서 처리
                print(f"[ERROR] Platform ID {platform_id}: 메트릭 저장 실패 - {str(e)}")
                raise
        else:
            print(f"[INFO] Platform ID {platform_id}: 저장할 메트릭이 없습니다.")
        # --- calculate_and_save_asset_metrics 로직 끝 ---
