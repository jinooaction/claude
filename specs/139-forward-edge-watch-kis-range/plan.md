# Implementation Plan: Forward Edge Watch and KIS Range Query

## Summary

기존 주문내역 함수에 종료일을 선택적으로 추가해 live smoke 호출 수만 줄이고, 실제 fill sync의 단일일 기본 동작과 거래소별 fail-closed를 보존한다. profit-evidence JSON은 autonomous-work의 새 읽기 전용 입력으로 추가한다.

## Technical Context

- Python 3.12, pytest, respx, GitHub Actions
- 변경 영역: broker read API, live smoke, autonomous analytics/probe/workflow
- 위험 등급 3, 새 주문·자본·비밀값·kernel 변경 없음

## Constitution Check

- K1 포지션 한도와 K2 허용 종목: 변경 없음.
- K4 감사 로그와 K5 비밀값: 변경 없음.
- 외부 API 오류: 한 거래소 실패도 계속 전파한다.
- `Backtest -> Canary -> Full`: forward 통과 뒤에도 승격 재검토만 허용한다.

## Implementation

1. 범위 날짜 파라미터와 역전 검증을 브로커 읽기 함수에 추가한다.
2. live smoke를 최근 7일 범위 한 번으로 변경한다.
3. profit-evidence sidecar를 autonomous manifest에 연결한다.
4. 현재 미달과 미래 통과를 각각 observation/promotion-recheck 패킷으로 변환한다.
5. fixture, 실제 sidecar replay, 전체 회귀, live smoke로 검증한다.

## Rollback

문제 발생 시 스펙 139 커밋을 되돌리면 기존 단일일 API와 일반 `wait-for-fresh-evidence` 동작으로 복구된다. 데이터베이스 마이그레이션이나 자본 상태 변경은 없다.
