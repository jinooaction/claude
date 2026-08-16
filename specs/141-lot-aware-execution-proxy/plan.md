# Implementation Plan: Lot-Aware Execution Proxy

**Branch**: `Codex/141-lot-aware-execution-proxy` | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

## Summary

검증된 기준 ETF로 신호를 계산한 뒤 명시적 저가 ETF로만 체결 종목을 바꾼다. 라이브 경로는
KIS 실제 보유·현금을 필수 입력으로 사용하고, 목표 달러 오차를 줄이는 가장 가까운 정수 주를
기존 캡 안에서만 허용한다.

## Technical Context

- Python 3.12, Pydantic, Typer, SQLite, GitHub Actions, KIS 해외주식 API
- 변경 영역: 포트폴리오 설정 로더, 재조정 플래너·실행기, 라이브 워크플로, 배포 설정, 테스트
- 데이터베이스 마이그레이션 없음
- 실제 주문 종목과 수량 산정에 닿는 등급 4 변경

## Constitution Check

- 단 1 자본 293달러와 20% 상한을 유지한다.
- 25% 이상은 기존 `EDGE_CONFIRMED`와 라이브 증거를 계속 요구한다.
- 신호 전략 지문은 검증 설정과 정확히 동일하다.
- 매핑·브로커 보유·현금·시세 중 하나라도 없으면 실패 폐쇄한다.
- K1 캡, whitelist, 손실 예산, 감사 로그, 비밀값, 정규장, 지정가, production 승인을 유지한다.

## Implementation

1. 선택적 `[execution]` 매핑과 정수 주 방식을 엄격히 읽는다.
2. 재조정 실행기는 기준 신호 비중을 체결 비중으로 1:1 변환하고 실제 계좌 보유와 비교한다.
3. 플래너는 기본 floor 동작을 보존하고 이 경로에서만 nearest 정수 주를 사용한다.
4. 라이브 설정은 저가 ETF만 whitelist에 넣고 account-wide 실제 스냅샷을 필수화한다.
5. 미리보기·실주문 워크플로 모두 같은 옵션과 증거를 사용한다.
6. 회귀·전체 검증 후 PR, 머지, 배포, KIS 미리보기를 확인한다.
7. 실주문 명령 종료 코드를 정확히 전파하고, 주문 직후 제한된 체결 동기화와 사후 측정 결과를
   항상 발행되는 sidecar에 함께 남긴다.

## Project Structure

```text
src/auto_invest/cli.py
src/auto_invest/execution/rebalancer.py
src/auto_invest/strategy/rebalance.py
deploy/canary-live-portfolio.toml
.github/workflows/rebalance-live-canary.yml
tests/integration/test_spec_032_live_rebalancer.py
tests/unit/test_canary_portfolio_config.py
tests/unit/test_live_canary_workflow.py
specs/141-lot-aware-execution-proxy/
```

## Rollback

센티넬을 먼저 `armed:false`, 단 0으로 내린 뒤 기능 커밋을 되돌린다. 이미 체결된 포지션은
감사 로그를 보존하고 기존 지정가 청산·킬스위치 절차로 처리한다.
