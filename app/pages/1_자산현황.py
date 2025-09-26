import streamlit as st
import pandas as pd

# 로컬 모듈 임포트
from utils.db import get_db_session
from utils.formatters import (
    format_currency,
    color_negative_red,
)
from crud.crud import get_all_assets, get_all_platforms
from components.asset_pie import render_asset_allocation_pie_by_name
from models.models import Platform

# 상수 정의
SMALL_ASSET_THRESHOLD = 1000  # 소액 자산 기준 (원)

# 페이지 확장 설정
st.set_page_config(layout="wide")

st.header("보유 자산 현황")

# 사이드바에 간단한 옵션 추가
with st.sidebar:
    # 세션 상태 초기화
    if "hide_small_assets" not in st.session_state:
        st.session_state["hide_small_assets"] = False

    # 소액 자산 숨김 옵션
    hide_small_assets = st.checkbox(
        f"소액 자산 숨기기 (₩{SMALL_ASSET_THRESHOLD:,} 미만)",
        value=st.session_state["hide_small_assets"],
    )
    st.session_state["hide_small_assets"] = hide_small_assets

# 데이터베이스 세션 획득
db = get_db_session()

try:
    # 데이터베이스에서 자산 목록 가져오기
    assets = get_all_assets(db)
    platforms = get_all_platforms(db)

    # 자산 목록을 데이터프레임으로 변환
    asset_data = []
    for asset in assets:
        platform = db.query(Platform).filter(Platform.id == asset.platform_id).first()
        platform_name = platform.name if platform else "알 수 없음"

        # 통화 정보 처리
        currency = asset.currency
        amount = asset.evaluation_amount

        asset_data.append(
            {
                "이름": asset.name,
                "심볼": asset.symbol,
                "카테고리": asset.category,
                "플랫폼": platform_name,
                "거래소": asset.exchange,
                "현재가": format_currency(asset.current_price, currency),
                "보유수량": asset.quantity,
                "평가금액": format_currency(amount, currency),
                "원화평가금액": format_currency(asset.eval_amount_krw, "KRW"),
                "원화평가금액_숫자": asset.eval_amount_krw,
                "통화": currency or "",
                "평균매수가": format_currency(asset.avg_price, currency),
                "평가손익": asset.profit_loss,
                "평가손익_표시": format_currency(asset.profit_loss, currency),
                "평가손익률": asset.profit_loss_rate,
                "등록일": asset.created_at.strftime("%Y-%m-%d"),
            }
        )

    df_assets = pd.DataFrame(asset_data)

    if df_assets.empty:
        st.info("보유 자산이 없습니다.")
    else:
        # 소액 자산 필터링
        if hide_small_assets:
            filtered_df = df_assets[
                df_assets["원화평가금액_숫자"] >= SMALL_ASSET_THRESHOLD
            ]
        else:
            filtered_df = df_assets

        # 전체 합계 표시
        total_asset_value = df_assets["원화평가금액_숫자"].sum()
        st.metric("총 평가금액", f"₩{total_asset_value:,.0f}")

        # 자산(이름) 기준 전체 보유 비율 원형 차트 (컴포넌트)
        render_asset_allocation_pie_by_name(assets)
        st.markdown("---")

        # 플랫폼별 그룹핑 (필터링된 데이터프레임 사용)
        if filtered_df.empty:
            st.info("표시할 자산이 없습니다.")
        else:
            # 플랫폼별 그룹핑
            grouped = filtered_df.groupby("플랫폼")

            # 플랫폼별 데이터프레임 및 소계 표시
            for platform, group in grouped:
                platform_total = group["원화평가금액_숫자"].sum()
                st.subheader(f"{platform} (소계: ₩{platform_total:,.0f})")

                # 표시할 컬럼만 선택
                display_df = group.drop(columns=["원화평가금액_숫자"]).copy()

                # 손익과 손익률에 색상 적용
                styled_df = display_df.style.applymap(
                    color_negative_red, subset=["평가손익", "평가손익률"]
                )

                # 데이터프레임 표시
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True,
                    column_order=(
                        "거래소",
                        "카테고리",
                        "이름",
                        "심볼",
                        "평가손익_표시",
                        "평가손익률",
                        "평가금액",
                        "보유수량",
                        "평균매수가",
                        "현재가",
                        "원화평가금액",
                        "통화",
                        "등록일",
                    ),
                    column_config={
                        "보유수량": st.column_config.NumberColumn(format="%.4f"),
                        "등록일": st.column_config.DateColumn(format="YYYY-MM-DD"),
                        "평가손익_표시": st.column_config.TextColumn(),
                        "평가손익률": st.column_config.NumberColumn(format="%.2f%%"),
                    },
                )
                st.markdown("<br>", unsafe_allow_html=True)  # 그룹 간 간격 추가

finally:
    # 데이터베이스 세션 종료
    db.close()
