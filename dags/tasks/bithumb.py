from typing import Dict, Any, List
import ccxt
import traceback
from airflow.hooks.base import BaseHook
from utils.db import (
    get_db_session,
    insert_asset,
    get_latest_revision,
    get_active_stable_coins,
)


def load_bithumb_api_keys() -> Dict[str, str]:
    """빗썸 API 키를 Airflow Connections에서 로드합니다."""
    try:
        conn = BaseHook.get_connection("bithumb_api")
        print(f"[DEBUG] 빗썸 API 키 로드 완료: {conn.login[:5]}...")
        return {
            "apiKey": conn.login,
            "secret": conn.password,
        }
    except Exception as e:
        print(f"[ERROR] 빗썸 API 키 로드 실패: {str(e)}")
        print(traceback.format_exc())
        return {"apiKey": "", "secret": ""}


def fetch_bithumb_balances(api_keys: Dict[str, str]) -> Dict[str, Any]:
    """빗썸 계정의 잔고를 조회합니다."""
    try:
        if not api_keys["apiKey"] or not api_keys["secret"]:
            print("[WARNING] 빗썸 API 키가 설정되지 않았습니다.")
            return {"total": {}, "prices": {}}

        exchange = ccxt.bithumb(
            {"apiKey": api_keys["apiKey"], "secret": api_keys["secret"]}
        )

        # 계정 잔고 조회
        balances = exchange.fetch_balance()
        print(f"[DEBUG] 빗썸 잔고 조회 완료: {balances['total']}")

        # 현재가 정보 추출
        prices = {}
        for currency, balance in balances["total"].items():
            # 잔고가 있는 경우에만 처리
            if balance > 0:
                if currency == "KRW":
                    prices[currency] = 1
                else:
                    # xcoin_last_{currency} 형식의 키에서 현재가 추출
                    price_key = f"xcoin_last_{currency.lower()}"
                    data = balances.get("info", {}).get("data", {})
                    if price_key in data:
                        try:
                            prices[currency] = float(data[price_key])
                        except (ValueError, TypeError):
                            prices[currency] = 0

        return {"total": balances["total"], "prices": prices}
    except Exception as e:
        print(f"[ERROR] 빗썸 잔고 조회 실패: {str(e)}")
        print(traceback.format_exc())
        return {"total": {}, "prices": {}}


def fetch_bithumb_prices(currencies: List[str]) -> Dict[str, float]:
    """빗썸에서 암호화폐 가격 정보를 가져옵니다."""
    exchange = ccxt.bithumb()
    prices = {}

    for currency in currencies:
        if currency == "KRW":
            # KRW는 1원으로 고정
            prices[currency] = 1
            continue

        try:
            # 티커 정보 조회 (KRW 쌍으로 조회)
            ticker = exchange.fetch_ticker(f"{currency}/KRW")
            prices[currency] = ticker["last"]
            print(f"[DEBUG] {currency} 가격 조회 완료: ₩{ticker['last']}")
        except Exception as e:
            print(f"[ERROR] {currency} 가격 조회 실패: {str(e)}")
            # 가격 정보를 가져오지 못한 경우 0으로 설정
            prices[currency] = 0

    return prices


def process_bithumb_balances(
    balances: Dict[str, Any], revision: int
) -> List[Dict[str, Any]]:
    """빗썸 잔고 데이터를 처리하여 자산 정보로 변환합니다."""
    assets = []

    # 스테이블코인 목록을 한 번만 조회
    with get_db_session() as db:
        active_stable_coins = get_active_stable_coins(db)

    # 자산 정보 생성
    for currency, balance in balances["total"].items():
        if balance > 0:
            # 스테이블코인 확인 (캐시된 목록 사용)
            if currency == "KRW":
                category = "현금"
            else:
                category = (
                    "스테이블코인" if currency in active_stable_coins else "암호화폐"
                )

            # 현재가 정보 가져오기
            current_price = balances["prices"].get(currency, 0)

            # 평가금액 계산
            evaluation_amount = current_price * balance

            asset = {
                "symbol": currency,
                "platform": "Bithumb",  # 플랫폼 이름
                "exchange": "Spot",  # 거래소 타입 (Spot)
                "quantity": balance,
                "category": category,
                "name": currency,  # 이름을 심볼과 동일하게 설정
                "currency": "KRW",  # 통화는 KRW로 고정
                "current_price": current_price,
                "evaluation_amount": evaluation_amount,
                "eval_amount_krw": evaluation_amount,  # KRW로 고정되어 있으므로 동일
                "revision": revision,  # 리비전 추가
            }
            assets.append(asset)
            print(f"[DEBUG] 처리된 자산: {asset}")

    return assets


def update_assets_in_db(assets: List[Dict[str, Any]]):
    """자산 정보를 데이터베이스에 업데이트합니다."""
    try:
        with get_db_session() as db:
            for asset in assets:
                print(f"[DEBUG] DB 삽입 시도: {asset}")
                try:
                    result = insert_asset(db, asset)
                    print(f"[DEBUG] 자산 삽입 성공: {asset['symbol']}")
                except Exception as e:
                    print(f"[ERROR] 자산 삽입 실패 ({asset['symbol']}): {str(e)}")
                    print(traceback.format_exc())
    except Exception as e:
        print(f"[ERROR] 데이터베이스 연결 또는 세션 오류: {str(e)}")
        print(traceback.format_exc())


def sync_bithumb_assets():
    """빗썸 자산 동기화 작업"""
    try:
        print("[DEBUG] 빗썸 자산 동기화 시작")

        # 리비전 조회
        with get_db_session() as db:
            latest_revision = get_latest_revision(
                db, "Bithumb"
            )  # 플랫폼 이름을 Bithumb으로 가정
            next_revision = latest_revision + 1
            print(f"[DEBUG] 다음 리비전: {next_revision}")

        api_keys = load_bithumb_api_keys()
        balances = fetch_bithumb_balances(api_keys)
        processed_assets = process_bithumb_balances(balances, next_revision)
        update_assets_in_db(processed_assets)
        print("[DEBUG] 빗썸 자산 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 빗썸 자산 동기화 중 오류 발생: {str(e)}")
        print(traceback.format_exc())
        raise
