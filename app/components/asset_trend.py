import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# 로컬 모듈
from crud.crud import get_portfolio_timeseries, get_total_asset_value


def render_portfolio_timeseries(
    db, *, days: int, use_current_value_today: bool = False
) -> None:
    """
    포트폴리오 자산가치 시계열 라인 차트를 렌더링합니다.

    - 기간 선택(selectbox) UI를 포함합니다.
    - 결측 일자를 보간(최근값 유지)하여 연속 시계열로 표기합니다.
    - 원화 축 형식을 적용하고, 레이아웃 폭에 맞춰 차트를 늘립니다.
    - 옵션 `use_current_value_today=True`이면, "현재 시점의 총 자산 가치"로 당일 포인트를 반영합니다.
    """
    timeseries = get_portfolio_timeseries(db, days=int(days))

    if not timeseries:
        st.info("자산 추이 데이터가 없습니다.")
        return

    # 옵션이 활성화되면: 당일 포인트를 현재 시점의 총 자산 가치로 반영합니다.
    if use_current_value_today:
        today = date.today()
        total_now = float(get_total_asset_value(db) or 0.0)
        last_ts = pd.to_datetime(timeseries[-1]["date"], errors="coerce")
        last_date = None if pd.isna(last_ts) else last_ts.date()
        if last_date == today:
            timeseries[-1]["total_krw"] = total_now
        else:
            timeseries.append({"date": today, "total_krw": total_now})

    df_series = pd.DataFrame(timeseries)
    df_series["date"] = pd.to_datetime(df_series["date"])
    df_series = df_series.sort_values("date").set_index("date")

    full_range = pd.date_range(
        start=df_series.index.min(),
        end=df_series.index.max(),
        freq="D",
    )
    df_series = df_series.reindex(full_range).ffill()
    df_series = df_series.reset_index().rename(
        columns={"index": "날짜", "total_krw": "자산가치"}
    )

    fig_line = px.line(
        df_series,
        x="날짜",
        y="자산가치",
        title=f"최근 {int(days)}일 자산 가치 추이 (KRW)",
        labels={"자산가치": "총 자산 가치 (KRW)", "날짜": "날짜"},
    )
    # main 포맷에 맞춘 y축 형식과 차트 폭
    fig_line.update_layout(yaxis_tickformat="₩,")
    st.plotly_chart(fig_line, use_container_width=True)
