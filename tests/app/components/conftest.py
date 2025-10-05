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
    def _px_pie(
        df, *, values: str, names: str, title: str, color_discrete_sequence=None
    ):
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
    def _px_line(df, *, x: str, y: str, title: str | None = None, labels=None):
        fig = SimpleNamespace(
            data=[],
            layout=SimpleNamespace(title=SimpleNamespace(text=title or "")),
        )

        def update_layout(**kwargs):
            for k, v in kwargs.items():
                setattr(fig.layout, k, v)

        fig.update_layout = update_layout
        return fig

    # Minimal fig for area (with add_traces used by tests)
    def _px_area(df, *, x: str, y: str, color: str, title: str, labels=None):
        fig = SimpleNamespace(
            data=[],
            layout=SimpleNamespace(title=SimpleNamespace(text=title)),
        )

        def update_layout(**kwargs):
            for k, v in kwargs.items():
                setattr(fig.layout, k, v)

        def add_traces(traces):
            if not isinstance(traces, (list, tuple)):
                traces = [traces]
            fig.data.extend(traces)

        fig.update_layout = update_layout
        fig.add_traces = add_traces
        return fig

    px_colors = SimpleNamespace(qualitative=SimpleNamespace(Pastel=["#ccc"]))
    px_mod.colors = px_colors
    px_mod.pie = _px_pie
    px_mod.line = _px_line
    px_mod.area = _px_area
    return px_mod


def _ensure_parent_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    plotly_pkg = ModuleType("plotly")
    # Mark as a package to be safe for submodule imports
    setattr(plotly_pkg, "__path__", [])
    monkeypatch.setitem(sys.modules, "plotly", plotly_pkg)


def _install_crud_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    crud_pkg = ModuleType("crud")
    # Mark as a package to allow submodule registration
    setattr(crud_pkg, "__path__", [])
    crud_crud_mod = ModuleType("crud.crud")
    crud_timeseries_mod = ModuleType("crud.timeseries")

    def _get_portfolio_timeseries(_db, days: int):
        return []

    def _get_total_asset_value(_db):
        return 0.0

    def _get_asset_distribution_by_platform(_db):
        return []

    crud_crud_mod.get_portfolio_timeseries = _get_portfolio_timeseries
    crud_crud_mod.get_total_asset_value = _get_total_asset_value
    crud_crud_mod.get_asset_distribution_by_platform = (
        _get_asset_distribution_by_platform
    )
    # The components import from crud.timeseries in the app code
    crud_timeseries_mod.get_portfolio_timeseries = _get_portfolio_timeseries
    # Platform chart uses this symbol; provide a harmless default
    crud_timeseries_mod.get_portfolio_timeseries_by_platform = lambda _db, days: []
    monkeypatch.setitem(sys.modules, "crud", crud_pkg)
    monkeypatch.setitem(sys.modules, "crud.crud", crud_crud_mod)
    monkeypatch.setitem(sys.modules, "crud.timeseries", crud_timeseries_mod)


@pytest.fixture(scope="function")
def components_stubs(monkeypatch: pytest.MonkeyPatch):
    """Install shared stubs for Streamlit, Plotly Express, and crud package.

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

    Usage: spy = px_spy_factory(module, "line" | "pie" | "area")
    """

    def _spy(module, func_name: str):
        target = getattr(module.px, func_name)
        spy = Mock(wraps=target)
        monkeypatch.setattr(module.px, func_name, spy)
        return spy

    return _spy
