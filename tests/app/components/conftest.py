import sys
import pytest
from unittest.mock import Mock
from types import ModuleType, SimpleNamespace


def _build_streamlit_stub():
    st_mod = ModuleType("streamlit")
    st_mod.info = lambda *args, **kwargs: None
    st_mod.plotly_chart = lambda *args, **kwargs: None
    return st_mod


def _build_plotly_express_stub():
    px_mod = ModuleType("plotly.express")

    # Minimal fig/traces for pie
    def _px_pie(df, *, values: str, names: str, title: str, color_discrete_sequence=None):
        labels = list(df[names])
        values_list = list(df[values])
        trace = SimpleNamespace(labels=labels, values=values_list)
        fig = SimpleNamespace(
            data=[trace],
            layout=SimpleNamespace(title=SimpleNamespace(text=title)),
        )

        def update_traces(**kwargs):
            for tr in fig.data:
                tr.__dict__.update(kwargs)

        fig.update_traces = update_traces
        return fig

    # Minimal fig for line
    def _px_line(df, *, x: str, y: str, title: str, labels=None):
        fig = SimpleNamespace(
            data=[],
            layout=SimpleNamespace(title=SimpleNamespace(text=title)),
        )

        def update_layout(**kwargs):
            for k, v in kwargs.items():
                setattr(fig.layout, k, v)

        fig.update_layout = update_layout
        return fig

    px_colors = SimpleNamespace(qualitative=SimpleNamespace(Pastel=["#ccc"]))
    px_mod.colors = px_colors
    px_mod.pie = _px_pie
    px_mod.line = _px_line
    return px_mod


def _ensure_parent_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    plotly_pkg = ModuleType("plotly")
    monkeypatch.setitem(sys.modules, "plotly", plotly_pkg)


def _install_crud_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    crud_pkg = ModuleType("crud")
    crud_crud_mod = ModuleType("crud.crud")

    def _get_portfolio_timeseries(_db, days: int):
        return []
    def _get_total_asset_value(_db):
        return 0.0

    crud_crud_mod.get_portfolio_timeseries = _get_portfolio_timeseries
    crud_crud_mod.get_total_asset_value = _get_total_asset_value
    monkeypatch.setitem(sys.modules, "crud", crud_pkg)
    monkeypatch.setitem(sys.modules, "crud.crud", crud_crud_mod)


@pytest.fixture(scope="function")
def components_stubs(monkeypatch: pytest.MonkeyPatch):
    """Install shared stubs for Streamlit, Plotly Express, and crud.crud.

    Tests under app/components can rely on these import-time stubs.
    """
    _ensure_parent_packages(monkeypatch)
    monkeypatch.setitem(sys.modules, "streamlit", _build_streamlit_stub())
    monkeypatch.setitem(sys.modules, "plotly.express", _build_plotly_express_stub())
    _install_crud_stub(monkeypatch)
    yield


@pytest.fixture(scope="function")
def streamlit_mocks(monkeypatch: pytest.MonkeyPatch):
    """Factory fixture to patch Streamlit methods on a target module.

    Usage: info_mock, chart_mock = streamlit_mocks(module)
    """

    def _apply(module):
        info_mock = Mock()
        chart_mock = Mock()
        monkeypatch.setattr(module.st, "info", info_mock)
        monkeypatch.setattr(module.st, "plotly_chart", chart_mock)
        return info_mock, chart_mock

    return _apply


@pytest.fixture(scope="function")
def px_spy_factory(monkeypatch: pytest.MonkeyPatch):
    """Factory fixture to spy on a plotly.express function of a module.

    Usage: spy = px_spy_factory(module, "line" or "pie")
    """

    def _spy(module, func_name: str):
        target = getattr(module.px, func_name)
        spy = Mock(wraps=target)
        monkeypatch.setattr(module.px, func_name, spy)
        return spy

    return _spy
