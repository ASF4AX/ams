import os
import sys
import logging
import streamlit as st
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 환경 변수 로드
load_dotenv()

# 로컬 모듈 임포트
from utils.db import get_db_session, initialize_db
from crud.crud import (
    get_total_asset_value,
    get_recent_transactions,
)
from crud.metrics import get_portfolio_period_return
from components.asset_trend_by_platform import render_platform_timeseries
from components.transactions_table import render_transactions_table

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

    # 조회 기간 선택 (차트 외부) 및 옵션 토글
    selected_days = st.selectbox(
        "조회 기간",
        options=[90, 180, 360],
        index=1,
        format_func=lambda value: f"{value}일",
        key="portfolio_period",
    )
    reflect_flows = st.toggle(
        "입출금 반영",
        value=True,
        help="입출금 반영 수익률 계산",
    )

    # 기간별 수익률 계산 (집계 엔드포인트만 조회)
    daily_return = get_portfolio_period_return(db, days=1, reflect_flows=reflect_flows)
    monthly_return = get_portfolio_period_return(
        db, days=30, reflect_flows=reflect_flows
    )
    period_return = get_portfolio_period_return(
        db, days=int(selected_days), reflect_flows=reflect_flows
    )

    # --- 대시보드 UI 부분 (데이터 표시 로직 업데이트) ---
    col1, col2, col3 = st.columns(3)
    with col1:
        # 총 자산 메트릭: daily_return 값을 delta로 사용 (없으면 N/A)
        st.metric(
            "총 자산",
            f"₩{total_value:,.0f}",
            f"{float(daily_return):.1f}%" if daily_return is not None else "N/A",
        )
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

    # 자산 추이 섹션: 기존 전체 추이를 플랫폼별 area 방식으로 대체
    render_platform_timeseries(
        db, days=int(selected_days), use_current_value_today=True
    )

    # 메인 페이지에서는 '자산 분포' 섹션을 제거했습니다.

    transactions = get_recent_transactions(db, days=30)
    st.subheader("최근 거래 내역")
    if transactions:
        render_transactions_table(transactions, include_memo=False)
    else:
        st.info("최근 거래 내역이 없습니다.")

finally:
    # 데이터베이스 세션 종료
    db.close()

st.markdown("---")
st.caption("© 2025 자산 관리 시스템 | 버전 0.1.1")  # 버전 업데이트
