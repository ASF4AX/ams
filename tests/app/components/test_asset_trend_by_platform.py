import pytest
from datetime import date, timedelta


@pytest.fixture
def mod(monkeypatch, components_stubs):
    import app.components.asset_trend_by_platform as m

    return m


@pytest.fixture
def st_mocks(streamlit_mocks, mod):
    return streamlit_mocks(mod)


@pytest.fixture
def px_area_spy(px_spy_factory, mod):
    return px_spy_factory(mod, "area")


@pytest.fixture
def render_df_factory(mod, px_area_spy, monkeypatch):
    """Patch inputs, render, and return the DataFrame passed to px.area."""

    def _render(rows, snapshot=None, *, days=7, use_today=False):
        monkeypatch.setattr(
            mod,
            "get_portfolio_timeseries_by_platform",
            lambda db, days=None: rows,
        )
        if snapshot is not None:
            monkeypatch.setattr(
                mod, "get_asset_distribution_by_platform", lambda db: snapshot
            )
        mod.render_platform_timeseries(
            db=None, days=days, use_current_value_today=use_today
        )
        return px_area_spy.call_args.args[0]

    return _render


def _rows_for(df, platform):
    d = df[df["플랫폼"] == platform].reset_index(drop=True)
    return [str(x.date()) for x in d["날짜"]], list(d["자산가치"])


def _last_by_platform(df):
    return (
        df.sort_values(["플랫폼", "날짜"]).groupby("플랫폼").tail(1).set_index("플랫폼")
    )


class TestPlatformTrend:
    def test_empty_shows_info(self, mod, st_mocks, px_area_spy, monkeypatch):
        info_mock, chart_mock = st_mocks
        monkeypatch.setattr(
            mod,
            "get_portfolio_timeseries_by_platform",
            lambda db, days: [],
        )

        mod.render_platform_timeseries(db=None, days=30)

        info_mock.assert_called_once_with("자산 추이 데이터가 없습니다.")
        chart_mock.assert_not_called()
        px_area_spy.assert_not_called()

    def test_ffill_per_platform_area(self, mod, st_mocks, render_df_factory):
        info_mock, chart_mock = st_mocks
        df = render_df_factory(
            [
                {"date": "2025-01-01", "platform": "A", "total_krw": 1000},
                {"date": "2025-01-03", "platform": "A", "total_krw": 1100},
                {"date": "2025-01-02", "platform": "B", "total_krw": 500},
            ]
        )

        dates_a, vals_a = _rows_for(df, "A")
        assert dates_a == ["2025-01-01", "2025-01-02", "2025-01-03"]
        assert vals_a == [1000, 1000, 1100]

        dates_b, vals_b = _rows_for(df, "B")
        assert dates_b == ["2025-01-01", "2025-01-02", "2025-01-03"]
        # area 규칙: 선행 구간은 0으로 채움
        assert vals_b == [0, 500, 500]

        info_mock.assert_not_called()
        chart_mock.assert_called_once()

    def test_today_snapshot_applied(self, mod, st_mocks, render_df_factory):
        today = date.today()
        yday = today - timedelta(days=1)
        df = render_df_factory(
            [
                {"date": yday.isoformat(), "platform": "A", "total_krw": 1000},
                {"date": yday.isoformat(), "platform": "B", "total_krw": 2000},
            ],
            snapshot=[
                {"platform": "A", "amount": 1111.0},
                {"platform": "B", "amount": 2222.0},
            ],
            use_today=True,
        )
        last = _last_by_platform(df)
        latest_dates = last["날짜"].dt.date.to_dict()
        assert all(d == today for d in latest_dates.values())
        latest_values = last["자산가치"].to_dict()
        assert latest_values["A"] == 1111.0
        assert latest_values["B"] == 2222.0

    def test_mixed_today_overwrite_and_append(self, mod, st_mocks, render_df_factory):
        """A는 오늘 존재→덮어쓰기, B는 없음→오늘 행 추가 후 스냅샷 값 반영."""
        today = date.today()
        yday = today - timedelta(days=1)
        df = render_df_factory(
            [
                {"date": today.isoformat(), "platform": "A", "total_krw": 1000},
                {"date": yday.isoformat(), "platform": "B", "total_krw": 2000},
            ],
            snapshot=[
                {"platform": "A", "amount": 1111.0},
                {"platform": "B", "amount": 2222.0},
            ],
            use_today=True,
        )

        last = _last_by_platform(df)
        latest_dates = last["날짜"].dt.date.to_dict()
        latest_values = last["자산가치"].to_dict()
        assert latest_dates["A"] == today
        assert latest_values["A"] == 1111.0
        assert latest_dates["B"] == today
        assert latest_values["B"] == 2222.0

    def test_partial_snapshot_overwrite_only_present_platforms(
        self, mod, st_mocks, render_df_factory
    ):
        """스냅샷에 포함된 플랫폼만 덮어쓰기, 나머지는 기존 유지."""
        info_mock, chart_mock = st_mocks
        today = date.today()
        df = render_df_factory(
            [
                {"date": today.isoformat(), "platform": "A", "total_krw": 1000},
                {"date": today.isoformat(), "platform": "B", "total_krw": 2000},
            ],
            snapshot=[
                {"platform": "A", "amount": 1111.0},
            ],
            use_today=True,
        )
        last = _last_by_platform(df)
        latest_dates = last["날짜"].dt.date.to_dict()
        latest_values = last["자산가치"].to_dict()
        assert latest_dates["A"] == today
        assert latest_values["A"] == 1111.0
        assert latest_dates["B"] == today
        assert latest_values["B"] == 2000.0

    def test_empty_snapshot_makes_no_change(self, mod, st_mocks, render_df_factory):
        """스냅샷이 비어있으면 오늘 값 추가/덮어쓰기 없이 그대로 유지."""
        today = date.today()
        yday = today - timedelta(days=1)
        df = render_df_factory(
            [
                {"date": yday.isoformat(), "platform": "A", "total_krw": 1000},
                {"date": yday.isoformat(), "platform": "B", "total_krw": 2000},
            ],
            snapshot=[],
            use_today=True,
        )
        last = _last_by_platform(df)
        latest_dates = last["날짜"].dt.date.to_dict()
        assert all(d == yday for d in latest_dates.values())
