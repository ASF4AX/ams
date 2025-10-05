import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# 로컬 모듈
from crud.timeseries import get_portfolio_timeseries_by_platform
from crud.crud import get_asset_distribution_by_platform


def _ffill_by_platform(df: pd.DataFrame) -> pd.DataFrame:
    """플랫폼별로 일자 연속 축으로 재색인 후 보간.

    - forward-fill 후 선행 구간 NaN을 0으로 채움(면적 누적 자연스러움)
    """
    if df.empty:
        return df

    df = df.copy()
    df["날짜"] = pd.to_datetime(df["날짜"])
    df = df.sort_values(["날짜", "플랫폼"])  # 안정적인 순서

    full_range = pd.date_range(start=df["날짜"].min(), end=df["날짜"].max(), freq="D")

    def _reindex_group(g: pd.DataFrame) -> pd.DataFrame:
        g2 = (
            g.set_index("날짜")["자산가치"]
            .reindex(full_range)
            .ffill()
            .to_frame(name="자산가치")
        )
        # 면적 차트 규칙: 선행 구간은 0으로 채움
        g2["자산가치"] = g2["자산가치"].fillna(0)
        g2 = g2.reset_index().rename(columns={"index": "날짜"})
        g2["플랫폼"] = g["플랫폼"].iloc[0]
        return g2

    out = df.groupby("플랫폼", sort=False).apply(_reindex_group).reset_index(drop=True)
    return out


def _apply_today_snapshot(
    df: pd.DataFrame,
    *,
    today_values: dict[str, float],
) -> pd.DataFrame:
    """오늘 날짜의 플랫폼별 값을 스냅샷으로 반영합니다.

    - 오늘 행이 있으면 해당 플랫폼 값만 덮어쓰기
    - 오늘 행이 없으면 스냅샷의 플랫폼만 오늘 행으로 추가
    """
    if df.empty:
        return df

    df = df.copy()
    today = pd.to_datetime(date.today())
    today_norm = today.normalize()
    mask_today = df["날짜"].dt.normalize().eq(today_norm)
    has_today = mask_today.any()

    # 스냅샷 매핑 준비
    mapping = pd.Series({k: float(v) for k, v in today_values.items()}) if today_values else pd.Series(dtype=float)

    # 1) 오늘 행이 없는 스냅샷 플랫폼은 오늘 행 추가
    if not mapping.empty:
        existing_today = set(df.loc[mask_today, "플랫폼"]) if has_today else set()
        missing = set(mapping.index) - existing_today
        if missing:
            add_df = pd.DataFrame(
                [{"날짜": today, "플랫폼": p, "자산가치": float(mapping[p])} for p in missing]
            )
            df = pd.concat([df, add_df], ignore_index=True)
            mask_today = df["날짜"].dt.normalize().eq(today_norm)

    # 2) 오늘 행(추가분 포함)에 대해 스냅샷 값으로 덮어쓰기(스냅샷에 없는 플랫폼은 기존 유지)
    if mask_today.any() and not mapping.empty:
        df.loc[mask_today, "자산가치"] = (
            df.loc[mask_today, "플랫폼"].map(mapping).fillna(df.loc[mask_today, "자산가치"])
        )

    return df


def render_platform_timeseries(
    db,
    *,
    days: int,
    use_current_value_today: bool = False,
) -> None:
    """
    플랫폼별 자산가치 시계열 차트를 렌더링합니다.

    - 스택 영역(면적 합계가 총 자산)
    - 옵션 use_current_value_today=True이면 오늘 값을 최신 보유 스냅샷으로 반영
    - selected_platforms가 주어지면 해당 플랫폼만 표시
    """
    rows = get_portfolio_timeseries_by_platform(db, days=int(days))
    if not rows:
        st.info("자산 추이 데이터가 없습니다.")
        return

    df = pd.DataFrame(rows).rename(
        columns={"date": "날짜", "platform": "플랫폼", "total_krw": "자산가치"}
    )
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"]).sort_values(["날짜", "플랫폼"])  # 안전 장치

    # 오늘 값 반영(선택): 최신 스냅샷 기반
    if use_current_value_today:
        try:
            snapshot = get_asset_distribution_by_platform(db)
            today_map = {r["platform"]: float(r["amount"]) for r in snapshot}
            if today_map:
                df = _apply_today_snapshot(df, today_values=today_map)
        except Exception:
            # 스냅샷 오류는 치명적이지 않으므로 무시하고 계속 진행
            pass

    # 플랫폼별 결측일 보간 처리 (area 규칙 적용)
    df_ff = _ffill_by_platform(df)

    title = f"최근 {int(days)}일 플랫폼별 자산가치 (KRW)"
    # 면적 차트: 기본 색상 체계(Plotly 기본) 사용 + 총계 라인 오버레이
    fig = px.area(
        df_ff,
        x="날짜",
        y="자산가치",
        color="플랫폼",
        title=title,
        labels={"자산가치": "자산가치 (KRW)", "날짜": "날짜", "플랫폼": "플랫폼"},
    )

    # 총계 시리즈 계산(보간 완료 데이터 기준)
    wide = df_ff.pivot(index="날짜", columns="플랫폼", values="자산가치")
    total_series = wide.sum(axis=1, skipna=True)
    # 총계 라인: px.line으로 생성 후 트레이스만 추가해 오버레이
    total_df = total_series.reset_index()
    total_df.columns = ["날짜", "자산가치"]
    fig_total = px.line(total_df, x="날짜", y="자산가치")
    for tr in getattr(fig_total, "data", []) or []:
        tr.name = "총 자산"
        tr.showlegend = True
        tr.legendgroup = "총 자산"
    if hasattr(fig, "add_traces"):
        fig.add_traces(getattr(fig_total, "data", []) or [])

    fig.update_layout(yaxis_tickformat="₩,")
    st.plotly_chart(fig, use_container_width=True)
