"""포맷팅 관련 유틸리티 함수들"""

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
