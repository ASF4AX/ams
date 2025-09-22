import math

import pytest

from app.utils.formatters import (
    color_negative_red,
    format_currency,
    format_profit_loss,
    format_profit_loss_rate,
)


@pytest.mark.parametrize(
    "amount,currency,expected",
    [
        (1234567.89, "KRW", "₩1,234,568"),
        (1234.567, "USD", "$1,234.57"),
        (1234.5, "BTC", "₿1,234.50"),
        (1234.5, "", "1,234.50"),
        (1234.5, None, "1,234.50"),
        (None, "KRW", ""),
        (1000, "ABC", "ABC1,000.00"),
    ],
)
def test_format_currency(amount, currency, expected):
    assert format_currency(amount, currency) == expected


@pytest.mark.parametrize(
    "amount,expected",
    [
        (1000000.4, "1,000,000"),
        (-1250.0, "-1,250"),
        (0, "0"),
        (None, ""),
    ],
)
def test_format_profit_loss(amount, expected):
    assert format_profit_loss(amount) == expected


@pytest.mark.parametrize(
    "rate,expected",
    [
        (12.3456, "12.35%"),
        (-7.891, "-7.89%"),
        (0, "0.00%"),
        (None, ""),
    ],
)
def test_format_profit_loss_rate(rate, expected):
    assert format_profit_loss_rate(rate) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (-1, "color: blue"),
        (-0.5, "color: blue"),
        (0, "color: black"),
        (0.0, "color: black"),
        (5, "color: red"),
        (math.pi, "color: red"),
        ("not-a-number", ""),
    ],
)
def test_color_negative_red(value, expected):
    assert color_negative_red(value) == expected
