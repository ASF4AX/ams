import logging
from datetime import datetime, timedelta

from utils.db import get_db_session, initialize_db
from models.models import Platform, Asset, Transaction

# 로깅 설정
logger = logging.getLogger(__name__)


def seed_database():
    """샘플 데이터를 데이터베이스에 생성하는 함수"""
    logger.info("샘플 데이터 생성 시작")

    # 데이터베이스 세션 획득
    db = get_db_session()

    try:
        # 기존 데이터 초기화 (테이블을 날리고 다시 생성)
        initialize_db()

        # 플랫폼 데이터 생성
        platforms = [
            {"name": "업비트", "category": "암호화폐 거래소"},
            {"name": "바이낸스", "category": "암호화폐 거래소"},
            {"name": "한국투자증권", "category": "증권사"},
            {"name": "미래에셋증권", "category": "증권사"},
            {"name": "현금자산", "category": "기타"},
        ]

        platform_entities = {}
        for platform_data in platforms:
            platform = Platform(
                name=platform_data["name"], category=platform_data["category"]
            )
            db.add(platform)
            db.flush()  # ID 할당을 위해 flush
            platform_entities[platform.name] = platform

        # 자산 데이터 생성
        assets = [
            {
                "name": "비트코인",
                "symbol": "BTC",
                "category": "암호화폐",
                "platform": "업비트",
                "current_price": 40000000,
                "quantity": 0.1,
            },
            {
                "name": "이더리움",
                "symbol": "ETH",
                "category": "암호화폐",
                "platform": "업비트",
                "current_price": 3000000,
                "quantity": 1.5,
            },
            {
                "name": "솔라나",
                "symbol": "SOL",
                "category": "암호화폐",
                "platform": "바이낸스",
                "current_price": 100000,
                "quantity": 10,
            },
            {
                "name": "삼성전자",
                "symbol": "005930",
                "category": "국내주식",
                "platform": "한국투자증권",
                "current_price": 70000,
                "quantity": 100,
            },
            {
                "name": "카카오",
                "symbol": "035720",
                "category": "국내주식",
                "platform": "한국투자증권",
                "current_price": 50000,
                "quantity": 50,
            },
            {
                "name": "LG화학",
                "symbol": "051910",
                "category": "국내주식",
                "platform": "미래에셋증권",
                "current_price": 500000,
                "quantity": 10,
            },
            {
                "name": "테슬라",
                "symbol": "TSLA",
                "category": "해외주식",
                "platform": "미래에셋증권",
                "current_price": 260000,
                "quantity": 10,
            },
            {
                "name": "애플",
                "symbol": "AAPL",
                "category": "해외주식",
                "platform": "미래에셋증권",
                "current_price": 180000,
                "quantity": 20,
            },
            {
                "name": "현금",
                "symbol": "KRW",
                "category": "현금",
                "platform": "현금자산",
                "current_price": 1,
                "quantity": 10000000,
            },
        ]

        asset_entities = {}
        for asset_data in assets:
            platform = platform_entities[asset_data["platform"]]
            asset = Asset(
                name=asset_data["name"],
                symbol=asset_data["symbol"],
                category=asset_data["category"],
                platform_id=platform.id,
                current_price=asset_data["current_price"],
                quantity=asset_data["quantity"],
                evaluation_amount=asset_data["current_price"] * asset_data["quantity"],
                revision=1,
            )
            db.add(asset)
            db.flush()  # ID 할당을 위해 flush
            asset_entities[asset.name] = asset

        # 거래 내역 데이터 생성 (각 자산별로 몇 개의 거래 내역 추가)
        transactions = []

        # 현재 시간
        now = datetime.now()

        # 비트코인 거래 내역
        btc = asset_entities["비트코인"]
        transactions.extend(
            [
                {
                    "asset": btc,
                    "type": "매수",
                    "price": 35000000,
                    "quantity": 0.05,
                    "date": now - timedelta(days=30),
                    "memo": "첫 비트코인 구매",
                },
                {
                    "asset": btc,
                    "type": "매수",
                    "price": 38000000,
                    "quantity": 0.05,
                    "date": now - timedelta(days=15),
                    "memo": "비트코인 추가 매수",
                },
            ]
        )

        # 이더리움 거래 내역
        eth = asset_entities["이더리움"]
        transactions.extend(
            [
                {
                    "asset": eth,
                    "type": "매수",
                    "price": 2800000,
                    "quantity": 1.0,
                    "date": now - timedelta(days=25),
                    "memo": "이더리움 첫 구매",
                },
                {
                    "asset": eth,
                    "type": "매수",
                    "price": 2900000,
                    "quantity": 0.5,
                    "date": now - timedelta(days=10),
                    "memo": "이더리움 추가 매수",
                },
            ]
        )

        # 솔라나 거래 내역
        sol = asset_entities["솔라나"]
        transactions.extend(
            [
                {
                    "asset": sol,
                    "type": "매수",
                    "price": 90000,
                    "quantity": 10.0,
                    "date": now - timedelta(days=20),
                    "memo": "솔라나 매수",
                }
            ]
        )

        # 삼성전자 거래 내역
        samsung = asset_entities["삼성전자"]
        transactions.extend(
            [
                {
                    "asset": samsung,
                    "type": "매수",
                    "price": 68000,
                    "quantity": 50,
                    "date": now - timedelta(days=60),
                    "memo": "삼성전자 첫 매수",
                },
                {
                    "asset": samsung,
                    "type": "매수",
                    "price": 69000,
                    "quantity": 50,
                    "date": now - timedelta(days=45),
                    "memo": "삼성전자 추가 매수",
                },
            ]
        )

        # 카카오 거래 내역
        kakao = asset_entities["카카오"]
        transactions.extend(
            [
                {
                    "asset": kakao,
                    "type": "매수",
                    "price": 48000,
                    "quantity": 50,
                    "date": now - timedelta(days=40),
                    "memo": "카카오 매수",
                }
            ]
        )

        # LG화학 거래 내역
        lg = asset_entities["LG화학"]
        transactions.extend(
            [
                {
                    "asset": lg,
                    "type": "매수",
                    "price": 490000,
                    "quantity": 5,
                    "date": now - timedelta(days=50),
                    "memo": "LG화학 첫 매수",
                },
                {
                    "asset": lg,
                    "type": "매수",
                    "price": 510000,
                    "quantity": 5,
                    "date": now - timedelta(days=35),
                    "memo": "LG화학 추가 매수",
                },
            ]
        )

        # 테슬라 거래 내역
        tesla = asset_entities["테슬라"]
        transactions.extend(
            [
                {
                    "asset": tesla,
                    "type": "매수",
                    "price": 250000,
                    "quantity": 5,
                    "date": now - timedelta(days=55),
                    "memo": "테슬라 첫 매수",
                },
                {
                    "asset": tesla,
                    "type": "매수",
                    "price": 270000,
                    "quantity": 5,
                    "date": now - timedelta(days=30),
                    "memo": "테슬라 추가 매수",
                },
            ]
        )

        # 애플 거래 내역
        apple = asset_entities["애플"]
        transactions.extend(
            [
                {
                    "asset": apple,
                    "type": "매수",
                    "price": 175000,
                    "quantity": 10,
                    "date": now - timedelta(days=65),
                    "memo": "애플 첫 매수",
                },
                {
                    "asset": apple,
                    "type": "매수",
                    "price": 185000,
                    "quantity": 10,
                    "date": now - timedelta(days=40),
                    "memo": "애플 추가 매수",
                },
            ]
        )

        # 거래 내역 생성
        for tx_data in transactions:
            tx = Transaction(
                asset_id=tx_data["asset"].id,
                transaction_type=tx_data["type"],
                price=tx_data["price"],
                quantity=tx_data["quantity"],
                amount=tx_data["price"] * tx_data["quantity"],
                memo=tx_data["memo"],
                transaction_date=tx_data["date"],
            )
            db.add(tx)

        # 변경사항 커밋
        db.commit()
        logger.info("샘플 데이터 생성 완료")

    except Exception as e:
        db.rollback()
        logger.error(f"샘플 데이터 생성 실패: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # 스크립트 직접 실행 시 샘플 데이터 생성
    seed_database()
