# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

대시보드 안정화 및 스테이징 정리(플랫폼별 area+총계 차트 확정, 불필요 코드 제거·기본값 일원화).

## Task List

- [x] 초기 세팅 완료: README, 환경 샘플, 핵심 페이지, 수동 등록 문서
- [x] 테스트 인프라/커버리지 구축(종합) 및 DAG 스모크 테스트
- [x] 대시보드/컴포넌트 정비: 자산 추이 컴포넌트 분리·적용, 자산 분포 파이 컴포넌트화(유닛 테스트 포함), 자산 현황 2열 배치, 대시보드 구성/조회기간 조정 (`app/app.py`)
- [x] 품질·모듈화: SQLAlchemy SAWarning 정리(IN Subquery→Select), 기간 수익률 CRUD 분리 및 테스트 추가 (`app/crud/*`, `tests/app/crud/test_metrics.py`)
- [x] 플랫폼별 자산 추이 그래프 추가: CRUD 집계 및 컴포넌트/탭 연동, 기본 유닛 테스트 (`app/crud/crud.py`, `app/components/asset_trend_by_platform.py`, `app/app.py`, `tests/app/components/test_asset_trend_by_platform.py`)
- [x] 입출금 반영 수익률(간단 버전): 기간 내 순입출금 합계를 현재값에서 제외하여 수익률 계산, 토글 연동 (`app/crud/metrics.py`, `app/app.py`)
- [x] 메인 조회 기간 옵션 조정: `30/90/180` → `90/180/360`으로 변경 (`app/app.py`)
