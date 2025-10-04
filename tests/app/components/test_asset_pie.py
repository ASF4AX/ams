import pytest
from types import SimpleNamespace


@pytest.fixture
def asset_pie_mod(monkeypatch, components_stubs):
    import app.components.asset_pie as asset_pie

    return asset_pie


@pytest.fixture
def st_mocks(streamlit_mocks, asset_pie_mod):
    return streamlit_mocks(asset_pie_mod)


@pytest.fixture
def px_pie_spy(px_spy_factory, asset_pie_mod):
    return px_spy_factory(asset_pie_mod, "pie")


class TestRender:
    @pytest.mark.parametrize(
        "func_name",
        [
            "render_asset_allocation_pie_by_name",
            "render_asset_allocation_pie_by_category",
        ],
    )
    def test_empty_assets_shows_info_and_no_chart(
        self, asset_pie_mod, st_mocks, px_pie_spy, func_name
    ):
        info_mock, plotly_chart_mock = st_mocks
        getattr(asset_pie_mod, func_name)([])

        info_mock.assert_called_once_with("자산 분포 데이터가 없습니다.")
        plotly_chart_mock.assert_not_called()
        px_pie_spy.assert_not_called()

    @pytest.mark.parametrize(
        "func_name, assets, expected_labels, expected_values",
        [
            (
                "render_asset_allocation_pie_by_name",
                [
                    SimpleNamespace(name="A", eval_amount_krw=100.0),
                    SimpleNamespace(name="A", eval_amount_krw=0.0),
                    SimpleNamespace(name="A", eval_amount_krw=-5.0),
                    SimpleNamespace(name="B", eval_amount_krw=50.0),
                    SimpleNamespace(name="ETH", eval_amount_krw=10.0),
                    SimpleNamespace(name="BTC", eval_amount_krw=20.0),
                    SimpleNamespace(name="ETH", eval_amount_krw=5.0),
                ],
                ["A", "B", "BTC", "ETH"],
                [100.0, 50.0, 20.0, 15.0],
            ),
            (
                "render_asset_allocation_pie_by_category",
                [
                    SimpleNamespace(category=None, eval_amount_krw=10.0),  # -> 기타
                    SimpleNamespace(category="기타", eval_amount_krw=5.0),
                    SimpleNamespace(category="A", eval_amount_krw=100.0),
                ],
                ["A", "기타"],
                [100.0, 15.0],
            ),
        ],
    )
    def test_plots_expected_labels_values(
        self,
        asset_pie_mod,
        st_mocks,
        px_pie_spy,
        func_name,
        assets,
        expected_labels,
        expected_values,
    ):
        info_mock, plotly_chart_mock = st_mocks
        getattr(asset_pie_mod, func_name)(assets)
        px_pie_spy.assert_called_once()
        info_mock.assert_not_called()
        plotly_chart_mock.assert_called_once()
        fig = plotly_chart_mock.call_args[0][0]
        assert list(fig.data[0].labels) == expected_labels
        assert list(fig.data[0].values) == expected_values

    # 통일성: 자산 스텁은 SimpleNamespace만 사용

    def test_renderer_shows_info_when_no_positive(
        self, asset_pie_mod, st_mocks, px_pie_spy
    ):
        """비양수만 있는 경우 안내 메시지 표시, 차트 미렌더링."""
        info_mock, plotly_chart_mock = st_mocks
        assets = [
            SimpleNamespace(name="A", eval_amount_krw=0.0),
            SimpleNamespace(name="B", eval_amount_krw=-1.0),
        ]
        asset_pie_mod.render_asset_allocation_pie_by_name(assets)
        info_mock.assert_called_once_with("자산 분포 데이터가 없습니다.")
        plotly_chart_mock.assert_not_called()
        px_pie_spy.assert_not_called()


class TestCompute:
    def test_compute_helper_basic(self, asset_pie_mod):
        assets = [
            SimpleNamespace(name="A", eval_amount_krw=100.0),
            SimpleNamespace(name="A", eval_amount_krw=0.0),
            SimpleNamespace(name="A", eval_amount_krw=-5.0),
            SimpleNamespace(name="B", eval_amount_krw=50.0),
            SimpleNamespace(name="ETH", eval_amount_krw=10.0),
            SimpleNamespace(name="BTC", eval_amount_krw=20.0),
            SimpleNamespace(name="ETH", eval_amount_krw=5.0),
        ]
        labels, values = asset_pie_mod._compute_labels_values_by(
            assets, lambda a: a.name
        )
        assert labels == ["A", "B", "BTC", "ETH"]
        assert values == [100.0, 50.0, 20.0, 15.0]

    def test_compute_helper_all_non_positive(self, asset_pie_mod):
        assets = [
            SimpleNamespace(name="A", eval_amount_krw=0.0),
            SimpleNamespace(name="B", eval_amount_krw=-1.0),
        ]
        labels, values = asset_pie_mod._compute_labels_values_by(
            assets, lambda a: a.name
        )
        assert labels == []
        assert values == []

    def test_compute_helper_category_none_to_others(self, asset_pie_mod):
        assets = [
            SimpleNamespace(category=None, eval_amount_krw=10.0),
            SimpleNamespace(category="기타", eval_amount_krw=5.0),
            SimpleNamespace(category="A", eval_amount_krw=100.0),
        ]
        labels, values = asset_pie_mod._compute_labels_values_by(
            assets, lambda a: (a.category or "기타")
        )
        assert labels[0] == "A" and values[0] == 100.0
        assert labels[1] == "기타" and values[1] == 15.0
