# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

운영 자산 동기화와 포트폴리오 스냅샷 전달 흐름의 안정성을 높이고, 종목별 손익 정보를 함께 전달한다.

## Task List

- [x] 초기 세팅 완료: README, 환경 샘플, 핵심 페이지, 수동 등록 문서
- [x] 테스트 인프라/커버리지 구축(종합) 및 DAG 스모크 테스트
- [x] 대시보드/컴포넌트 정비: 자산 추이 컴포넌트 분리·적용, 자산 분포 파이 컴포넌트화(유닛 테스트 포함), 자산 현황 2열 배치, 대시보드 구성/조회기간 조정 (`app/app.py`)
- [x] 품질·모듈화: SQLAlchemy SAWarning 정리(IN Subquery→Select), 기간 수익률 CRUD 분리 및 테스트 추가 (`app/crud/*`, `tests/app/crud/test_metrics.py`)
- [x] 플랫폼별 자산 추이 그래프 추가: CRUD 집계 및 컴포넌트/탭 연동, 기본 유닛 테스트 (`app/crud/crud.py`, `app/components/asset_trend_by_platform.py`, `app/app.py`, `tests/app/components/test_asset_trend_by_platform.py`)
- [x] 입출금 반영 수익률(간단 버전): 기간 내 순입출금 합계를 현재값에서 제외하여 수익률 계산, 토글 연동 (`app/crud/metrics.py`, `app/app.py`)
- [x] 메인 조회 기간 옵션 조정: `30/90/180` → `90/180/360`으로 변경 (`app/app.py`)
- [x] 한국투자증권 국내 예수금 기준 조정: 체결기준 합산용 현금을 `D+2(prvs_rcdl_excc_amt)`만 사용하도록 변경 (`dags/tasks/kis.py`, `tests/dags/tasks/test_kis.py`)
- [x] 한국투자증권 해외 주식 수량 기준 확정: 체결기준 수량 `ccld_qty_smtl1`만 사용하도록 정리 (`dags/tasks/kis.py`, `tests/dags/tasks/test_kis.py`)
- [x] 한국투자증권 해외 예수금 기준 확정: 외화 예수금을 `frcr_sll_amt_smtl - frcr_buy_amt_smtl + frcr_dncl_amt_2` 계산식으로 적용하고 비교용 로그 제거 (`dags/tasks/kis.py`, `tests/dags/tasks/test_kis.py`)
- [x] 테스트용 Airflow 기동 안정화: `docker-compose.test.yml`에서 런타임 `apache-airflow-providers-postgres` 설치 제거(버전 충돌 방지)
- [x] Airflow DAG DB 연결 고정: `conn_id=ams`를 `AIRFLOW_CONN_AMS` 환경변수로 테스트 스택에 주입
- [x] Airflow DAG Postgres 드라이버 보강: `dags/requirements-dags.txt`에 `psycopg2-binary` 추가
- [x] 예상 금리 현황 중복 표기 수정: `get_latest_cash_equivalent_annual_interest_info` 조인 키에 `exchange`를 포함해 동일 심볼 Spot/Futures 곱집합 중복 제거 및 회귀 테스트 추가 (`app/crud/crud.py`, `tests/app/crud/test_crud.py`)
- [x] FastAPI 읽기 전용 API 추가: 총 자산/현재 자산/기간 수익률/시계열/일일 메트릭/거래내역/MDD 엔드포인트와 기본 테스트 작성 (`api/*`, `tests/api/test_main.py`)
- [x] 운영 Compose에 API 서비스 추가: 동일 Docker 이미지 기반으로 Streamlit/API를 별도 서비스로 실행 (`Dockerfile`, `docker-compose.yml`)
- [x] 운영 Compose 헬스체크 추가: Streamlit/API 컨테이너 HTTP healthcheck 구성 (`Dockerfile`, `docker-compose.yml`)
- [x] API 테스트 안정화 검토: override 정리 범위 축소, lifespan async 테스트 전환, UTC 기준 날짜 계산, 누락 commit 보강 (`tests/api/test_main.py`)
- [x] 에이전트 workbench 가이드 추가: `.agent-workbench/` 용도, target config 예시, API smoke check helper 작성
- [x] API 테스트 후속 검증: lifespan 스키마 초기화 미수행 검증 보강 및 기간 수익률/시계열 commit 존재 확인 (`tests/api/test_main.py`)
- [x] 포트폴리오 현황 업데이트: 2026-06-01 기준 운영 API 자산/수익률/MDD 수집 및 JOB-008 응답 기록, API helper compact 출력 보강 (`.agent-workbench/queries/api_smoke_check.py`)
- [x] MDD 결측 구간 백필/정리: 운영 read-only DB 기준 KIS 부분 실패 원인 확정, 문제 3일 metrics 삭제 후 API MDD 정상화(-14.23%) 확인 (`.agent-bridge/JOB-009_MDD_결측구간_백필방안_검토.md`, `.agent-workbench/queries/mdd_missing_db_analysis.py`)
- [x] KIS API 지수 백오프 재시도 적용: 국내/해외 잔고 fetch의 5xx/연결/타임아웃 오류 재시도 및 회귀 테스트 추가 (`dags/tasks/kis.py`, `tests/dags/tasks/test_kis.py`)
- [x] 자산 현황 최신 조회: 2026-06-03 기준 운영 API 자산/수익률/MDD 수집 및 TSK-019 업데이트 (`work/tasks/TSK-019_포트폴리오점검및MDD모니터링.md`)
- [x] 포트폴리오 캐시 JSON 생성 자동화: 운영 API 스냅샷을 외부 `.agent-bridge/portfolio_cache.json`으로 덮어쓰는 helper와 변환 테스트 추가 (`app/utils/portfolio_cache.py`, `.agent-workbench/queries/refresh_portfolio_cache.py`, `tests/app/utils/test_portfolio_cache.py`)
- [x] 포트폴리오 캐시 손익 확장: 종목별 원가·평가손익·수익률 및 summary 손익 집계를 캐시에 포함하도록 변환 규칙과 테스트 갱신 (`app/utils/portfolio_cache.py`, `tests/app/utils/test_portfolio_cache.py`)
- [x] AgentHub 포트폴리오 캐시 스크립트 추가: AMS 읽기 API를 조회해 최신 MDD 스키마를 포함한 캐시를 Windmill 실행 결과로 제공
- [x] AMS 라이브 조회 사용 가이드 문서화: 최신값·정적 캐시의 사용 구분과 공개 정보 경계를 기록 (`docs/agenthub_ams_portfolio_mcp.md`)
