import streamlit as st
import pandas as pd
import plotly.express as px
from typing import Sequence, Any


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

    df = pd.DataFrame(
        [
            {
                "name": getattr(a, "name", None),
                "amount": float(getattr(a, "eval_amount_krw", 0) or 0),
            }
            for a in assets
        ]
    )

    # Keep only positive amounts
    df = df[df["amount"] > 0]
    if df.empty:
        st.info(empty_message)
        return

    df = df.groupby("name", as_index=False)["amount"].sum().sort_values(
        "amount", ascending=False
    )

    fig = px.pie(
        df,
        values="amount",
        names="name",
        title=title,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

