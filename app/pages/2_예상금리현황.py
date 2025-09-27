import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session

# 로컬 모듈 임포트
from utils.db import get_db_session
from crud.crud import get_latest_cash_equivalent_annual_interest_info

# 페이지 확장 설정
st.set_page_config(layout="wide")

st.header("예상 금리 현황")

# 데이터베이스 세션 획득
db: Session = get_db_session()

try:
    # 데이터 가져오기
    interest_data = get_latest_cash_equivalent_annual_interest_info(db)

    if not interest_data:
        st.info("표시할 현금성 자산이 없습니다.")
    else:
        # 데이터프레임으로 변환
        df_interest = pd.DataFrame(
            interest_data
        )  # CRUD 함수가 dict 리스트를 반환하므로 바로 사용

        # 백분율 계산을 위한 새로운 컬럼 추가
        df_interest["예상 연 금리 (%)"] = df_interest["annual_yield_decimal"] * 100

        # 컬럼 순서 및 이름 변경 (선택 사항)
        df_interest = df_interest.rename(
            columns={
                "platform_name": "플랫폼",
                "symbol": "심볼",
                "category": "자산 유형",
                "exchange": "거래소",
            }
        )

        st.dataframe(
            df_interest,
            width='stretch',
            hide_index=True,
            column_order=(
                "플랫폼",
                "거래소",
                "자산 유형",
                "심볼",
                "예상 연 금리 (%)",
            ),
            column_config={
                "예상 연 금리 (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

finally:
    db.close()
