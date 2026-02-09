from __future__ import annotations

import math

from dags.tasks.kis import (
    calculate_eval_amount_krw,
    process_kis_assets,
    process_kis_exchange_rates,
    process_kis_overseas_assets,
    process_kis_overseas_cash,
)


def test_process_kis_assets_converts_numeric_fields_and_appends_deposit() -> None:
    balance_data = {
        "output1": [
            {
                "pdno": "005930",
                "prpr": "70200",
                "evlu_amt": "1404000",
                "hldg_qty": "20",
                "pchs_avg_pric": "65000",
                "evlu_pfls_amt": "104000",
                "evlu_pfls_rt": "7.42",
                "prdt_name": "삼성전자",
            },
            {
                "pdno": None,
                "prpr": "1000",
                "evlu_amt": "1000",
                "hldg_qty": "1",
            },
        ],
        "output2": [
            {"prvs_rcdl_excc_amt": "500000", "dnca_tot_amt": "999999"},
        ],
    }

    assets = process_kis_assets(balance_data, revision=3)

    assert len(assets) == 2
    stock_asset = next(item for item in assets if item["symbol"] == "005930")
    assert stock_asset["platform"] == "한국투자증권"
    assert stock_asset["category"] == "국내주식"
    assert stock_asset["name"] == "삼성전자"
    assert math.isclose(stock_asset["quantity"], 20.0)
    assert math.isclose(stock_asset["current_price"], 70200.0)
    assert math.isclose(stock_asset["evaluation_amount"], 1404000.0)
    assert math.isclose(stock_asset["avg_price"], 65000.0)
    assert math.isclose(stock_asset["profit_loss"], 104000.0)
    assert math.isclose(stock_asset["profit_loss_rate"], 7.42)
    assert stock_asset["currency"] == "KRW"
    assert stock_asset["revision"] == 3

    deposit_asset = next(item for item in assets if item["symbol"] == "KRW")
    assert deposit_asset == {
        "symbol": "KRW",
        "platform": "한국투자증권",
        "quantity": 500000.0,
        "current_price": 1,
        "evaluation_amount": 500000.0,
        "category": "현금",
        "name": "원화 예수금",
        "currency": "KRW",
        "revision": 3,
    }


def test_process_kis_assets_supports_dict_summary() -> None:
    balance_data = {
        "output1": [],
        "output2": {"prvs_rcdl_excc_amt": "123.45", "dnca_tot_amt": "999999"},
    }

    assets = process_kis_assets(balance_data, revision=7)

    assert assets == [
        {
            "symbol": "KRW",
            "platform": "한국투자증권",
            "quantity": 123.45,
            "current_price": 1,
            "evaluation_amount": 123.45,
            "category": "현금",
            "name": "원화 예수금",
            "currency": "KRW",
            "revision": 7,
        }
    ]


def test_process_kis_assets_ignores_dnca_when_d2_missing() -> None:
    balance_data = {
        "output1": [],
        "output2": {"dnca_tot_amt": "1000", "nxdy_excc_amt": "500"},
    }

    assets = process_kis_assets(balance_data, revision=7)

    assert assets == []


def test_process_kis_overseas_assets_deduplicates_and_derives_fields() -> None:
    stock_list = [
        {
            "pdno": "AAPL",
            "cblc_qty13": "2",
            "ovrs_now_pric1": "150.5",
            "avg_unpr3": "120.1",
            "evlu_pfls_amt2": "60.2",
            "evlu_pfls_rt1": "10.3",
            "natn_kor_name": "미국",
            "prdt_name": "애플",
            "buy_crcy_cd": "USD",
            "ovrs_excg_cd": "NASDAQ",
        },
        {
            "pdno": "AAPL",
            "cblc_qty13": "5",
            "ovrs_now_pric1": "170.0",
            "buy_crcy_cd": "USD",
            "ovrs_excg_cd": "NASDAQ",
        },
        {
            "pdno": "TSLA",
            "cblc_qty13": "3",
            "ovrs_now_pric1": "not-a-number",
            "avg_unpr3": "",
            "evlu_pfls_amt2": None,
            "evlu_pfls_rt1": "abc",
            "prdt_name": "테슬라",
            "buy_crcy_cd": "USD",
            "ovrs_excg_cd": "",
        },
        {
            "pdno": "BABA",
            "cblc_qty13": "0",
            "ovrs_now_pric1": "80",
            "buy_crcy_cd": "HKD",
            "ovrs_excg_cd": "NYSE",
        },
    ]

    assets = process_kis_overseas_assets(stock_list, revision=11)

    assert len(assets) == 2

    aapl = next(item for item in assets if item["symbol"] == "AAPL")
    assert math.isclose(aapl["quantity"], 2.0)
    assert math.isclose(aapl["current_price"], 150.5)
    assert math.isclose(aapl["evaluation_amount"], 301.0)
    assert math.isclose(aapl["avg_price"], 120.1)
    assert math.isclose(aapl["profit_loss"], 60.2)
    assert math.isclose(aapl["profit_loss_rate"], 10.3)
    assert aapl["category"] == "미국주식"
    assert aapl["name"] == "애플"
    assert aapl["exchange"] == "NASDAQ"
    assert aapl["currency"] == "USD"
    assert aapl["revision"] == 11

    tsla = next(item for item in assets if item["symbol"] == "TSLA")
    assert math.isclose(tsla["quantity"], 3.0)
    assert math.isclose(tsla["current_price"], 0.0)
    assert math.isclose(tsla["evaluation_amount"], 0.0)
    assert math.isclose(tsla["avg_price"], 0.0)
    assert math.isclose(tsla["profit_loss"], 0.0)
    assert math.isclose(tsla["profit_loss_rate"], 0.0)
    assert tsla["category"] == "해외주식"
    assert tsla["name"] == "테슬라"
    assert tsla["exchange"] == ""
    assert tsla["currency"] == "USD"
    assert tsla["revision"] == 11


def test_process_kis_overseas_cash_skips_zero_and_duplicates() -> None:
    cash_list = [
        {"crcy_cd": "USD", "frcr_dncl_amt_2": "100.5"},
        {"crcy_cd": "USD", "frcr_dncl_amt_2": "200"},
        {"crcy_cd": "JPY", "frcr_dncl_amt_2": "0"},
        {"crcy_cd": "AUD", "frcr_dncl_amt_2": "50"},
    ]

    assets = process_kis_overseas_cash(cash_list, revision=13)

    assert assets == [
        {
            "symbol": "USD",
            "platform": "한국투자증권",
            "quantity": 100.5,
            "current_price": 1,
            "evaluation_amount": 100.5,
            "category": "현금",
            "name": "달러 예수금",
            "currency": "USD",
            "revision": 13,
        },
        {
            "symbol": "AUD",
            "platform": "한국투자증권",
            "quantity": 50.0,
            "current_price": 1,
            "evaluation_amount": 50.0,
            "category": "현금",
            "name": "AUD 예수금",
            "currency": "AUD",
            "revision": 13,
        },
    ]


def test_process_kis_exchange_rates_filters_invalid_entries() -> None:
    cash_list = [
        {"crcy_cd": "USD", "frst_bltn_exrt": "1300.5"},
        {"crcy_cd": "USD", "frst_bltn_exrt": "1400"},
        {"crcy_cd": "JPY", "frst_bltn_exrt": "0"},
        {"crcy_cd": "EUR", "frst_bltn_exrt": "1430.2"},
        {"crcy_cd": "GBP", "frst_bltn_exrt": "-1"},
        {"crcy_cd": "CHF", "frst_bltn_exrt": "not-a-number"},
        {"crcy_cd": None, "frst_bltn_exrt": "1200"},
    ]

    rates = process_kis_exchange_rates(cash_list)

    assert rates == [
        {"base_currency": "USD", "target_currency": "KRW", "rate": 1300.5},
        {"base_currency": "EUR", "target_currency": "KRW", "rate": 1430.2},
    ]


def test_calculate_eval_amount_krw_uses_rates_and_leaves_missing_values() -> None:
    assets = [
        {"symbol": "BTC", "currency": "USD", "evaluation_amount": 2.5},
        {"symbol": "KRW", "currency": "KRW", "evaluation_amount": 1000},
        {"symbol": "ETH", "currency": "EUR", "evaluation_amount": 3.0},
        {"symbol": "DOGE", "currency": "JPY", "evaluation_amount": 1000},
        {"symbol": "XRP", "currency": None, "evaluation_amount": 5},
        {"symbol": "ADA", "currency": "USD", "evaluation_amount": None},
    ]
    rates = {"USD": 1300, "EUR": 1400}

    updated = calculate_eval_amount_krw(assets, rates)

    btc = next(item for item in updated if item["symbol"] == "BTC")
    assert btc["eval_amount_krw"] == 3250.0

    krw = next(item for item in updated if item["symbol"] == "KRW")
    assert krw["eval_amount_krw"] == 1000

    eth = next(item for item in updated if item["symbol"] == "ETH")
    assert eth["eval_amount_krw"] == 4200.0

    doge = next(item for item in updated if item["symbol"] == "DOGE")
    assert "eval_amount_krw" not in doge

    xrp = next(item for item in updated if item["symbol"] == "XRP")
    assert "eval_amount_krw" not in xrp

    ada = next(item for item in updated if item["symbol"] == "ADA")
    assert "eval_amount_krw" not in ada
