import streamlit as st
import os
from dotenv import load_dotenv
import pandas as pd

# 로컬 모듈 임포트
from utils.db import initialize_db, test_connection, get_db_session
from crud.crud import (
    get_all_stable_coins,
    create_stable_coin,
    update_stable_coin_status,
    get_stable_coin_by_symbol,
)

# 페이지 확장 설정
st.set_page_config(layout="wide")

# 환경 변수 로드
load_dotenv()

st.header("설정")

# 데이터베이스 연결 테스트
connection_successful, db_status = test_connection()

# --- 설정 UI ---
st.subheader("데이터베이스 상태")
if connection_successful:
    st.success(f"데이터베이스 연결 상태: {db_status}")
else:
    st.error(f"데이터베이스 연결 상태: {db_status}")
    st.warning("데이터베이스 연결에 문제가 있습니다. 설정을 확인하세요.")

st.subheader("데이터 관리")

if st.button("데이터베이스 초기화"):
    if connection_successful:
        try:
            # 기존 테이블 삭제하고 새로 생성
            initialize_db(drop_all=True)
            st.success("데이터베이스가 초기화되었습니다.")
        except Exception as e:
            st.error(f"데이터베이스 초기화 실패: {str(e)}")
    else:
        st.error("데이터베이스 연결이 불가능하여 초기화할 수 없습니다.")

st.markdown("---")
st.warning("데이터베이스 초기화 시 기존 데이터가 모두 삭제됩니다.")

# 스테이블코인 관리 섹션
st.subheader("스테이블코인 관리")

# 데이터베이스 세션 획득
db = get_db_session()

try:
    # 현재 등록된 스테이블코인 목록 조회
    stable_coins = get_all_stable_coins(db)

    # 새로운 스테이블코인 추가 폼
    with st.form("add_stable_coin"):
        symbol = st.text_input("심볼 (예: USDT)")

        submitted = st.form_submit_button("추가")
        if submitted:
            if symbol:
                try:
                    create_stable_coin(db, symbol.upper())
                    st.success(f"{symbol} 스테이블코인이 추가되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"스테이블코인 추가 중 오류 발생: {str(e)}")
            else:
                st.warning("심볼을 입력해주세요.")

    # 기존 스테이블코인 목록 표시 및 관리
    if stable_coins:
        # 데이터프레임 생성
        df = pd.DataFrame(
            [
                {
                    "심볼": coin.symbol,
                    "활성": coin.is_active,
                }
                for coin in stable_coins
            ]
        )

        # 수정 가능한 데이터프레임 표시
        edited_df = st.data_editor(
            df,
            width='stretch',
            hide_index=True,
            column_config={
                "심볼": st.column_config.TextColumn(
                    "심볼",
                    disabled=True,
                ),
                "활성": st.column_config.CheckboxColumn(
                    "활성",
                    help="스테이블코인 활성화 여부",
                    default=False,
                ),
                "등록일": st.column_config.TextColumn(
                    "등록일",
                    disabled=True,
                ),
                "수정일": st.column_config.TextColumn(
                    "수정일",
                    disabled=True,
                ),
            },
        )

        # 변경사항 저장
        if st.button("변경사항 저장"):
            try:
                # 변경된 데이터 확인
                for _, row in edited_df.iterrows():
                    symbol = row["심볼"]
                    is_active = row["활성"]
                    coin = get_stable_coin_by_symbol(db, symbol)
                    if coin and coin.is_active != is_active:
                        update_stable_coin_status(db, symbol, is_active)

                st.success("변경사항이 저장되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"변경사항 저장 중 오류 발생: {str(e)}")
    else:
        st.info("등록된 스테이블코인이 없습니다.")

finally:
    db.close()

st.subheader("환경 정보")
st.text(f"데이터베이스 호스트: {os.getenv('DB_HOST', '정보 없음')}")
st.text(f"데이터베이스 포트: {os.getenv('DB_PORT', '정보 없음')}")
st.text(f"데이터베이스 이름: {os.getenv('DB_NAME', '정보 없음')}")
st.text(f"데이터베이스 사용자: {os.getenv('DB_USER', '정보 없음')}")
st.text(f"애플리케이션 환경: {os.getenv('APP_ENV', '정보 없음')}")
