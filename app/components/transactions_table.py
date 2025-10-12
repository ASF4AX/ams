import streamlit as st
import pandas as pd

from utils.formatters import (
    add_currency_display_columns,
    make_row_color_styler,
)


def render_transactions_table(transactions: list, include_memo: bool = True) -> None:
    """거래 리스트를 표준 테이블로 렌더링합니다.

    - include_memo: True면 메모 컬럼을 표시합니다.
    - "종류" 컬럼은 값(입금/출금)에 따라 색상 지정합니다.
    """
    rows = []
    for tx in transactions or []:
        asset = getattr(tx, "asset", None)
        currency = getattr(asset, "currency", None) or ""
        row = {
            "날짜": tx.transaction_date.strftime("%Y-%m-%d %H:%M"),
            "자산": getattr(asset, "name", "N/A"),
            "종류": tx.transaction_type,
            "수량": tx.quantity,
            "가격": tx.price,
            "금액": tx.amount,
            "통화": currency,
        }
        if include_memo:
            row["메모"] = tx.memo if tx.memo else ""
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("표시할 거래가 없습니다.")
        return

    # 표시용 문자열 컬럼 추가 (숫자 컬럼은 정렬/집계용으로 유지)
    specs = [("가격", "통화", "가격_표시"), ("금액", "통화", "금액_표시")]
    df = add_currency_display_columns(df, specs=specs)

    # "종류" 컬럼 색상 지정(입금=red, 출금=blue)
    target_cols = ["종류"]
    styler_fn = make_row_color_styler(
        df,
        key_col="종류",
        value_to_color={"입금": "red", "출금": "blue"},
        target_cols=target_cols,
    )
    styled_df = df.style.apply(styler_fn, axis=1)

    # 표시 컬럼 우선 순서 구성
    column_order = [
        "날짜",
        "자산",
        "종류",
        "수량",
        "가격_표시",
        "금액_표시",
        "통화",
    ] + (["메모"] if include_memo else [])

    column_config = {
        "날짜": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
    }
    if "수량" in df.columns:
        column_config["수량"] = st.column_config.NumberColumn(format="%d")
    if "가격_표시" in df.columns:
        column_config["가격_표시"] = st.column_config.TextColumn(label="가격")
    if "금액_표시" in df.columns:
        column_config["금액_표시"] = st.column_config.TextColumn(label="금액")
    if include_memo and "메모" in df.columns:
        column_config["메모"] = st.column_config.TextColumn(width="large")

    st.dataframe(
        styled_df,
        width="stretch",
        hide_index=True,
        column_order=column_order,
        column_config=column_config,
    )
