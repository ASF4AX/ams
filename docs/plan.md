# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

테스트 커버리지 구축 및 자동화(핵심 로직/데이터 파이프라인 우선, 상세 결과는 -vv로 노출).

## Task List

- [x] Document manual asset registration for asset overview page
- [x] Write and publish project README
- [x] Add environment samples (`.env.sample`, `.env.sample.test`)
- [x] Implement core Streamlit pages (dashboard, assets, rates, transactions)

- [ ] 테스트 환경 준비

  - [ ] pytest 기본 설정 및 실행 옵션 구성(`pytest -vv`)
  - [ ] SQLAlchemy 테스트 픽스처(엔진/세션, PostgreSQL 연결)
  - [ ] 샘플 데이터 팩토리 작성(경량 팩토리 우선); `app/utils/seed_data.py`는 현 구조와 합치성 검토 후 필요 시 수정 또는 미사용
  - [ ] 외부 의존성 mock 픽스처(ccxt, requests, Airflow BaseHook/Variable)

- [ ] 유닛 테스트: utils

  - [x] `format_currency` KRW/USD/BTC/None/미지정 통화 포맷
  - [x] `format_profit_loss`, `format_profit_loss_rate` 포맷
  - [x] `color_negative_red` 음수/양수/0/비수치 처리

- [x] DB 유틸(app/utils/db.py)

  - [x] `initialize_db(drop_all=False)` 테이블 생성/멱등성
  - [x] `test_connection()` 성공/실패(mock 실패 시나리오)

- [x] CRUD 테스트(app/crud/crud.py)

  - [x] Platform: `create_platform`, `get_platform_by_name`
  - [x] Asset: `create_asset` 평가금액/리비전, 최신 리비전 서브쿼리 동작
  - [x] Asset: `get_all_assets`가 플랫폼별 최신 리비전만 반환
  - [x] Asset: `update_asset` 시 `evaluation_amount` 재계산
  - [x] Transaction: `create_transaction` 매수/매도 후 수량 반영
  - [x] Transaction: `get_all_transactions` 정렬/limit/offset
  - [x] Transaction: `get_recent_transactions(days)` 필터링
  - [x] Summary: `get_total_asset_value` 최신 `eval_amount_krw` 합산
  - [x] Summary: `get_daily_change_percentage`(플랫폼별 2개 리비전)
  - [x] Summary: `get_asset_distribution_by_category` 합산/0 제외
  - [x] Summary: `get_asset_distribution_by_platform` 합산
  - [x] StableCoin: 생성/조회/활성화 업데이트/삭제/활성 목록
  - [x] CashRates: `get_latest_cash_equivalent_annual_interest_info` 365배 계산

- [x] DAG 유틸(dags/utils/db.py)

  - [x] `insert_asset` 필수필드 검증/플랫폼 자동 생성/삽입
  - [x] `get_latest_revision`/`get_latest_asset_revision_by_platform_id`
  - [x] `upsert_exchange_rate` 및 `get_exchange_rates` 딕셔너리 출력
  - [x] `get_active_stable_coins` 세트 반환

- [ ] 거래소/동기화 태스크

  - [x] Binance: `process_binance_balances` 스팟/선물, 평가금액 KRW, 스테이블 분류(mock 환율)
  - [x] Binance: `update_assets_in_db`가 `insert_asset` 호출(mock DB 세션)
  - [x] Bitget: `process_bitget_balances` 가격/필터링/평가금액 KRW
  - [x] Bithumb: `process_bithumb_balances` KRW 가격/평가금액 매핑

- [ ] KIS 처리

  - [ ] 국내: `process_kis_assets` 수치 변환/필드 매핑
  - [ ] 해외: `process_kis_overseas_assets` 중복제거/거래소코드/숫자 파싱
  - [ ] 해외: `process_kis_overseas_cash` 0 금액 제외/최초 유효 항목 처리
  - [ ] 환율: `process_kis_exchange_rates` base→KRW 양수 환율 추출

- [ ] 데일리 메트릭(dags/tasks/daily_asset_metrics.py)

  - [ ] `_fetch_previous_metrics` 이전값 조회/신규 리비전 증가
  - [ ] `process_metrics` 스테이블/일반 after_value 계산 및 저장

- [ ] DAG 스모크 테스트
  - [ ] 각 DAG 파일 임포트 가능 여부
  - [ ] 태스크 ID 존재 확인 및 기본 스케줄 값 확인
