import streamlit as st
from typing import List

from crud.crud import get_all_assets, create_transaction


def _get_krw_assets_all(db):
    assets = get_all_assets(db) or []
    return [a for a in assets if getattr(a, "symbol", "") == "KRW"]


def _validate_cashflow_inputs(asset, amount: float) -> List[str]:
    errors: List[str] = []
    if not asset:
        errors.append("대상 자산을 선택하세요.")
    if amount is None or amount <= 0:
        errors.append("금액을 입력하세요.")
    return errors


def render_cashflow_expander(db) -> None:
    """입출금 등록 UI(KRW 자산만). 플랫폼 선택 없이 KRW 자산만 표출."""
    with st.expander("입출금 등록", expanded=False):
        assets = _get_krw_assets_all(db)
        if not assets:
            st.info("KRW 자산이 없습니다. 먼저 KRW 자산을 추가하세요.")
            return

        with st.form("cashflow_form", clear_on_submit=True):
            tx_type = st.selectbox("유형", ["입금", "출금"], index=0)
            amount = st.number_input("금액 (KRW)", min_value=0.0, format="%.0f")
            asset = st.selectbox(
                "대상 자산",
                options=assets,
                format_func=lambda a: f"{getattr(getattr(a,'platform',None),'name','알 수 없음')} · {getattr(a,'name','')}{' (' + getattr(a,'symbol','') + ')' if getattr(a,'symbol',None) else ''}",
            )
            memo = st.text_input("메모", placeholder="선택")
            submitted = st.form_submit_button("등록")

        if submitted:
            errors = _validate_cashflow_inputs(asset, amount)
            if errors:
                for m in errors:
                    st.error(m)
            else:
                try:
                    # KRW 전용 설계: 단가를 1원으로 고정하고 수량을 금액으로 저장합니다.
                    created = create_transaction(
                        db,
                        asset_id=asset.id,
                        transaction_type=tx_type,
                        price=1.0,
                        quantity=float(amount),
                        memo=memo or None,
                        flow_fx_to_krw=1.0,
                    )
                    if created:
                        st.success("입출금이 등록되었습니다.")
                except Exception as e:
                    st.error(f"등록 중 오류가 발생했습니다: {e}")
