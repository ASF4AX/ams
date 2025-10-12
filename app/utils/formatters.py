"""포맷팅 관련 유틸리티 함수들"""

from __future__ import annotations

import pandas as pd
from typing import Callable, Mapping, Sequence, Optional

# 통화 기호 매핑
CURRENCY_SYMBOLS = {
    "KRW": "₩",
    "USD": "$",
    "EUR": "€",
    "JPY": "¥",
    "CNY": "¥",
    "BTC": "₿",
}


def format_currency(amount: float, currency: str) -> str:
    """통화에 맞는 기호와 포맷으로 금액을 표시"""
    if amount is None:
        return ""
    if currency is None:
        return f"{amount:,.2f}"  # 통화가 없는 경우 숫자만 표시
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if currency == "KRW":
        return f"{symbol}{amount:,.0f}"
    else:
        return f"{symbol}{amount:,.2f}"


def format_profit_loss(amount: float) -> str:
    """손익을 색상과 함께 표시"""
    if amount is None:
        return ""
    return f"{amount:,.0f}"


def format_profit_loss_rate(rate: float) -> str:
    """손익률을 색상과 함께 표시"""
    if rate is None:
        return ""
    return f"{rate:,.2f}%"


def color_negative_red(val):
    """음수는 파란색, 양수는 빨간색으로 표시"""
    if isinstance(val, (int, float)):
        if val < 0:
            color = "blue"
        elif val > 0:
            color = "red"
        else:
            color = "black"
        return f"color: {color}"
    return ""


def add_currency_display_columns(
    df: pd.DataFrame,
    specs: list[tuple[str, str, str]],
) -> pd.DataFrame:
    """행마다 통화 포맷을 적용한 표시용 컬럼을 추가합니다.

    - df: DataFrame (제자리 수정 후 반환)
    - specs: (금액컬럼, 통화컬럼, 출력컬럼) 목록
    누락된 컬럼은 건너뜁니다. 예: add_currency_display_columns(df, [("가격", "통화", "가격_표시"), ("금액", "통화", "금액_표시")])
    """
    for amount_col, currency_col, out_col in specs:
        if amount_col in df.columns and currency_col in df.columns:
            df[out_col] = pd.Series(
                [
                    format_currency(a, c)
                    for a, c in zip(df[amount_col], df[currency_col])
                ],
                index=df[amount_col].index,
            )
    return df


def make_row_color_styler(
    df: pd.DataFrame,
    key_col: str,
    value_to_color: Mapping[object, str],
    *,
    target_cols: Optional[Sequence[str]] = None,
) -> Callable[[pd.Series], pd.Series]:
    """범용 행 색상 Styler.

    - key_col 값 → value_to_color 매핑으로 글자색(color) 결정
    - target_cols: 스타일을 적용할 컬럼들(미지정 시 적용하지 않음)
    """

    all_cols = list(df.columns)
    targets = list(target_cols) if target_cols is not None else []

    def _styler(row: pd.Series) -> pd.Series:
        key = row.get(key_col, None)
        color = value_to_color.get(key, None)
        styles = {col: "" for col in all_cols}
        if color:
            value = f"color: {color}"
            for col in targets:
                if col in styles:
                    styles[col] = value
        return pd.Series(styles)

    return _styler
