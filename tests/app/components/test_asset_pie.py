import sys
from types import ModuleType, SimpleNamespace
from typing import List, Any, Tuple


def _make_asset(name: str, amount: float) -> Any:
    return SimpleNamespace(name=name, eval_amount_krw=amount)


def _inject_stubs(monkeypatch) -> None:
    """Inject lightweight stubs for streamlit and plotly.express before import."""
    # streamlit stub
    st_mod = ModuleType("streamlit")
    # default no-op; tests will monkeypatch to capture
    st_mod.info = lambda *args, **kwargs: None
    st_mod.plotly_chart = lambda *args, **kwargs: None
    sys.modules["streamlit"] = st_mod

    # plotly.express stub
    px_mod = ModuleType("plotly.express")

    class FakeTrace:
        def __init__(self, labels: List[Any], values: List[float]):
            self.labels = list(labels)
            self.values = list(values)
            self.textposition = None
            self.textinfo = None

    class FakeLayoutTitle:
        def __init__(self, text: str):
            self.text = text

    class FakeLayout:
        def __init__(self, title: str):
            self.title = FakeLayoutTitle(title)

    class FakeFigure:
        def __init__(self, labels: List[Any], values: List[float], title: str):
            self.data = [FakeTrace(labels, values)]
            self.layout = FakeLayout(title)

        def update_traces(self, **kwargs):
            for tr in self.data:
                for k, v in kwargs.items():
                    setattr(tr, k, v)

    def _px_pie(
        df, *, values: str, names: str, title: str, color_discrete_sequence=None
    ):
        labels = list(df[names])
        vals = list(df[values])
        return FakeFigure(labels, vals, title)

    # colors placeholder
    px_mod.colors = SimpleNamespace(qualitative=SimpleNamespace(Pastel=["#ccc"]))
    px_mod.pie = _px_pie

    # Ensure parent package exists for import resolution
    plotly_pkg = ModuleType("plotly")
    sys.modules["plotly"] = plotly_pkg
    sys.modules["plotly.express"] = px_mod


def _capture_st_on_module(monkeypatch, asset_pie_module) -> Tuple[List[str], List[Any]]:
    infos: List[str] = []
    charts: List[Any] = []

    def fake_info(msg: str):
        infos.append(str(msg))

    def fake_plotly_chart(fig, use_container_width: bool = False):
        charts.append(fig)

    # Patch the exact module-level 'st' used by the component
    monkeypatch.setattr(asset_pie_module.st, "info", fake_info)
    monkeypatch.setattr(asset_pie_module.st, "plotly_chart", fake_plotly_chart)

    return infos, charts


def _pie_labels_values(fig: Any):
    assert fig.data, "Pie figure should contain data traces"
    trace = fig.data[0]
    # Plotly may store labels/values in different array-like forms; coerce to list
    labels_attr = getattr(trace, "labels", None)
    values_attr = getattr(trace, "values", None)
    labels = list(labels_attr) if labels_attr is not None else []
    values = list(values_attr) if values_attr is not None else []
    return labels, values


def test_empty_assets_shows_info_and_no_chart(monkeypatch):
    _inject_stubs(monkeypatch)
    import app.components.asset_pie as asset_pie

    infos, charts = _capture_st_on_module(monkeypatch, asset_pie)
    asset_pie.render_asset_allocation_pie_by_name([])

    assert infos == ["자산 분포 데이터가 없습니다."], "Should show empty info message"
    assert charts == [], "Should not render a chart when no data"


def test_aggregates_filters_and_sorts(monkeypatch):
    _inject_stubs(monkeypatch)
    import app.components.asset_pie as asset_pie

    # Includes duplicates, zero/negative, and multiple names to verify
    # aggregation, filtering, and descending sort by total amount.
    assets = [
        _make_asset("A", 100.0),
        _make_asset("A", 0.0),
        _make_asset("A", -5.0),
        _make_asset("B", 50.0),
        _make_asset("ETH", 10.0),
        _make_asset("BTC", 20.0),
        _make_asset("ETH", 5.0),
    ]

    infos, charts = _capture_st_on_module(monkeypatch, asset_pie)
    asset_pie.render_asset_allocation_pie_by_name(assets)

    assert infos == []
    assert len(charts) == 1
    labels, values = _pie_labels_values(charts[0])

    # Expected aggregation and sort order: A(100), B(50), BTC(20), ETH(15)
    assert labels == ["A", "B", "BTC", "ETH"]
    assert values == [100.0, 50.0, 20.0, 15.0]
