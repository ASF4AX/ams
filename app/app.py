import os
import sys
import logging
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 환경 변수 로드
load_dotenv()

# 로컬 모듈 임포트
from utils.db import get_db_session, initialize_db
from crud.crud import (
    get_total_asset_value,
    get_recent_transactions,
    get_daily_change_percentage,
)
from crud.metrics import get_portfolio_period_return
from components.asset_trend import render_portfolio_timeseries

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

    # 조회 기간 선택 (차트 외부)
    selected_days = st.selectbox(
        "조회 기간",
        options=[30, 90, 180],
        index=1,
        format_func=lambda value: f"{value}일",
        key="portfolio_period",
    )

    # 기간별 수익률 계산 (집계 엔드포인트만 조회)
    monthly_return = get_portfolio_period_return(db, days=30)
    period_return = get_portfolio_period_return(db, days=int(selected_days))

    # --- 대시보드 UI 부분 (데이터 표시 로직 업데이트) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        # 총 자산 메트릭: daily_change 값을 delta로 사용
        st.metric("총 자산", f"₩{total_value:,.0f}", f"{daily_change:.1f}%")
    with col2:
        # 월 수익률 (30일 기준)
        st.metric(
            "월 수익률",
            f"{monthly_return:.1f}%" if monthly_return is not None else "N/A",
        )
    with col3:
        # 선택 기간 수익률 (조회기간 연동)
        st.metric(
            f"{int(selected_days)}일 수익률",
            f"{period_return:.1f}%" if period_return is not None else "N/A",
        )

    # 자산 추이 (상단, 전체 폭) 컴포넌트
    # 오늘 포인트를 현재 총자산 값으로 반영해 표시
    render_portfolio_timeseries(
        db, days=int(selected_days), use_current_value_today=True
    )

    # 메인 페이지에서는 '자산 분포' 섹션을 제거했습니다.

    st.subheader("최근 거래 내역")
    if recent_transactions.empty:
        st.info("최근 거래 내역이 없습니다.")
    else:
        st.dataframe(
            recent_transactions,
            width="stretch",
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
