# Implementation Plan: 공식 거시 발표일 가격 진단

**Branch**: `codex/203-macro-release-price` | **Date**: 2026-10-02  
**Spec**: [spec.md](spec.md) | **Risk**: 등급 2, 연구 명령과 에이전트 활성 포인터

## Summary

고정 공개 달력 JSON·연준 날짜 텍스트·기존 5분봉 CSV를 저장소 밖에서 읽는다.
정확한 지문 검사 뒤 발표 가족/시각/날짜/미국 증시 세션을 교차 확인한다.
개발 기간만 5분봉 가격 참조쌍을 계산해 비용 전후 결과·제외 이유를
새 파일에 출력한다. 브로커 인증·주문·자본·현재 전략은 읽거나 바꾸지 않는다.

## Technical Context

- Python 3.11+, 표준 라이브러리와 기존 `exchange_calendars`.
- 입력: `20261002-macro-calendar`의 네 원본과 189의 연구용 5분봉 파일/목록.
- 출력: 저장소 밖 JSON, 기존 출력 덮어쓰기 금지, 원본·계약·출력 SHA-256.
- 테스트: 원본 변조, 달력 상태값 오분류, 비공식 날짜, 휴장·일광절약시간,
  누락·거래량0·전일 봉·개발 기간 외 가격 수익 미개봉 반례.
- 전체 회귀와 린트는 Mac 부하를 줄이기 위해 원격 검사로 수행한다.

## Constitution Check

- I~VII, VIII.A, IX, X: 현재 주문·허용 종목·위험·감사·배포·비밀값 경로를
  변경하지 않는다. 주문0, 실제 자본0, 승격 불가를 입력과 출력에 고정한다.
- `Backtest -> Canary -> Full`: 이 연구는 Backtest 전의 개발 진단만 한다.
  차단/최종 성과를 보기 전에 별도 판정을 요구한다.
- 실패 시 새 연구 명령/명세 포인터만 되돌린다. 기존 기능 제거 없음.

## Phase 0 — Research

[research.md](research.md)에 공식/2차 출처, 잘못된 취소 상태,
추가 수정 날짜, 5분봉 조정 한계, 비용과 대안 결정을 기록했다.

## Phase 1 — Design

- [data-model.md](data-model.md): 행사·관측쌍·결과와 실패 상태.
- [contracts/preregistration.json](contracts/preregistration.json): 원본 지문,
  한 후보, 시간 분할, 비용, 안전 표식을 가격 조회 전에 고정.
- [quickstart.md](quickstart.md): 읽기 전용 재생과 검증 순서.

## Phase 2 — Implementation

`scripts/macro_release_price_diagnostic.py`가 세 원본과 가격 목록을
지문 대조하고, 가격 CSV를 한 번씩 순차 읽는다. 계약의 개발 시작/끝만
관측 대상으로 선택한다. 각 입력 경로는 예상한 파일명/폴더 아래로 제한한다.
`tests/unit/test_macro_release_price_diagnostic.py`의 반례와 실제 개발 자료
저부하 재생을 거쳐, 비용 후 음수 또는 표본 부족이면 후보를 탈락시킨다.

## 적용 경로와 되돌림

`.specify/feature.json`과 `AGENTS.md`의 `SPECKIT` 포인터가 이 계획을
가리키도록 한다. 연구 명령은 기존 라이브 진입점에 연결하지 않는다.
문제 발생 시 이 포인터 및 새 연구 파일만 되돌리며 원본 자료와 기존
운영 장부는 보존한다.
