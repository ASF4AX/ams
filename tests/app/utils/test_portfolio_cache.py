from app.utils.portfolio_cache import MDD_NOTE, build_portfolio_cache


def test_build_portfolio_cache_shapes_and_rounds_values():
    cache = build_portfolio_cache(
        summary={
            "as_of": "2026-06-10",
            "total_krw": 12345.67,
            "by_platform": [{"platform": "한국투자증권", "amount_krw": 10000.4}],
            "by_category": [{"category": "미국주식", "amount_krw": 9999.6}],
        },
        current_assets=[
            {
                "symbol": "IONQ",
                "name": "아이온큐",
                "platform": "한국투자증권",
                "category": "미국주식",
                "quantity": 2,
                "evaluation_amount": 7,
                "eval_amount_krw": 7000.3,
                "avg_price": 2.5,
            },
            {
                "symbol": "USD",
                "name": "달러 예수금",
                "platform": "한국투자증권",
                "category": "현금",
                "quantity": 10.5,
                "evaluation_amount": 10.5,
                "eval_amount_krw": 3000.2,
            },
            {
                "symbol": "DUST",
                "name": "영점자산",
                "platform": "테스트",
                "category": "암호화폐",
                "quantity": 1,
                "evaluation_amount": 0,
                "eval_amount_krw": 0,
            },
        ],
        return_7d={"return_rate_pct": -1.234},
        return_30d={"return_rate_pct": 5.678},
        mdd_30d={"maximum_drawdown_pct": -3.456},
        as_of="2026-06-11T09:00:00+09:00",
    )

    assert cache["summary"] == {
        "as_of_date": "2026-06-10",
        "total_assets_krw": 12346,
        "item_count": 2,
        "total_cost_krw": 5000,
        "total_unrealized_pnl_krw": 2000,
        "total_return_pct": 40.0,
    }
    assert cache["returns"] == {"d7_pct": -1.23, "d30_pct": 5.68}
    assert cache["mdd"] == {
        "measured_30d_pct": -3.46,
        "api_raw_pct": None,
        "note": MDD_NOTE,
    }
    assert cache["by_platform"] == [{"platform": "한국투자증권", "value_krw": 10000}]
    assert cache["by_asset_class"] == [{"class": "미국주식", "value_krw": 10000}]
    assert cache["positions"] == [
        {
            "ticker": "IONQ",
            "name": "아이온큐",
            "platform": "한국투자증권",
            "asset_class": "미국주식",
            "shares": 2.0,
            "value_krw": 7000,
            "weight_pct": 56.7,
            "cost_basis_krw": 5000,
            "avg_price": 2.5,
            "unrealized_pnl_krw": 2000,
            "return_pct": 40.0,
        },
        {
            "ticker": "USD",
            "name": "달러 예수금",
            "platform": "한국투자증권",
            "asset_class": "현금",
            "shares": 10.5,
            "value_krw": 3000,
            "weight_pct": 24.3,
            "cost_basis_krw": None,
            "avg_price": None,
            "unrealized_pnl_krw": None,
            "return_pct": None,
        },
    ]


def test_build_portfolio_cache_keeps_null_pct_when_total_is_zero():
    cache = build_portfolio_cache(
        summary={"as_of": "2026-06-10", "total_krw": 0, "by_platform": [], "by_category": []},
        current_assets=[
            {
                "symbol": "KRW",
                "name": "원화",
                "platform": "수동등록",
                "category": "현금",
                "quantity": 1,
                "eval_amount_krw": 1,
            }
        ],
        return_7d={"return_rate_pct": None},
        return_30d={"return_rate_pct": None},
        mdd_30d={"maximum_drawdown_pct": None},
        as_of="2026-06-11T09:00:00+09:00",
    )

    assert cache["positions"][0]["weight_pct"] is None
    assert cache["positions"][0]["cost_basis_krw"] is None
    assert cache["returns"] == {"d7_pct": None, "d30_pct": None}
    assert cache["mdd"]["measured_30d_pct"] is None
    assert cache["summary"]["total_cost_krw"] is None
    assert cache["summary"]["total_unrealized_pnl_krw"] is None
    assert cache["summary"]["total_return_pct"] is None
