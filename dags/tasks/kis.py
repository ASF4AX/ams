import requests
import json
import time
import traceback
from typing import Dict, Any, List
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from utils.db import (
    get_db_session,
    insert_asset,
    upsert_exchange_rate,
    get_exchange_rates,
    get_latest_revision,
)


# --- KIS API 설정 ---
def get_kis_api_config() -> Dict[str, Any]:
    """Airflow Connection에서 KIS API 설정을 로드합니다."""
    try:
        conn = BaseHook.get_connection("kis_api")
        port = conn.extra_dejson.get("port", "9443")  # 기본 포트 9443
        config = {
            "appkey": conn.extra_dejson.get("appkey", ""),
            "appsecret": conn.password,
            "account": conn.login,  # 계좌번호 (앞 8자리)
            "account_suffix": conn.extra_dejson.get(
                "account_suffix", "01"
            ),  # 계좌번호 뒤 2자리
            "base_url": f"{conn.host}:{port}",
        }
        if not config["appkey"] or not config["appsecret"] or not config["account"]:
            raise ValueError(
                "KIS API 설정(appkey, appsecret, account)이 Airflow Connection에 없습니다."
            )
        print("[DEBUG] KIS API 설정 로드 완료")
        return config
    except Exception as e:
        print(f"[ERROR] KIS API 설정 로드 실패: {str(e)}")
        print(traceback.format_exc())
        raise


def get_kis_access_token(config: Dict[str, Any]) -> str:
    """KIS API 접근 토큰을 발급받습니다."""
    token_url = f"{config['base_url']}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    payload = {
        "grant_type": "client_credentials",
        "appkey": config["appkey"],
        "appsecret": config["appsecret"],
    }
    try:
        # 타임아웃 설정 추가 (연결 5초, 읽기 10초)
        res = requests.post(
            token_url, headers=headers, data=json.dumps(payload), timeout=(5, 10)
        )
        res.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        token_data = res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("토큰 발급 실패")

        print("[DEBUG] KIS 접근 토큰 발급 성공")
        # Airflow Variable에 토큰 저장 (기존 토큰 덮어쓰기)
        token_expiry = int(time.time()) + (
            token_data.get("expires_in", 3600) - 600
        )  # 만료 10분 전
        Variable.set("kis_access_token", access_token)
        Variable.set("kis_token_expiry", str(token_expiry))
        return access_token
    except requests.exceptions.RequestException as e:
        print("[ERROR] KIS 토큰 발급 요청 실패")
        print(traceback.format_exc())
        raise
    except Exception as e:
        print("[ERROR] KIS 토큰 발급 중 예상치 못한 오류")
        print(traceback.format_exc())
        raise


def get_valid_kis_token(config: Dict[str, Any]) -> str:
    """유효한 KIS 접근 토큰을 가져오거나 새로 발급받습니다."""
    access_token = Variable.get("kis_access_token", default_var=None)
    expiry_str = Variable.get("kis_token_expiry", default_var=None)

    if access_token and expiry_str:
        expiry_ts = int(expiry_str)
        if time.time() < expiry_ts:
            print("[DEBUG] 기존 KIS 접근 토큰 사용")
            return access_token
        else:
            print("[INFO] KIS 접근 토큰 만료, 새로 발급합니다.")
    else:
        print("[INFO] KIS 접근 토큰 없음, 새로 발급합니다.")

    return get_kis_access_token(config)


def fetch_kis_balance_api(config: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    """KIS API를 호출하여 잔고 정보를 조회합니다."""
    url = f"{config['base_url']}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {access_token}",
        "appKey": config["appkey"],
        "appSecret": config["appsecret"],
        "tr_id": "TTTC8434R",  # 주식 잔고 조회 TR ID
        "custtype": "P",
    }
    params = {
        "CANO": config["account"],
        "ACNT_PRDT_CD": config["account_suffix"],
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "01",  # 조회구분 (01:대출일별, 02:종목별)
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",  # 처리구분 (00:전일매매포함, 01:전일매매미포함)
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    try:
        # 타임아웃 설정 (연결: 5초, 읽기: 10초)
        res = requests.get(url, headers=headers, params=params, timeout=(5, 10))
        res.raise_for_status()
        balance_data = res.json()
        if balance_data.get("rt_cd") != "0":
            raise ValueError(f"잔고 조회 API 오류: {balance_data.get('msg1', '')}")
        print(f"[DEBUG] KIS 잔고 API 조회 성공 (rt_cd: {balance_data.get('rt_cd')})")
        return balance_data
    except requests.exceptions.Timeout:
        print("[ERROR] KIS 잔고 API 요청 시간 초과")
        return {}
    except requests.exceptions.ConnectionError:
        print("[ERROR] KIS 잔고 API 연결 실패")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] KIS 잔고 API 요청 실패: {str(e)}")
        print(traceback.format_exc())
        return {}
    except Exception as e:
        print(f"[ERROR] KIS 잔고 API 처리 중 오류: {str(e)}")
        print(traceback.format_exc())
        return {}


def process_kis_assets(
    balance_data: Dict[str, Any], revision: int
) -> List[Dict[str, Any]]:
    """KIS 잔고 데이터를 처리하여 표준 자산 정보 리스트로 변환합니다."""
    assets = []
    stock_list = balance_data.get("output1", [])  # 보유 주식 목록
    summary = balance_data.get("output2", {})  # 예수금 등 요약 정보

    # 보유 주식 처리
    for stock in stock_list:
        try:
            symbol = stock.get("pdno")
            if not symbol:
                continue

            # 평가금액 사용 (API 호출 줄이기)
            current_price = float(stock.get("prpr", 0))  # 현재가 사용 (잔고조회 시점)
            evaluation_amount = float(stock.get("evlu_amt", 0))  # 평가금액
            quantity = float(stock.get("hldg_qty", 0))  # 보유수량
            avg_price = float(stock.get("pchs_avg_pric", 0))  # 매수평균가
            profit_loss = float(stock.get("evlu_pfls_amt", 0))  # 평가손익금액
            profit_loss_rate = float(stock.get("evlu_pfls_rt", 0))  # 평가손익률

            asset = {
                "symbol": symbol,
                "platform": "한국투자증권",
                "quantity": quantity,
                "current_price": current_price,
                "evaluation_amount": evaluation_amount,
                "avg_price": avg_price,
                "profit_loss": profit_loss,
                "profit_loss_rate": profit_loss_rate,
                "category": "국내주식",  # 기본값을 국내주식으로 설정
                "name": stock.get("prdt_name", symbol),  # 상품명, 없으면 심볼 사용
                "currency": "KRW",  # 국내주식은 KRW로 설정
                "revision": revision,
            }
            assets.append(asset)
            print(f"[DEBUG] 처리된 주식 자산: {asset}")
        except Exception as e:
            stock_symbol = stock.get("pdno", "알 수 없음")
            print(f"[ERROR] 주식 자산 처리 중 오류 ({stock_symbol}): {str(e)}")
            print(traceback.format_exc())

    # 예수금 처리
    try:
        def _d2_cash(summary_item: Dict[str, Any]) -> float:
            """체결기준 합산용 국내 현금은 D+2 정산 금액만 사용합니다."""
            raw = summary_item.get("prvs_rcdl_excc_amt", 0)
            return float(raw or 0)

        # summary가 리스트인 경우 첫 번째 항목 사용, 딕셔너리인 경우 그대로 사용
        if isinstance(summary, list) and len(summary) > 0:
            summary_item = summary[0]
            deposit = _d2_cash(summary_item)
        elif isinstance(summary, dict):
            deposit = _d2_cash(summary)
        else:
            print("[WARNING] 예수금 정보가 예상 형식이 아님. 기본값 0 사용.")
            deposit = 0

        if deposit > 0:
            deposit_asset = {
                "symbol": "KRW",
                "platform": "한국투자증권",
                "quantity": deposit,
                "current_price": 1,
                "evaluation_amount": deposit,
                "category": "현금",
                "name": "원화 예수금",
                "currency": "KRW",  # 예수금은 KRW로 설정
                "revision": revision,
            }
            assets.append(deposit_asset)
            print(f"[DEBUG] 처리된 예수금 자산: {deposit_asset}")
    except Exception as e:
        print(f"[ERROR] 예수금 처리 중 오류: {str(e)}")
        print(traceback.format_exc())

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


# --- KIS 해외 계좌 상세 API 호출 (수정: API 변경 및 전체 응답 반환) ---
def fetch_kis_overseas_account_details_api(
    config: Dict[str, Any], access_token: str
) -> Dict[str, Any]:
    """KIS API를 호출하여 해외주식 체결기준현재잔고 정보를 조회합니다."""
    print(
        "[INFO] fetch_kis_overseas_account_details_api: 해외 계좌 상세 API 호출 시작 (CTRP6504R)"
    )
    try:
        url = f"{config['base_url']}/uapi/overseas-stock/v1/trading/inquire-present-balance"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
            "appKey": config["appkey"],
            "appSecret": config["appsecret"],
            "tr_id": "CTRP6504R",  # 해외주식 체결기준현재잔고 TR ID
            "custtype": "P",
        }
        params = {
            "CANO": config["account"],
            "ACNT_PRDT_CD": config["account_suffix"],
            "WCRC_FRCR_DVSN_CD": "02",  # 01:원화, 02:외화
            "NATN_CD": "000",  # 국가코드 (000: 전체)
            "TR_MKET_CD": "00",  # 거래시장코드 (00: 전체)
            "INQR_DVSN_CD": "00",  # 조회구분코드 (00: 전체)
        }

        # 타임아웃 설정 (연결: 5초, 읽기: 10초)
        res = requests.get(url, headers=headers, params=params, timeout=(5, 10))
        print(f"[DEBUG] 해외 계좌 상세 API 응답 상태 코드: {res.status_code}")
        res.raise_for_status()
        account_data = res.json()

        if account_data.get("rt_cd") != "0":
            error_msg = account_data.get("msg1", "")
            print(f"[ERROR] 해외 계좌 상세 API 오류 응답: {error_msg}")
            raise ValueError(f"해외 계좌 상세 조회 API 오류: {error_msg}")

        print(
            "[INFO] fetch_kis_overseas_account_details_api: 해외 계좌 상세 API 조회 성공"
        )
        return account_data

    except requests.exceptions.Timeout:
        print("[ERROR] 해외 계좌 상세 API 요청 시간 초과")
        return {}
    except requests.exceptions.ConnectionError:
        print("[ERROR] 해외 계좌 상세 API 연결 실패")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 해외 계좌 상세 API 요청 실패: {str(e)}")
        print(traceback.format_exc())
        return {}
    except Exception as e:
        print(f"[ERROR] 해외 계좌 상세 API 처리 중 오류: {str(e)}")
        print(traceback.format_exc())
        return {}


# --- KIS 해외 주식 처리 (수정: 필드명 변경) ---
def process_kis_overseas_assets(
    stock_list: List[Dict[str, Any]], revision: int  # output1과 revision 받음
) -> List[Dict[str, Any]]:
    """KIS 해외주식 잔고 데이터(CTRP6504R output1)를 처리하여 표준 자산 정보 리스트로 변환합니다."""
    assets = []
    processed_symbols = set()  # 중복 처리용

    print(
        f"[INFO] process_kis_overseas_assets: 해외주식 {len(stock_list)}개 항목 처리 시작"
    )
    for stock in stock_list:
        try:
            # --- 필드명 변경 (CTRP6504R output1 명세 기준) ---
            symbol = stock.get("pdno")  # 상품번호
            if not symbol:
                continue

            quantity_str = stock.get("ccld_qty_smtl1", "0")  # 체결수량합계1
            quantity = float(quantity_str) if quantity_str else 0.0
            if quantity <= 0:
                continue

            currency = stock.get("buy_crcy_cd")  # 매수통화코드
            exchange_code = stock.get(
                "ovrs_excg_cd", ""
            )  # 해외거래소코드 (없을 수 있음)
            unique_key = f"{exchange_code}_{symbol}"
            if not exchange_code:
                unique_key = symbol  # 거래소 코드 없으면 symbol만 사용

            if unique_key in processed_symbols:
                # print(f"[DEBUG] 중복 종목 건너뛰기: {unique_key}") # 필요시 주석 해제
                continue
            processed_symbols.add(unique_key)

            # 현재가
            current_price = 0.0
            price_str = stock.get("ovrs_now_pric1", "0")  # 해외현재가격1
            try:
                current_price = float(price_str) if price_str else 0.0
            except (ValueError, TypeError):
                print(f"[WARNING] {symbol}: 해외현재가({price_str}) 변환 오류")
                current_price = 0.0

            # 매수평균가
            avg_price = 0.0
            avg_price_str = stock.get("avg_unpr3", "0")  # 평균단가3
            try:
                avg_price = float(avg_price_str) if avg_price_str else 0.0
            except (ValueError, TypeError):
                print(f"[WARNING] {symbol}: 평균단가({avg_price_str}) 변환 오류")

            # 평가손익
            profit_loss = 0.0
            profit_loss_str = stock.get("evlu_pfls_amt2", "0")  # 평가손익금액2
            try:
                profit_loss = float(profit_loss_str) if profit_loss_str else 0.0
            except (ValueError, TypeError):
                print(f"[WARNING] {symbol}: 평가손익({profit_loss_str}) 변환 오류")

            # 평가손익률
            profit_loss_rate = 0.0
            profit_loss_rate_str = stock.get("evlu_pfls_rt1", "0")  # 평가손익율1
            try:
                profit_loss_rate = (
                    float(profit_loss_rate_str) if profit_loss_rate_str else 0.0
                )
            except (ValueError, TypeError):
                print(
                    f"[WARNING] {symbol}: 평가손익률({profit_loss_rate_str}) 변환 오류"
                )

            # 평가금액 계산
            evaluation_amount = current_price * quantity

            # natn_kor_name 필드를 사용하여 카테고리 동적 생성
            nation_name = stock.get("natn_kor_name")  # 국가한글명
            if nation_name:
                category = f"{nation_name}주식"
            else:
                print(
                    f"[WARNING] {symbol}: 국가명(natn_kor_name) 없음. '해외주식'으로 카테고리 설정."
                )
                category = "해외주식"  # 기본 카테고리

            stock_name = stock.get("prdt_name", symbol)  # 상품명

            asset = {
                "symbol": symbol,
                "platform": "한국투자증권",
                "quantity": quantity,
                "current_price": current_price,
                "evaluation_amount": evaluation_amount,
                "avg_price": avg_price,
                "profit_loss": profit_loss,
                "profit_loss_rate": profit_loss_rate,
                "category": category,
                "name": stock_name,
                "exchange": exchange_code,
                "currency": currency,
                "revision": revision,
            }
            assets.append(asset)
            # print(f"[DEBUG] 처리된 해외주식 자산: {asset}") # 필요시 주석 해제

        except Exception as e:
            stock_symbol = stock.get("pdno", "알 수 없음")
            print(f"[ERROR] 해외주식 자산 처리 중 오류 ({stock_symbol}): {str(e)}")
            print(traceback.format_exc())

    print(
        f"[INFO] process_kis_overseas_assets: 해외주식 처리 완료. 최종 {len(assets)}개 자산 생성"
    )
    return assets


# --- KIS 해외 예수금 처리 (수정: 필드명 변경 및 입력 데이터 변경) ---
def process_kis_overseas_cash(
    cash_list: List[Dict[str, Any]], revision: int  # output2와 revision 받음
) -> List[Dict[str, Any]]:
    """KIS 해외 예수금 데이터(CTRP6504R output2)를 처리하여 표준 자산 정보 리스트로 변환합니다."""
    assets = []
    processed_currencies = (
        set()
    )  # 중복 처리 (output2에 중복 통화가 없을 것으로 예상되지만 안전 장치)
    currency_names = {
        "USD": "달러 예수금",
        "JPY": "엔화 예수금",
        "EUR": "유로 예수금",  # 유로 추가
        "CNY": "위안화 예수금",
        "HKD": "홍콩달러 예수금",
        "VND": "베트남동 예수금",  # 베트남 동 추가
        # 필요한 다른 통화 추가
    }
    print(
        f"[INFO] process_kis_overseas_cash: 해외 예수금 {len(cash_list)}개 항목 처리 시작"
    )

    for cash_item in cash_list:
        try:
            currency_code = cash_item.get("crcy_cd")  # 통화코드
            frcr_buy_amt_smtl = cash_item.get("frcr_buy_amt_smtl", "0")
            frcr_sll_amt_smtl = cash_item.get("frcr_sll_amt_smtl", "0")
            frcr_dncl_amt_2 = cash_item.get("frcr_dncl_amt_2", "0")

            if not currency_code:
                continue

            # 이미 처리된 통화 코드는 건너뛰기
            if currency_code in processed_currencies:
                print(f"[DEBUG] 이미 처리된 통화 건너뛰기 (예수금): {currency_code}")
                continue

            amount = (
                float(frcr_sll_amt_smtl)
                - float(frcr_buy_amt_smtl)
                + float(frcr_dncl_amt_2)
            )
            # 금액이 0.0 인 경우만 무시
            if amount == 0.0:
                # print(f"[DEBUG] 금액이 0이므로 무시: {currency_code} {amount}") # 필요시 주석 해제
                processed_currencies.add(currency_code)
                continue

            # 첫 번째 유효한 항목 처리
            asset = {
                "symbol": currency_code,  # 통화 코드를 심볼로 사용
                "platform": "한국투자증권",
                "quantity": amount,
                "current_price": 1,  # 현금성 자산
                "evaluation_amount": amount,  # 평가금액 추가
                "category": "현금",
                "name": currency_names.get(currency_code, f"{currency_code} 예수금"),
                "currency": currency_code,  # 통화코드 설정
                "revision": revision,
            }
            assets.append(asset)
            processed_currencies.add(currency_code)
            print(f"[DEBUG] 처리된 해외 예수금 자산: {asset}")

        except Exception as e:
            ccy = cash_item.get("crcy_cd", "알 수 없음")
            print(f"[ERROR] 해외 예수금 처리 중 오류 ({ccy}): {str(e)}")
            print(traceback.format_exc())

    print(
        f"[INFO] process_kis_overseas_cash: 해외 예수금 처리 완료. 최종 {len(assets)}개 자산 생성"
    )
    return assets


# --- KIS 환율 처리 (신규 함수) ---
def process_kis_exchange_rates(
    cash_list: List[Dict[str, Any]],  # output2를 받음
) -> List[Dict[str, Any]]:
    """KIS 해외 예수금 데이터(CTRP6504R output2)에서 환율 정보를 추출합니다."""
    exchange_rates = []
    processed_currencies = set()  # 중복 처리
    print(
        f"[INFO] process_kis_exchange_rates: 환율 정보 {len(cash_list)}개 항목 처리 시작"
    )
    for item in cash_list:
        try:
            base_currency = item.get("crcy_cd")
            # --- 필드명 변경 (CTRP6504R output2 명세 기준) ---
            rate_str = item.get("frst_bltn_exrt", "0")  # 최초고시환율 사용

            if not base_currency or not rate_str:
                continue

            if base_currency in processed_currencies:
                continue

            rate = float(rate_str)
            if rate <= 0:
                print(f"[WARNING] {base_currency} 환율 값이 0 이하입니다: {rate}")
                continue

            # KRW 대비 환율로 저장 (대상 통화는 항상 KRW)
            exchange_data = {
                "base_currency": base_currency,
                "target_currency": "KRW",
                "rate": rate,
            }
            exchange_rates.append(exchange_data)
            processed_currencies.add(base_currency)
            print(f"[DEBUG] 추출된 환율 정보: {exchange_data}")

        except Exception as e:
            ccy = item.get("crcy_cd", "알 수 없음")
            print(f"[ERROR] 환율 처리 중 오류 ({ccy}): {str(e)}")
            print(traceback.format_exc())

    print(
        f"[INFO] process_kis_exchange_rates: 환율 처리 완료. 최종 {len(exchange_rates)}개 환율 정보 생성"
    )
    return exchange_rates


def update_exchange_rates_in_db(exchange_rate_data: List[Dict[str, Any]]):
    """환율 정보를 데이터베이스에 업데이트합니다."""
    if not exchange_rate_data:
        print("[WARNING] DB에 업데이트할 환율 정보가 없습니다.")
        return

    print(f"[INFO] 총 {len(exchange_rate_data)}개 환율 정보 DB 업데이트 시작")
    try:
        with get_db_session() as db:
            for rate_info in exchange_rate_data:
                try:
                    upsert_exchange_rate(db, rate_info)
                    print(
                        f"[DEBUG] 환율 업데이트 성공: {rate_info['base_currency']}/KRW = {rate_info['rate']}"
                    )
                except Exception as e_rate_db:
                    print(
                        f"[ERROR] 환율 DB 업데이트 실패 ({rate_info.get('base_currency')}): {str(e_rate_db)}"
                    )
                    print(traceback.format_exc())
        print("[INFO] 환율 DB 업데이트 완료")
    except Exception as e_db_session:
        print(f"[ERROR] 환율 DB 세션 오류: {str(e_db_session)}")
        print(traceback.format_exc())


def calculate_eval_amount_krw(
    assets: List[Dict[str, Any]], rates: Dict[str, float]
) -> List[Dict[str, Any]]:
    """자산 목록의 원화 환산 평가금액을 계산합니다.

    Args:
        assets: 자산 정보 목록
        rates: {통화코드: 환율} 형태의 환율 정보

    Returns:
        원화 환산 평가금액이 추가된 자산 목록
    """
    for asset in assets:
        currency = asset.get("currency")  # 통화코드가 없으면 None 반환
        amount_foreign = asset.get("evaluation_amount")  # 평가금액 사용

        if currency is None:
            print(
                f"[WARNING] {asset.get('symbol', 'N/A')} 통화코드 정보 없음. 원화 환산 불가."
            )
            continue

        if amount_foreign is not None:
            if currency == "KRW":
                asset["eval_amount_krw"] = amount_foreign
                continue

            rate = rates.get(currency)
            if rate is not None:
                try:
                    asset["eval_amount_krw"] = amount_foreign * rate
                except Exception as calc_e:
                    print(
                        f"[ERROR] {asset.get('symbol', 'N/A')} 원화 환산 평가금액 계산 오류: {calc_e}"
                    )
            else:
                print(
                    f"[WARNING] {asset.get('symbol', 'N/A')} ({currency}) 환율 정보 없음. 원화 환산 불가."
                )
        else:
            print(
                f"[WARNING] {asset.get('symbol', 'N/A')} 원화 환산 평가금액 계산 위한 정보 부족 (통화: {currency}, 금액: {amount_foreign})"
            )

    return assets


# --- 메인 동기화 함수 (수정: 통합 API 호출 및 처리) ---
def sync_kis_assets():
    """한국투자증권 자산 동기화 작업 (국내주식/현금 + 해외주식/현금 + 환율)"""
    try:
        print("[INFO] 한국투자증권 자산 동기화 시작 (통합 API)")
        config = get_kis_api_config()
        access_token = get_valid_kis_token(config)

        # --- 리비전 조회 ---
        with get_db_session() as db:
            latest_revision = get_latest_revision(db, "한국투자증권")
            next_revision = latest_revision + 1
            print(f"[DEBUG] 다음 리비전: {next_revision}")

        # --- 국내 자산 처리 (유지) ---
        print("[INFO] 국내 자산 조회 및 처리 시작")
        domestic_balance_data = fetch_kis_balance_api(config, access_token)
        domestic_assets = []
        if domestic_balance_data:
            domestic_assets = process_kis_assets(domestic_balance_data, next_revision)
            print(f"[INFO] 국내 자산 {len(domestic_assets)}개 처리 완료")
        else:
            print("[WARNING] 국내 잔고 정보를 가져오지 못했습니다.")

        # --- 해외 계좌 상세 정보 조회 (통합 API 호출) ---
        print("[INFO] 해외 계좌 상세 정보 조회 시작 (주식, 예수금, 환율)")
        overseas_account_data = fetch_kis_overseas_account_details_api(
            config, access_token
        )
        overseas_assets = []
        overseas_cash_assets = []
        exchange_rate_data = []

        if overseas_account_data and overseas_account_data.get("rt_cd") == "0":
            # 해외 주식 처리 (output1 사용)
            output1 = overseas_account_data.get("output1", [])
            if output1:
                overseas_assets = process_kis_overseas_assets(output1, next_revision)
            else:
                print("[INFO] 해외 주식 잔고 없음 (output1)")

            # 해외 예수금 및 환율 처리 (output2 사용)
            output2 = overseas_account_data.get("output2", [])
            if output2:
                overseas_cash_assets = process_kis_overseas_cash(output2, next_revision)
                exchange_rate_data = process_kis_exchange_rates(output2)
            else:
                print("[INFO] 해외 예수금/환율 정보 없음 (output2)")

        else:
            print("[WARNING] 해외 계좌 상세 정보를 가져오지 못했습니다.")

        # --- 환율 정보 처리 ---
        # API에서 제공하는 환율 데이터를 {통화코드: 환율} 형태의 딕셔너리로 변환
        rates = {rate["base_currency"]: rate["rate"] for rate in exchange_rate_data}
        rates["KRW"] = 1.0  # 원화 환율은 1로 설정

        # API에서 제공하지 않는 통화에 대해서만 DB에서 환율 정보 조회
        try:
            with get_db_session() as db:
                db_rates = get_exchange_rates(db)
                for currency, rate in db_rates.items():
                    if (
                        currency not in rates
                    ):  # API에서 제공하지 않는 통화만 DB 환율 사용
                        rates[currency] = rate
                        print(f"[INFO] DB에서 {currency} 환율 정보 사용: {rate}")
        except Exception as e:
            print(f"[ERROR] DB 환율 정보 조회 실패: {str(e)}")

        print(f"[DEBUG] 최종 사용 환율 정보: {rates}")

        # --- 자산 통합 및 원화 환산 평가금액 계산 ---
        all_assets = domestic_assets + overseas_assets + overseas_cash_assets
        all_assets = calculate_eval_amount_krw(all_assets, rates)

        # --- 자산 DB 업데이트 ---
        if all_assets:
            print(f"[INFO] 총 {len(all_assets)}개 자산 DB 업데이트 시작")
            update_assets_in_db(all_assets)
            print(f"[INFO] 자산 DB 업데이트 완료")
        else:
            print("[WARNING] DB에 업데이트할 자산이 없습니다.")

        # --- 환율 정보 DB 업데이트 ---
        update_exchange_rates_in_db(exchange_rate_data)

        print(
            f"[INFO] 한국투자증권 자산 동기화 완료 (총 {len(all_assets)}개 자산, {len(exchange_rate_data)}개 환율)"
        )

    except Exception as e:
        print(f"[ERROR] 한국투자증권 자산 동기화 중 최상위 오류 발생: {str(e)}")
        print(traceback.format_exc())
        raise
