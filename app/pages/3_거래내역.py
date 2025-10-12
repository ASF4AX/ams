import streamlit as st

from utils.db import get_db_session
from crud.crud import (
    get_all_transactions,
    get_transactions_by_type,
)
from components.cashflow_expander import render_cashflow_expander
from components.transactions_table import render_transactions_table

# 페이지 확장 설정
st.set_page_config(layout="wide")

st.header("거래 내역")

db = get_db_session()

try:
    # 입출금 등록 UI
    render_cashflow_expander(db)

    st.write("")

    transactions = get_all_transactions(db)

    if not transactions:
        st.info("거래 내역이 없습니다.")
    else:
        tx_types = ["전체"]
        tx_types.extend(sorted({t.transaction_type for t in transactions}))
        selected_type = st.selectbox("거래 종류", tx_types)

        if selected_type == "전체":
            filtered_transactions = transactions
        else:
            filtered_transactions = get_transactions_by_type(db, selected_type)
        render_transactions_table(filtered_transactions, include_memo=True)

finally:
    db.close()
