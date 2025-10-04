import pytest
from unittest.mock import Mock
from datetime import date, timedelta


@pytest.fixture
def asset_trend_mod(monkeypatch, components_stubs):
    import app.components.asset_trend as asset_trend

    return asset_trend


@pytest.fixture
def st_mocks(streamlit_mocks, asset_trend_mod):
    return streamlit_mocks(asset_trend_mod)


@pytest.fixture
def px_line_spy(px_spy_factory, asset_trend_mod):
    return px_spy_factory(asset_trend_mod, "line")


class TestRenderPortfolioTimeseries:
    def test_empty_timeseries_shows_info_and_no_chart(
        self, asset_trend_mod, st_mocks, px_line_spy, monkeypatch
    ):
        info_mock, plotly_chart_mock = st_mocks
        monkeypatch.setattr(
            asset_trend_mod, "get_portfolio_timeseries", lambda db, days: []
        )

        asset_trend_mod.render_portfolio_timeseries(db=None, days=30)

        info_mock.assert_called_once_with("자산 추이 데이터가 없습니다.")
        plotly_chart_mock.assert_not_called()
        px_line_spy.assert_not_called()

    def test_plots_line_with_ffilled_gap_and_title(
        self, asset_trend_mod, st_mocks, px_line_spy, monkeypatch
    ):
        info_mock, plotly_chart_mock = st_mocks
        monkeypatch.setattr(
            asset_trend_mod,
            "get_portfolio_timeseries",
            lambda db, days: [
                {"date": "2025-01-01", "total_krw": 1000},
                {"date": "2025-01-03", "total_krw": 1100},
            ],
        )

        asset_trend_mod.render_portfolio_timeseries(db=None, days=7)

        # px.line should be called once with expected x/y and title
        px_line_spy.assert_called_once()
        kwargs = px_line_spy.call_args.kwargs
        assert kwargs["x"] == "날짜"
        assert kwargs["y"] == "자산가치"
        assert "최근 7일" in kwargs["title"]

        # Data continuity: middle date should be forward-filled
        df = px_line_spy.call_args.args[0]
        as_str = [str(d.date()) for d in df["날짜"]]
        assert as_str == ["2025-01-01", "2025-01-02", "2025-01-03"]
        assert list(df["자산가치"]) == [1000, 1000, 1100]

        # Streamlit should plot the figure and not show info
        info_mock.assert_not_called()
        plotly_chart_mock.assert_called_once()

    @pytest.mark.parametrize(
        "initial_series, use_flag, expect_last_is_today, expected_last_value, should_fetch_current_value",
        [
            pytest.param(
                lambda today: [
                    {"date": (today - timedelta(days=2)).isoformat(), "total_krw": 100},
                    {"date": (today - timedelta(days=1)).isoformat(), "total_krw": 200},
                ],
                True,
                True,
                777.0,
                True,
                id="missing_today_use_true",
            ),
            pytest.param(
                lambda today: [
                    {"date": (today - timedelta(days=2)).isoformat(), "total_krw": 100},
                    {"date": (today - timedelta(days=1)).isoformat(), "total_krw": 200},
                ],
                False,
                False,
                200.0,
                False,
                id="missing_today_use_false",
            ),
            pytest.param(
                lambda today: [
                    {"date": today.isoformat(), "total_krw": 500},
                ],
                True,
                True,
                777.0,
                True,
                id="present_today_use_true",
            ),
            pytest.param(
                lambda today: [
                    {"date": today.isoformat(), "total_krw": 500},
                ],
                False,
                True,
                500.0,
                False,
                id="present_today_use_false",
            ),
        ],
    )
    def test_today_current_value_behavior(
        self,
        asset_trend_mod,
        st_mocks,
        px_line_spy,
        monkeypatch,
        initial_series,
        use_flag,
        expect_last_is_today,
        expected_last_value,
        should_fetch_current_value,
    ):
        info_mock, plotly_chart_mock = st_mocks
        today = date.today()
        monkeypatch.setattr(
            asset_trend_mod,
            "get_portfolio_timeseries",
            lambda db, days: initial_series(today),
        )
        get_total_mock = Mock(return_value=777.0)
        monkeypatch.setattr(asset_trend_mod, "get_total_asset_value", get_total_mock)

        asset_trend_mod.render_portfolio_timeseries(
            db=None, days=7, use_current_value_today=use_flag
        )

        px_line_spy.assert_called_once()
        info_mock.assert_not_called()
        plotly_chart_mock.assert_called_once()

        if should_fetch_current_value:
            get_total_mock.assert_called_once()
        else:
            get_total_mock.assert_not_called()

        df = px_line_spy.call_args.args[0]
        last_date_str = str(df["날짜"].iloc[-1].date())

        if expect_last_is_today:
            assert last_date_str == str(today)
        else:
            # when not using current value today and missing today, last is yesterday
            assert last_date_str == str(today - timedelta(days=1))

        assert float(df["자산가치"].iloc[-1]) == expected_last_value

    def test_no_append_when_empty_even_with_flag(
        self, asset_trend_mod, st_mocks, px_line_spy, monkeypatch
    ):
        info_mock, plotly_chart_mock = st_mocks
        monkeypatch.setattr(
            asset_trend_mod, "get_portfolio_timeseries", lambda db, days: []
        )
        get_total_mock = Mock(return_value=888.0)
        monkeypatch.setattr(asset_trend_mod, "get_total_asset_value", get_total_mock)

        asset_trend_mod.render_portfolio_timeseries(
            db=None, days=7, use_current_value_today=True
        )

        info_mock.assert_called_once_with("자산 추이 데이터가 없습니다.")
        px_line_spy.assert_not_called()
        plotly_chart_mock.assert_not_called()
        get_total_mock.assert_not_called()
