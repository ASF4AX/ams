import ccxt
from typing import Dict, Any, List
from airflow.hooks.base import BaseHook
from utils.db import (
    get_db_session,
    insert_asset,
    get_exchange_rates,
    get_latest_revision,
    get_active_stable_coins,
)
import traceback


def load_binance_api_keys() -> Dict[str, str]:
    """바이낸스 API 키를 Airflow Connections에서 로드합니다."""
    conn = BaseHook.get_connection("binance_api")
    print(f"[DEBUG] 바이낸스 API 키 로드 완료")
    return {
        "apiKey": conn.login,
        "secret": conn.password,
    }


def fetch_binance_balances(api_keys: Dict[str, str]) -> Dict[str, Any]:
    """바이낸스 계정의 잔고를 조회합니다."""
    try:
        exchange = ccxt.binance(
            {"apiKey": api_keys["apiKey"], "secret": api_keys["secret"]}
        )

        # 스팟 계정 잔고 조회
        spot_balances = exchange.fetch_balance()
        print(f"[DEBUG] 바이낸스 스팟 잔고 조회 완료: {spot_balances['total']}")

        # Earn 계정 잔고 조회 (새로운 방식)
        flexible_positions = exchange.sapi_get_simple_earn_flexible_position()
        locked_positions = exchange.sapi_get_simple_earn_locked_position()

        # Earn 잔고 계산
        earn_balances = {"total": {}}

        # 유동성 포지션 처리
        if "rows" in flexible_positions:
            for position in flexible_positions["rows"]:
                currency = position["asset"]
                amount = float(position["totalAmount"])
                if amount > 0:
                    if currency in earn_balances["total"]:
                        earn_balances["total"][currency] += amount
                    else:
                        earn_balances["total"][currency] = amount

        # 락업 포지션 처리
        if "rows" in locked_positions:
            for position in locked_positions["rows"]:
                currency = position["asset"]
                amount = float(position["amount"])
                if amount > 0:
                    if currency in earn_balances["total"]:
                        earn_balances["total"][currency] += amount
                    else:
                        earn_balances["total"][currency] = amount

        print(f"[DEBUG] 바이낸스 Earn 잔고 조회 완료: {earn_balances['total']}")

        # 스팟과 Earn 잔고 합치기
        total_balances = spot_balances["total"].copy()
        for currency, amount in earn_balances["total"].items():
            if amount > 0:
                if currency in total_balances:
                    total_balances[currency] += amount
                else:
                    total_balances[currency] = amount

        print(f"[DEBUG] 바이낸스 전체 잔고 (스팟 + Earn): {total_balances}")
        return {"total": total_balances}
    except Exception as e:
        print(f"[ERROR] 바이낸스 잔고 조회 실패: {str(e)}")
        print(traceback.format_exc())
        return {"total": {}}


def fetch_binance_futures_balances(api_keys: Dict[str, str]) -> Dict[str, Any]:
    """바이낸스 선물 계정의 잔고를 조회합니다."""
    try:
        exchange = ccxt.binance(
            {"apiKey": api_keys["apiKey"], "secret": api_keys["secret"]}
        )

        # 선물 계정 잔고 조회
        futures_balances = exchange.fapiprivatev2_get_balance()

        # 선물 잔고 계산
        futures_total = {}
        for balance in futures_balances:
            currency = balance["asset"]
            amount = float(balance["balance"])
            if amount > 0:
                if currency in futures_total:
                    futures_total[currency] += amount
                else:
                    futures_total[currency] = amount

        print(f"[DEBUG] 바이낸스 선물 잔고 조회 완료: {futures_total}")
        return {"total": futures_total}
    except Exception as e:
        print(f"[ERROR] 바이낸스 선물 잔고 조회 실패: {str(e)}")
        print(traceback.format_exc())
        return {"total": {}}


def fetch_binance_prices(currencies: List[str]) -> Dict[str, float]:
    """바이낸스에서 암호화폐 가격 정보를 가져옵니다."""
    exchange = ccxt.binance()
    prices = {}

    for currency in currencies:
        if currency == "USDT":
            # USDT는 1달러로 고정
            prices[currency] = 1
            continue

        try:
            # 티커 정보 조회 (USDT 쌍으로 조회)
            ticker = exchange.fetch_ticker(f"{currency}/USDT")
            prices[currency] = ticker["last"]
            print(f"[DEBUG] {currency} 가격 조회 완료: ${ticker['last']}")
        except Exception as e:
            error_msg = str(e)
            if "binance does not have market symbol" in error_msg:
                print(
                    f"[WARNING] {currency}는 유효하지 않은 마켓 심볼입니다: {error_msg}"
                )
                continue
            print(f"[ERROR] {currency} 가격 조회 실패: {error_msg}")
            prices[currency] = 0

    return prices


def process_binance_balances(
    balances: Dict[str, Any], revision: int, is_futures: bool = False
) -> List[Dict[str, Any]]:
    """바이낸스 잔고 데이터를 처리하여 자산 정보로 변환합니다."""
    assets = []
    currencies = []

    # 스테이블코인 목록을 한 번만 조회
    with get_db_session() as db:
        active_stable_coins = get_active_stable_coins(db)

    # 자산 정보 생성
    for currency, balance in balances["total"].items():
        if balance > 0:
            currencies.append(currency)

            # 스테이블코인 확인 (캐시된 목록 사용)
            category = "스테이블코인" if currency in active_stable_coins else "암호화폐"

            asset = {
                "symbol": currency,
                "platform": "Binance",  # 플랫폼 이름
                "exchange": "Futures" if is_futures else "Spot",  # 거래소 구분
                "quantity": balance,
                "category": category,
                "name": currency,  # 이름을 심볼과 동일하게 설정
                "currency": "USD",
                "revision": revision,  # 리비전 추가
            }
            assets.append(asset)
            print(f"[DEBUG] 처리된 자산: {asset}")

    # 가격 정보 조회
    prices = fetch_binance_prices(currencies)

    # 가격 정보가 있는 자산만 필터링
    valid_assets = []
    for asset in assets:
        symbol = asset["symbol"]
        if symbol in prices:
            asset["current_price"] = prices[symbol]
            # 평가금액 계산 (수량 * 현재가)
            asset["evaluation_amount"] = asset["quantity"] * asset["current_price"]
            valid_assets.append(asset)
            print(f"[DEBUG] 유효한 자산 추가: {asset['symbol']}")
        else:
            print(f"[WARNING] 유효하지 않은 자산 제외: {asset['symbol']}")

    # 환율 정보 조회 및 원화 평가금액 계산
    try:
        with get_db_session() as db:
            db_rates = get_exchange_rates(db)
            usd_rate = db_rates.get("USD", 0)
            if usd_rate == 0:
                print("[WARNING] USD 환율 정보가 없습니다.")
            else:
                for asset in valid_assets:
                    # USD 기준으로 평가금액을 원화로 변환
                    asset["eval_amount_krw"] = asset["evaluation_amount"] * usd_rate
    except Exception as e:
        print(f"[ERROR] 환율 정보 조회 실패: {str(e)}")

    return valid_assets


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


def sync_binance_assets():
    """바이낸스 자산 동기화 작업"""
    try:
        print("[DEBUG] 바이낸스 자산 동기화 시작")

        # 리비전 조회
        with get_db_session() as db:
            latest_revision = get_latest_revision(db, "Binance")
            next_revision = latest_revision + 1
            print(f"[DEBUG] 다음 리비전: {next_revision}")

        api_keys = load_binance_api_keys()

        # 스팟 + Earn 자산 동기화
        balances = fetch_binance_balances(api_keys)
        processed_assets = process_binance_balances(balances, next_revision)
        update_assets_in_db(processed_assets)

        # 선물 자산 동기화
        futures_balances = fetch_binance_futures_balances(api_keys)
        processed_futures_assets = process_binance_balances(
            futures_balances, next_revision, is_futures=True
        )
        update_assets_in_db(processed_futures_assets)

        print("[DEBUG] 바이낸스 자산 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 바이낸스 자산 동기화 중 오류 발생: {str(e)}")
        print(traceback.format_exc())
        raise
