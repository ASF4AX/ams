import streamlit as st
import pandas as pd

# 로컬 모듈 임포트
from utils.db import get_db_session
from crud.crud import get_all_transactions, get_transactions_by_type

# 페이지 확장 설정
st.set_page_config(layout="wide")

st.header("거래 내역")

# 데이터베이스 세션 획득
db = get_db_session()

try:
    # 데이터베이스에서 거래 내역 가져오기
    transactions = get_all_transactions(db)

    # 거래 내역을 데이터프레임으로 변환
    transaction_data = []
    for tx in transactions:
        asset = tx.asset
        transaction_data.append(
            {
                "날짜": tx.transaction_date.strftime("%Y-%m-%d %H:%M"),
                "자산": asset.name,
                "종류": tx.transaction_type,
                "수량": tx.quantity,
                "가격": tx.price,
                "금액": tx.amount,
                "메모": tx.memo if tx.memo else "",
            }
        )

    df_transactions = pd.DataFrame(transaction_data)

    # --- 거래 내역 UI ---
    if df_transactions.empty:
        st.info("거래 내역이 없습니다.")
    else:
        # 사용자 인터페이스 (필터링 예시 - 종류)
        tx_types = ["전체"]
        if not df_transactions.empty:
            tx_types.extend(df_transactions["종류"].unique().tolist())
        selected_type = st.selectbox("거래 종류 필터", tx_types)

        # 필터링 적용
        if selected_type == "전체":
            filtered_df = df_transactions
        else:
            # 데이터베이스에서 필터링된 데이터 가져오기
            filtered_transactions = get_transactions_by_type(db, selected_type)

            filtered_data = []
            for tx in filtered_transactions:
                asset = tx.asset
                filtered_data.append(
                    {
                        "날짜": tx.transaction_date.strftime("%Y-%m-%d %H:%M"),
                        "자산": asset.name,
                        "종류": tx.transaction_type,
                        "수량": tx.quantity,
                        "가격": tx.price,
                        "금액": tx.amount,
                        "메모": tx.memo if tx.memo else "",
                    }
                )

            filtered_df = pd.DataFrame(filtered_data)

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={  # 컬럼별 상세 설정
                "날짜": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
                "수량": st.column_config.NumberColumn(format="%d"),  # 정수
                "가격": st.column_config.NumberColumn(format="₩ %d"),  # 원화
                "금액": st.column_config.NumberColumn(format="₩ %d"),  # 원화
                "메모": st.column_config.TextColumn(width="large"),
            },
        )

finally:
    # 데이터베이스 세션 종료
    db.close()
