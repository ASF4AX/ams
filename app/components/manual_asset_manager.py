import streamlit as st
import pandas as pd

from sqlalchemy.orm import Session
from models.models import AssetCategory
from crud.manual_assets import (
    apply_manual_assets_state,
    get_manual_assets,
    Col,
)

COLUMN_ORDER = [
    Col.EXCHANGE.value,
    Col.CATEGORY.value,
    Col.NAME.value,
    Col.SYMBOL.value,
    Col.PRICE.value,
    Col.QTY.value,
    Col.CURRENCY.value,
    Col.EVAL_KRW.value,
    Col.UPDATED_AT.value,
]


def _assets_to_editor_dataframe(assets) -> pd.DataFrame:
    """Build DataFrame using the component's canonical column order."""
    cols = [Col.ID.value] + COLUMN_ORDER

    if not assets:
        return pd.DataFrame(columns=cols)

    rows = [
        [
            a.id,
            a.exchange or "",
            a.category,
            a.name,
            a.symbol,
            a.current_price,
            a.quantity,
            a.currency or "",
            a.eval_amount_krw,
            a.updated_at,
        ]
        for a in assets
    ]
    return pd.DataFrame(rows, columns=cols)


def _build_state_from_editor(df: pd.DataFrame, raw_state: dict) -> dict:
    """Translate editor's index-based state into ID-based state for CRUD.

    - deleted_rows -> deleted_ids (by mapping row index to Col.ID)
    - edited_rows  -> edited_by_id with keys as string IDs
    - added_rows   -> pass-through
    """
    deleted_rows = raw_state.get("deleted_rows", [])
    deleted_ids = [int(df.iloc[int(pos)][Col.ID.value]) for pos in deleted_rows]

    edited_rows = raw_state.get("edited_rows", {}) or {}
    edited_by_id = {
        str(int(df.iloc[int(idx)][Col.ID.value])): change
        for idx, change in edited_rows.items()
    }

    return {
        "added_rows": raw_state.get("added_rows", []),
        "deleted_ids": deleted_ids,
        "edited_by_id": edited_by_id,
    }


def render_manual_asset_manager(db: Session) -> None:
    """
    Render manual asset add/delete UI under Settings page.
    - Adds assets into MANUAL_PLATFORM_NAME with MANUAL_REVISION.
    - Computes eval_amount_krw using ExchangeRate when possible.
    """
    st.subheader("수동 자산 관리")

    # Display + inline edit (single path)
    # Fetch latest assets for the manual platform
    latest_assets = get_manual_assets(db)
    df = _assets_to_editor_dataframe(latest_assets)
    if df.empty:
        st.info("수동등록 자산이 없습니다. 아래 표에 행을 추가해 저장하세요.")
    else:
        st.caption("현재 수동등록 자산 목록 (행 추가/수정/삭제 후 저장)")

    # Versioned key to avoid reusing cached widget state across reruns
    ver = st.session_state.get("manual_assets_table_ver", 0)
    table_key = f"manual_assets_table_{ver}"

    st.data_editor(
        df,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=table_key,
        column_order=COLUMN_ORDER,
        column_config={
            Col.ID.value: st.column_config.TextColumn(Col.ID.value, disabled=True),
            Col.CATEGORY.value: st.column_config.SelectboxColumn(
                Col.CATEGORY.value, options=[c.value for c in AssetCategory]
            ),
            Col.EXCHANGE.value: st.column_config.TextColumn(Col.EXCHANGE.value),
            Col.EVAL_KRW.value: st.column_config.NumberColumn(
                Col.EVAL_KRW.value, disabled=True, format="₩ %d"
            ),
            Col.UPDATED_AT.value: st.column_config.DatetimeColumn(
                Col.UPDATED_AT.value, disabled=True
            ),
        },
    )

    # Save button: apply editor changes
    if st.button("변경사항 저장", key="manual_assets_save"):
        try:
            raw_state = st.session_state.get(table_key, {}) or {}
            enriched_state = _build_state_from_editor(df, raw_state)

            apply_manual_assets_state(db, state=enriched_state)

            st.session_state["manual_assets_flash_type"] = "success"
            st.session_state["manual_assets_flash"] = "저장 완료"
        except Exception as e:
            st.session_state["manual_assets_flash_type"] = "error"
            st.session_state["manual_assets_flash"] = f"저장 실패: {e}"
        finally:
            # Force refresh to show flash and discard editor cache
            st.session_state["manual_assets_table_ver"] = ver + 1
            st.rerun()

    # Flash message shown just below the button (after reruns)
    _flash_msg = st.session_state.pop("manual_assets_flash", None)
    _flash_type = st.session_state.pop("manual_assets_flash_type", None)
    if _flash_msg:
        if _flash_type == "error":
            st.error(_flash_msg)
        else:
            st.success(_flash_msg)
