# Implementation Plan: 첫 체결 전 자본 정합

**Branch**: `codex/180-prefill-capital-parity` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

## Summary

기존 ladder 결정에서 현재 NAV의 10%로 검증한 예산과 sentinel의 과거 예산이 다른 문제를 보정한다.
새 자본 공식이나 주문 경로를 만들지 않는다. 첫 체결 전 운영1단의 엄격한 증거가 있을 때만
10% drift 대기 대신 기존 RESIZE·sentinel PR 경로를 사용한다.

## Technical Context

- Python3.12, Decimal, pytest/ruff/uv; 새 의존성 없음.
- 순수 portfolio/capital_ladder.py 결정, cli.py:ladder-decide가 검증된 증거를 구성한다.
- 저장소 sentinel·Git PR가 승인 이력. DB 변경·새 외부API 없음.
- 고정 입력의 결정론적 O(1) 추가 검사. 기존 Linux 생산 경로 재사용.

## Constitution Check

- I/II: per-trade50%, symbol60%, global100%, 지정가·기존 허용 종목 변경 없음.
- III/VII: LLM·외부 비용·네트워크 호출·속도 제한 변경 없음.
- IV/V: 감사·체결·선점 삭제 없음. 비밀값 노출 없음.
- VI/X: 운영1단, floor(NAV×0.1), alpha_confirmed=false. 시간분리·비용·정확 지문·전체 진입 검증 필요. 상위 단계 및 20% 초과 EDGE_CONFIRMED 경계 유지.
- VIII/IX: 장외 배포·하드닝·건강·되돌림·PR 관문 유지.
- X.4의 현재 NAV10% 검증을 실행값에 맞추는 보정이다. 비율·오차·진입 조건 변경 없이 위험4 검증과 안전경계 자체검토를 기록한다. 헌법 개정 불필요.
- 설계 후 재검토: 통과. 첫 체결 전 작은 변동 대기만 제거하며 체결 후 규칙은 유지.

## Project Structure

- src/auto_invest/portfolio/capital_ladder.py: 엄격한 첫 체결 전 증거 및 RESIZE 조건.
- tests/unit/test_capital_ladder.py: 정상·반례·손실 우선순위.
- tests/unit/test_fundability.py: 생산142/143 및 불가능한 가격 구간 재현.
- cli.py 및 .github/workflows/forward-edge-autoarm.yml: 기존 검증·PR·배포 경로 확인.

## Phases

1. 실패하는 재현 시험부터 작성한다.
2. 순수 ladder의 RESIZE 조건만 확장하고 비유한 NAV는 BLOCKED로 반환한다.
3. 관련·전체 pytest, ruff, strict harness, HANDOFF 사실 검사 및 PR 관문.
4. merge·배포 뒤 기존 autoarm이 새 예산을 검증하고 sentinel PR로 승인하게 한다.
5. 새 main 배포·KIS smoke·no-order preflight 확인. 실제 자동체결은 별도 관찰.

## Rollback

코드 되돌림 PR로 특별 갱신만 제거한다. 승인 sentinel은 손으로 고치지 않고 기존 ladder의
최신 증거로 판정한다. 감사·선점·체결 삭제 금지.
