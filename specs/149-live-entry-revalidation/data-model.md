# Data Model: 최신 엣지 재검증과 병렬 탐색

## LiveEntryRevalidation

- `allowed`: 실제 주문 단계 진행 가능 여부
- `state`: `ENTRY_READY`, `ENTRY_BLOCKED`, `ACTIVE_LIVE_TRACK`
- `fills_count`: 전략 범위 실제 체결 수
- `historical_passed`, `forward_observations`, `forward_psr`, `forward_calmar_passed`
- `hardened_canary_passed`
- `reasons`: 차단 사유 목록

## ParallelChallenger

- `candidate_id`: 관측 5개 단위 증거 지문
- `status`: no-live `EXECUTION_READY` 또는 완료
- `source_refs`: 수익 증거, paper forward, 공개 자료, 레짐, 비용, released-work
- `safety_boundary`: 주문·자본·live 변경 금지

## State Transitions

- 단 1 + 체결 0 + 최신 자격 PASS -> 주문 전 기존 게이트 진행
- 단 1 + 체결 0 + 최신 자격 FAIL -> 주문 차단, 단 0 자동 강등
- 체결 존재 -> 기존 라이브 손실·정합성 게이트 유지
- forward 미달 -> 관찰 패킷 유지 + 독립 challenger 발행
