# Implementation Plan: Live Money Route Priority

## Summary

기존 money-path의 micro 전용 최상위 평가를 표준 자본 사다리와 micro 경로의 공통 평가·선택으로
바꾼다. 표준 경로는 저장소 센티넬과 최신 sidecar를 교차 확인하고, 실제 주문 가능한 경로를
최상위에 표시한다.

## Constitution Check

- 읽기 전용 상태 집계이며 주문·자본·실거래 전환을 하지 않는다.
- 불완전하거나 모순된 증거는 `BLOCKED`/`UNKNOWN`으로 실패 폐쇄한다.
- K1/K2, 손실 한도, production 승인, 정규장, 비밀값, 감사 로그를 유지한다.

## Implementation

1. 표준 live 센티넬 파서를 프로브에 추가한다.
2. 표준 자본 사다리 상태 평가기를 추가한다.
3. 표준·micro 경로를 공통 순위로 선택한다.
4. 단위·프로브 회귀와 현재 sidecar 재생을 추가한다.
5. 전체 검증, PR, 머지, 배포 뒤 money-path와 capital readiness를 재발행한다.

## Rollback

기능 커밋을 revert한다. 이 기능이 만든 sidecar는 읽기 전용 보고서이므로 계좌·주문·감사 장부
되돌림은 필요 없다.
