# Project Plan

This document tracks tasks, progress, and next steps for the project. After each modification or feature addition, update this file with the current status and any changes to the plan.

## Current Goal

테스트 커버리지 구축·자동화(-vv 상세 노출, 핵심 로직/데이터 파이프라인 우선). 다음 단계: 엣지케이스/실패 시나리오 커버리지 보강, 컴포넌트 테스트 추가, 문서 갱신.

## Task List

- [x] 초기 세팅 완료: README, 환경 샘플, 핵심 페이지, 수동 등록 문서
- [x] 테스트 인프라/커버리지 구축(종합) 및 DAG 스모크 테스트
- [x] 대시보드/컴포넌트 정비: 자산 추이 컴포넌트 분리·적용, 자산 분포 파이 컴포넌트화(유닛 테스트 포함), 자산 현황 2열 배치, 대시보드 구성/조회기간 조정 (`app/app.py`)
- [x] 품질·모듈화: SQLAlchemy SAWarning 정리(IN Subquery→Select), 기간 수익률 CRUD 분리 및 테스트 추가 (`app/crud/*`, `tests/app/crud/test_metrics.py`)
