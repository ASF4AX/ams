# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

테스트 커버리지 구축 및 자동화(핵심 로직/데이터 파이프라인 우선, 상세 결과는 -vv로 노출).

## Task List

- [x] Document manual asset registration for asset overview page
- [x] Write and publish project README
- [x] Add environment samples (`.env.sample`, `.env.sample.test`)
- [x] Implement core Streamlit pages (dashboard, assets, rates, transactions)

- [x] 테스트 인프라 및 커버리지 구축(종합)
  - pytest -vv 구성, SQLAlchemy 픽스처, 데이터 팩토리, 외부 의존성 mock
  - utils/DB 유틸/CRUD/DAG 유틸 테스트, 거래소·KIS 처리 로직 검증, 데일리 메트릭
  - DAG 스모크 테스트(임포트/태스크/스케줄)

- [x] SQLAlchemy SAWarning 정리: IN 절 Subquery→Select 명시화 (`app/crud/crud.py`)
- [x] 자산 분포 원형차트 개선 및 적용
  - 상단 배치, 라벨/집계 기준(심볼→이름) 변경, 소제목 제거
  - 컴포넌트화(`app/components/asset_pie.py`) 및 유닛 테스트(`tests/app/components/test_asset_pie.py`)

- [x] pandas Styler.applymap→map 마이그레이션 (`app/pages/1_자산현황.py`)
- [x] Streamlit `use_container_width` 폐지 대응: `width='stretch'`로 교체(데이터프레임/차트/에디터 전역)
