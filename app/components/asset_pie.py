import streamlit as st
import plotly.express as px
from typing import Sequence, Any, Callable, Tuple, List


def _compute_labels_values_by(
    assets: Sequence[Any], label_getter: Callable[[Any], Any]
) -> Tuple[List[Any], List[float]]:
    """
    Aggregate positive `eval_amount_krw` by a label derived from the asset.

    Returns labels and values sorted by value (desc). Empty lists if nothing positive.
    """
    totals: dict[Any, float] = {}
    for a in assets:
        amount = float(getattr(a, "eval_amount_krw", 0) or 0)
        if amount <= 0:
            continue
        label = label_getter(a)
        totals[label] = totals.get(label, 0.0) + amount

    if not totals:
        return [], []

    keys = sorted(totals, key=totals.get, reverse=True)
    labels = list(keys)
    values = [totals[k] for k in keys]
    return labels, values


def render_asset_allocation_pie_by_name(
    assets: Sequence[Any],
    *,
    title: str = "자산별 보유 비율 (KRW 기준)",
    empty_message: str = "자산 분포 데이터가 없습니다.",
) -> None:
    """
    Render a pie chart of asset allocation aggregated by asset "name" using KRW values.

    - Aggregates eval_amount_krw by asset name
    - Filters out non-positive amounts
    - Renders a Plotly pie inside Streamlit

    Parameters
    ----------
    assets: sequence of ORM-like objects having attributes: name, eval_amount_krw
    title: chart title
    empty_message: message to show when there is no data
    """
    if not assets:
        st.info(empty_message)
        return

    labels, values = _compute_labels_values_by(assets, lambda a: getattr(a, "name", None))
    if not labels:
        st.info(empty_message)
        return

    df_like = {"name": labels, "amount": values}
    fig = px.pie(
        df_like,
        values="amount",
        names="name",
        title=title,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_asset_allocation_pie_by_category(
    assets: Sequence[Any],
    *,
    title: str = "카테고리별 자산 비율 (KRW 기준)",
    empty_message: str = "자산 분포 데이터가 없습니다.",
) -> None:
    """
    Render a pie chart of asset allocation aggregated by asset "category" using KRW values.

    - Aggregates eval_amount_krw by asset category
    - Filters out non-positive amounts and missing categories
    - Renders a Plotly pie inside Streamlit

    Parameters
    ----------
    assets: sequence of ORM-like objects having attributes: category, eval_amount_krw
    title: chart title
    empty_message: message to show when there is no data
    """
    if not assets:
        st.info(empty_message)
        return

    labels, values = _compute_labels_values_by(
        assets, lambda a: getattr(a, "category", None) or "기타"
    )
    if not labels:
        st.info(empty_message)
        return

    df_like = {"category": labels, "amount": values}
    fig = px.pie(
        df_like,
        values="amount",
        names="category",
        title=title,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)
