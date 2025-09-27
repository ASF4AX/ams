# AMS — 자산 관리 시스템 (Asset Management System)

개인 투자자를 위한 경량 자산 관리 웹앱입니다. Streamlit로 UI를 제공하고, PostgreSQL에 데이터를 저장합니다. Airflow DAGs로 거래소/증권사 동기화 및 일일 지표 수집을 자동화합니다.

## 기능과 화면

- Dashboard (`app/app.py`)

  - 요약: 총 자산, 일일 변화율, 카테고리 분포, 자산 추이(일별 시계열), 최근 거래를 한눈에 확인
  - 주요 동작: 최신 리비전 기준 합산(`get_total_asset_value`), 일일 수익률(`get_daily_change_percentage`), 선택 기간 수익률(`get_portfolio_period_return`), 일자별 포트폴리오 시계열(`get_portfolio_timeseries`)

- 자산현황 (`app/pages/1_자산현황.py`)

  - 요약: 총 평가금액과 개별 자산(이름 기준) 비율 원형차트, 플랫폼별 묶음, 소액 자산 숨기기, 손익/손익률 표시
  - 주요 동작: 최신 리비전 스냅샷, 이름 기준 집계 + KRW 환산 합산, 임계값 기반 필터

- 예상금리현황 (`app/pages/2_예상금리현황.py`)

  - 요약: 현금/스테이블코인 예상 연 금리 목록
  - 주요 동작: 일일 수익률 × 365 계산(`get_latest_cash_equivalent_annual_interest_info`)

- 거래내역 (`app/pages/3_거래내역.py`)

  - 요약: 거래 유형별 필터, 표 출력
  - 주요 동작: 정렬/검색, 유형 필터(`get_transactions_by_type`)

- 설정 (`app/pages/4_설정.py`)

  - 요약: DB 상태/초기화, 스테이블코인 관리, 환경 정보
  - 주요 동작: 연결 테스트/초기화(`initialize_db`), 스테이블코인 CRUD

- 백그라운드 자동화(Airflow, `dags/`)
  - 동기화: 거래소/증권사 자산 동기화 DAGs(`sync_*.py`)
  - 일일 지표: 플랫폼별 일일 메트릭 집계(`*_daily_metrics.py`)
  - 유틸: DB/환율/리비전 유틸(`dags/utils/db.py`)

## 빠른 시작 (로컬 개발)

사전 준비

- Python 3.11
- 로컬 PostgreSQL 또는 `docker-compose.test.yml`로 띄운 테스트 DB (권장)

1. 의존성 설치

- 가상환경을 권장합니다.

```
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경 변수 설정

- 프로덕션 예시: `.env.sample`
- 로컬 테스트 스택 예시: `.env.sample.test`

```
cp .env.sample.test .env
# 필요 시 포트/계정 등 수정
```

주요 변수

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `APP_ENV`, `LOG_LEVEL`
- `STREAMLIT_BASE_URL_PATH` (리버스 프록시 사용 시 베이스 경로)

3. 테스트 DB + Airflow 올리기 (선택)

아래 명령으로 PostgreSQL(포트 5433)과 Airflow(포트 8080)를 함께 띄웁니다.

```
docker compose -f docker-compose.test.yml up -d
```

- Airflow UI: http://localhost:8080 (계정은 `.env.sample.test` 참조)

4. 앱 실행 (Streamlit)

- DB를 직접 운영 중이거나 위 테스트 스택(DB: `localhost:5433`)에 연결해 실행합니다.

```
streamlit run app/app.py
```

- 기본 포트: 8501 → http://localhost:8501
- 최초 실행 시 테이블이 자동 생성됩니다. (`initialize_db(drop_all=False)`)

5. 샘플 데이터 (옵션)

초기 화면 구성을 위해 더미 데이터를 주입할 수 있습니다. (현재 DB 스키마를 모두 재생성하므로 주의)

```
python app/utils/seed_data.py
```

## 테스트

의존성 설치 후 아래 명령으로 테스트를 실행합니다. `pytest.ini`에 `-vv`가 설정되어 있어 실행된 테스트 이름이 모두 출력됩니다.

```
pytest            # 전체 테스트 실행 (verbose)
```


## Docker로 스트림릿만 실행 (고급)

`docker-compose.yml`은 외부 네트워크(`postgres-network`, `caddy_net`)와 외부 DB를 전제로 합니다. 사내/개인 인프라에서 역프록시 및 DB가 이미 구성된 환경에 적합합니다.

전제

- 사전에 동일 이름의 도커 네트워크가 존재해야 합니다.
- DB 접속 정보는 `.env`로 주입합니다.

실행

```
docker compose up -d
```

환경 변수 `STREAMLIT_BASE_URL_PATH`를 통해 베이스 경로를 지정할 수 있습니다.

## 디렉터리 구조

- `app/` — Streamlit 앱 소스
  - `app/app.py` — 메인 대시보드
  - `app/pages/1_자산현황.py` — 보유 자산 현황
  - `app/pages/2_예상금리현황.py` — 현금성/스테이블코인 예상 연 금리
  - `app/pages/3_거래내역.py` — 거래 내역
  - `app/pages/4_설정.py` — 설정 및 환경 정보
  - `app/crud/` — DB CRUD 및 통계/집계 함수
  - `app/utils/` — DB 연결/초기화, 포매터, 샘플 데이터 시드
- `models/` — SQLAlchemy 모델 정의
- `dags/` — Airflow DAGs 및 태스크 유틸
- `docs/` — 설계 문서와 진행 계획
- `tests/` — 테스트 스위트 (유닛/컴포넌트/DAG 스모크)
- `requirements.txt` — 앱 의존성
- `docker-compose.test.yml` — 로컬 테스트용 DB+Airflow 스택
- `docker-compose.yml` — 스트림릿 컨테이너 (외부 네트워크 전제)

## Airflow DAGs

- 거래소 동기화: `dags/sync_*.py` (Binance, Bitget, Bithumb, KIS 등)
- 일일 메트릭: `dags/*_daily_metrics.py`
- 추가 의존성: `dags/requirements-dags.txt`

테스트 스택에서 Airflow는 `.env.sample.test`의 관리자 계정으로 초기화됩니다. DAGs는 `/opt/airflow/dags`로 마운트되어 자동 로드됩니다.

## 데이터 모델 요약

- `Platform` — 거래 플랫폼 (거래소/증권사)
- `Asset` — 보유 자산 스냅샷 (리비전 필드로 버전 구분, 원화 환산액 포함)
- `Transaction` — 거래 내역 (매수/매도/입출금)
- `DailyAssetMetrics` — 플랫폼/심볼별 일일 전후 가치와 수익률(원화/원화 외)
- `StableCoin` — 관리용 스테이블코인 목록

주요 조회 로직은 `app/crud/crud.py`에 정의되어 있으며, 최신 리비전 기준 합산/분포 계산을 제공합니다.

## 기술 스택

- Python 3.11, Streamlit
- PostgreSQL + SQLAlchemy
- Airflow 2.10 (웹서버/스케줄러, DAGs)
- Plotly, Pandas, python-dotenv
- Docker, Docker Compose
