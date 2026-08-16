# Implementation Plan: Heldout Exploration Canary

## Summary

수익 증거 엔진이 전략군 우승자가 아니라 실제 배포할 `global-trend-fixed` 설정을 별도로 계산하고,
그 결과와 강화 캐너리 PASS를 자본 사다리의 새 20% 탐색 단에 연결한다. 25% 이상은 기존
`EDGE_CONFIRMED` 문턱을 유지한다.

## Technical Context

- Python 3.12, pytest, ruff, GitHub Actions, KIS production environment
- 변경 영역: 수익 증거, 자본 사다리, 자동 무장, 관측 SSH 경계, 라이브 캐너리 설정, 헌법
- 데이터베이스 마이그레이션 없음

## Constitution Check

- 헌법 X.4를 7.0.0으로 개정하며 안전 경계 변경을 명시한다.
- K1 캡, whitelist, 감사 로그, 비밀값, 외부 API fail-closed, 장중 배포 금지는 유지한다.
- `Backtest -> Canary -> Full`에서 새 단계는 Full이 아니라 최대 20% 탐색 Canary다.
- 정확한 배포 지문과 누락 증거 fail-closed를 자동 시험으로 고정한다.

## Implementation

1. 정확한 균등가중 앙상블의 개발·홀드아웃·forward 증거를 구조화한다.
2. 사다리에 20% 탐색 단을 넣고 25% 승격에는 원래 EDGE_CONFIRMED를 요구한다.
3. 자동 무장 워크플로가 증거 sidecar와 고정된 강화 캐너리 결과만 소비하게 한다.
4. 라이브 캐너리 설정을 검증 설정과 정확히 맞추고 SSH 허용명령을 최소 확장한다.
5. 회귀·전체 검증 뒤 PR을 머지하고 배포·sidecar를 재확인한다.

## Rollback

기능 커밋을 되돌리고 무장 센티넬을 `armed:false`, 단 0으로 되돌린다. 새 스키마는 sidecar에만
추가되며 DB 변경이 없다. 이미 체결된 포지션은 감사 기록을 보존한 채 기존 안전한 리밸런싱 또는
킬스위치 절차로 처리한다.
