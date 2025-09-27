# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

테스트 커버리지 구축 및 자동화(핵심 로직/데이터 파이프라인 우선, 상세 결과는 -vv로 노출).

## Task List

- [x] Document manual asset registration for asset overview page
- [x] Write and publish project README
- [x] Add environment samples (`.env.sample`, `.env.sample.test`)
- [x] Implement core Streamlit pages (dashboard, assets, rates, transactions)

- [x] 테스트 환경 준비 (pytest -vv 구성, SQLAlchemy 픽스처, 샘플 데이터 팩토리, 외부 의존성 mock)
- [x] 유닛 테스트: utils (통화/손익/색상 포맷터, DB 초기화·연결, seed 데이터 작성)
- [x] DB 유틸(app/utils/db.py) (테이블 멱등 생성 및 연결 확인 경로 검증)
- [x] CRUD 테스트(app/crud/crud.py) (플랫폼/자산 리비전, 거래 흐름, 요약 지표, 스테이블·현금 자산)
- [x] DAG 유틸(dags/utils/db.py) (자산 삽입, 리비전 조회, 환율 업서트, 스테이블코인 조회)
- [x] 거래소/동기화 태스크 (Binance/Bitget/Bithumb 처리 로직과 DB 삽입 검증)
- [x] KIS 처리 (국내·해외 자산/현금 파싱 및 환율 추출)
- [x] 데일리 메트릭(dags/tasks/daily_asset_metrics.py) (이전값 조회와 변화량 계산)
- [x] DAG 스모크 테스트 (DAG 임포트 및 태스크/스케줄 검증)

- [x] SQLAlchemy SAWarning 정리: IN 절 우변을 Subquery에서 Select로 명시화하여 경고 제거 (`app/crud/crud.py`)
- [x] 보유 자산 현황 상단에 자산별 보유 비율 원형차트 추가 (`app/pages/1_자산현황.py`)
- [x] 자산별 원형차트 라벨/집계 기준을 심볼→이름으로 변경 (`app/pages/1_자산현황.py`)
- [x] 자산별 원형차트 위치를 "총 평가금액" 바로 아래로 이동, 소제목 제거 (`app/pages/1_자산현황.py`)
- [x] 자산 분포 원형차트 컴포넌트화 (`app/components/asset_pie.py`) 및 페이지 적용
- [x] 컴포넌트 유닛 테스트: 자산 분포 원형차트 (`tests/app/components/test_asset_pie.py`)
- [x] 대시보드 자산 추이 시계열 집계 추가 (`app/crud/crud.py`)
- [x] 자산 추이 차트/기간 선택 UI 구현 (`app/app.py`)
- [x] 포트폴리오 시계열 테스트 및 문서 업데이트 (`tests/app/crud/test_crud.py`, `README.md`)
