import os
import sys
import logging
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 환경 변수 로드
load_dotenv()

# 로컬 모듈 임포트
from utils.db import get_db_session, initialize_db
from crud.crud import (
    get_total_asset_value,
    get_asset_distribution_by_category,
    get_recent_transactions,
    get_daily_change_percentage,
)

# 데이터베이스 테이블 생성
initialize_db(drop_all=False)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="자산 관리 시스템",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 메인 페이지 타이틀 표시
st.title("자산 관리 시스템")

# 대시보드 내용
# 데이터베이스 세션 획득
db = get_db_session()

try:
    # 데이터베이스에서 데이터 가져오기
    total_value = get_total_asset_value(db)

    # 자산 분포 (기존 Asset 기반 - KRW 사용하도록 수정됨)
    category_data = get_asset_distribution_by_category(db)

    # --- 데이터 가져오기 (DailyAssetMetrics 기반) ---
    daily_change = get_daily_change_percentage(db)

    # 최근 거래 내역
    transactions = get_recent_transactions(db, days=30)
    transactions_data = []
    for tx in transactions:
        # asset 정보 로드가 필요하면 lazy='joined' 또는 별도 쿼리 필요
        # 여기서는 asset.name이 필요하므로, get_recent_transactions에서 join 로딩 고려
        asset_name = tx.asset.name if tx.asset else "N/A"  # 로딩 확인
        transactions_data.append(
            {
                "날짜": tx.transaction_date.strftime("%Y-%m-%d"),
                "자산": asset_name,
                "종류": tx.transaction_type,
                "금액": tx.amount,  # Transaction amount는 KRW가 아닐 수 있음. 표시 주의
            }
        )
    recent_transactions = pd.DataFrame(transactions_data)

    # --- 대시보드 UI 부분 (데이터 표시 로직 업데이트) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        # 총 자산 메트릭: daily_change 값을 delta로 사용
        st.metric("총 자산", f"₩{total_value:,.0f}", f"{daily_change:.1f}%")
    with col2:
        # 일일 수익률 메트릭: delta 없음
        st.metric("일일 수익률", f"{daily_change:.1f}%")
    with col3:
        # 30일 수익률 메트릭: delta 없음
        st.metric("30일 수익률", "N/A")

    # 차트를 2열로 배치
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("자산 분포")
        if not category_data:
            st.info("자산 분포 데이터가 없습니다.")
        else:
            # category_data 구조: [{'category': '...', 'amount': ...}]
            df_category = pd.DataFrame(category_data)
            fig_pie = px.pie(
                df_category,
                values="amount",  # amount는 KRW 기준 총액
                names="category",
                title="카테고리별 자산 비율 (KRW 기준)",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, width='stretch')

    with col_right:
        st.subheader("자산 추이")
        if True:
            st.info("자산 추이 데이터가 없습니다.")
        else:
            # performance_data 구조: DataFrame[날짜, 자산가치]
            fig_line = px.line(
                performance_data,
                x="날짜",
                y="자산가치",
                title="최근 30일 자산 가치 추이 (KRW)",
                labels={"자산가치": "총 자산 가치 (KRW)", "날짜": "날짜"},
            )
            # y축 형식을 원화로 설정
            fig_line.update_layout(
                yaxis_tickformat="₩,"
            )  # 정수형이 아닐 수 있으므로 ',' 사용
            st.plotly_chart(fig_line, width='stretch')

    st.subheader("최근 거래 내역")
    if recent_transactions.empty:
        st.info("최근 거래 내역이 없습니다.")
    else:
        st.dataframe(
            recent_transactions,
            width='stretch',
            hide_index=True,
            # 거래 금액(tx.amount)의 통화가 KRW가 아닐 수 있음에 유의
            column_config={
                "금액": st.column_config.NumberColumn(format="₩ %d")
            },  # 형식을 KRW로 가정
        )

finally:
    # 데이터베이스 세션 종료
    db.close()

# 푸터
st.markdown("---")
st.caption("© 2025 자산 관리 시스템 | 버전 0.1.1")  # 버전 업데이트
