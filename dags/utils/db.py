from typing import Dict, Any
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from airflow.hooks.base import BaseHook

from models.models import (
    Base,
    Platform,
    Asset,
    ExchangeRate,
    StableCoin,
)


def get_database_url():
    """Airflow Connections에서 데이터베이스 연결 정보를 가져옵니다."""
    conn = BaseHook.get_connection("ams")
    return f"postgresql://{conn.login}:{conn.password}@{conn.host}:{conn.port}/{conn.schema}"


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 시작 시 데이터베이스 스키마 생성
def create_tables():
    """데이터베이스 테이블이 존재하지 않으면 생성합니다."""
    try:
        # 테이블 생성 시도
        Base.metadata.create_all(bind=engine)
        print("[INFO] 데이터베이스 테이블 생성 완료 또는 이미 존재함")
    except Exception as e:
        print(f"[ERROR] 데이터베이스 테이블 생성 실패: {str(e)}")


# 초기화 코드 실행
create_tables()


@contextmanager
def get_db_session():
    """데이터베이스 세션을 제공하는 컨텍스트 매니저"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_asset(db, asset_data: Dict[str, Any]):
    """자산 정보를 데이터베이스에 업데이트합니다."""
    # 필수 필드 확인
    required_fields = ["symbol", "quantity", "category"]
    for field in required_fields:
        if field not in asset_data:
            raise ValueError(f"필수 필드 누락: {field}")

    # 플랫폼 조회 또는 생성
    platform_name = asset_data.pop("platform", "자동 동기화")
    platform = db.query(Platform).filter(Platform.name == platform_name).first()

    if not platform:
        platform = Platform(name=platform_name, category="거래소")
        db.add(platform)
        db.flush()  # ID 생성을 위해 flush

    # 기존 자산 조회
    asset = (
        db.query(Asset)
        .filter(
            Asset.symbol == asset_data["symbol"],
            Asset.platform_id == platform.id,
        )
        .first()
    )

    # 현재가가 없으면 0으로 설정
    current_price = asset_data.get("current_price", 0)

    evaluation_amount = asset_data.get("evaluation_amount", 0)

    # 원화 환산 평가금액 가져오기 (호출하는 쪽에서 계산해서 전달해야 함)
    eval_amount_krw = asset_data.get("eval_amount_krw", 0)

    if asset:
        # 기존 자산 업데이트
        for key, value in asset_data.items():
            if hasattr(asset, key) and key not in ["id", "created_at", "platform_id"]:
                setattr(asset, key, value)
        asset.current_price = current_price
        asset.evaluation_amount = evaluation_amount
        asset.eval_amount_krw = eval_amount_krw  # 원화 환산 평가금액 업데이트
        asset.updated_at = func.now()
    else:
        # 새 자산 생성
        # name이 없으면 symbol을 사용
        if "name" not in asset_data:
            asset_data["name"] = asset_data["symbol"]
        asset_data["current_price"] = current_price
        asset_data["evaluation_amount"] = evaluation_amount
        asset_data["eval_amount_krw"] = eval_amount_krw  # 원화 환산 평가금액 설정
        asset_data["platform_id"] = platform.id

        # 새 자산 인스턴스 생성
        asset = Asset(**asset_data)
        db.add(asset)

    return asset


def get_latest_asset_revision_by_platform_id(db, platform_id: int) -> int:
    """플랫폼 ID로 최신 리비전 번호를 조회합니다."""
    return (
        db.query(func.max(Asset.revision))
        .filter(Asset.platform_id == platform_id)
        .scalar()
    )


def get_latest_revision(db, platform_name: str) -> int:
    """플랫폼 이름으로 최신 리비전 번호를 조회합니다."""
    platform = db.query(Platform).filter(Platform.name == platform_name).first()
    if not platform:
        return 0

    latest_revision = get_latest_asset_revision_by_platform_id(db, platform.id)
    return 0 if latest_revision is None else latest_revision


def insert_asset(db, asset_data: Dict[str, Any]):
    """자산 정보를 데이터베이스에 새로 삽입합니다."""
    # 필수 필드 확인
    required_fields = [
        "symbol",
        "quantity",
        "category",
        "revision",
    ]  # revision 필드 추가
    for field in required_fields:
        if field not in asset_data:
            raise ValueError(f"필수 필드 누락: {field}")

    # 플랫폼 조회 또는 생성
    platform_name = asset_data.pop("platform", "자동 동기화")
    platform = db.query(Platform).filter(Platform.name == platform_name).first()

    if not platform:
        platform = Platform(name=platform_name, category="거래소")
        db.add(platform)
        db.flush()  # ID 생성을 위해 flush

    # 현재가가 없으면 0으로 설정
    current_price = asset_data.get("current_price", 0)
    evaluation_amount = asset_data.get("evaluation_amount", 0)
    eval_amount_krw = asset_data.get("eval_amount_krw", 0)  # 원화 환산 평가금액

    # 새 자산 생성 준비
    # name이 없으면 symbol을 사용
    if "name" not in asset_data:
        asset_data["name"] = asset_data["symbol"]

    asset_data["current_price"] = current_price
    asset_data["evaluation_amount"] = evaluation_amount
    asset_data["eval_amount_krw"] = eval_amount_krw
    asset_data["platform_id"] = platform.id

    # 새 자산 인스턴스 생성 및 추가
    asset = Asset(**asset_data)
    db.add(asset)
    db.flush()  # 새 asset의 ID를 얻기 위해 flush

    return asset


def upsert_exchange_rate(db, exchange_data: Dict[str, Any]):
    """환율 정보를 업데이트하거나 새로 생성합니다."""
    required_fields = ["base_currency", "target_currency", "rate"]
    for field in required_fields:
        if field not in exchange_data:
            raise ValueError(f"필수 필드 누락: {field}")

    exchange_rate = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.base_currency == exchange_data["base_currency"],
            ExchangeRate.target_currency == exchange_data["target_currency"],
        )
        .first()
    )

    if exchange_rate:
        exchange_rate.rate = exchange_data["rate"]
        exchange_rate.updated_at = func.now()
    else:
        exchange_rate = ExchangeRate(**exchange_data)
        db.add(exchange_rate)

    return exchange_rate


def get_exchange_rates(db) -> Dict[str, float]:
    """DB에서 모든 환율 정보를 조회하여 {통화코드: 환율} 형태의 딕셔너리로 반환합니다."""
    rates = {"KRW": 1.0}  # 원화 환율은 1로 설정
    try:
        exchange_rates = db.query(ExchangeRate).all()
        for rate in exchange_rates:
            rates[rate.base_currency] = rate.rate
        print(f"[DEBUG] DB에서 조회된 환율 정보: {rates}")
    except Exception as e:
        print(f"[ERROR] DB 환율 정보 조회 실패: {str(e)}")
    return rates


def get_active_stable_coins(db) -> set[str]:
    """활성화된 스테이블코인 심볼 목록을 조회합니다."""
    stable_coins = (
        db.query(StableCoin.symbol).filter(StableCoin.is_active == True).all()
    )
    return {coin[0] for coin in stable_coins}
