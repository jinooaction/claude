# 데이터 모델: 돈 경로 게이트 정렬 루프

## GateSurface

- `key`: sidecar 식별자.
- `source_ref`: 원천 브랜치와 파일.
- `present`: 원문 존재 여부.
- `parse_status`: `ok`, `present`, `missing`, `malformed`.
- `status`: 표면별 핵심 상태.
- `timestamp_utc`: 입력 표면이 제공한 시각.
- `summary_ko`: 사람이 읽을 요약.

## GateAlignmentIssue

- `issue_id`: 결정론적 이슈 식별자.
- `severity`: `INFO`, `WAITING`, `MISALIGNED`, `BLOCKED`.
- `gate_key`: 관련 게이트.
- `expected`: 기준 또는 기대 상태.
- `observed`: 관측 상태.
- `reason_ko`: 왜 이슈인지.
- `next_action_ko`: 다음 자동 작업 또는 운영 행동.
- `source_refs`: 이슈를 만든 원천 표면 목록.

## MoneyGateAlignmentReport

- `schema_version`: 보고 스키마 버전.
- `run_id`: workflow 실행 식별자.
- `commit`: 실행 대상 커밋.
- `timestamp_utc`: 보고 생성 시각.
- `overall_status`: `ALIGNED_WAITING`, `ALIGNED_READY`, `MISALIGNED`, `BLOCKED`, `UNKNOWN`.
- `live_money_status`: `money-path` 기준 실거래 경로 상태.
- `readiness_state`: 자본 준비도 루프 상태.
- `capital_ladder_stage`: 돈 경로 기준 자본 사다리 단계.
- `blocking_gate`: 현재 차단 또는 대기 게이트.
- `selected_work_candidate`: 자동 작업 실행 루프가 고른 후보 식별자.
- `next_action_ko`: 사람이 바로 이해할 다음 행동.
- `gate_surfaces`: `GateSurface` 목록.
- `alignment_issues`: `GateAlignmentIssue` 목록.
- `safety_invariants`: 이 루프가 지키는 안전 불변조건.

## 상태 전이

- 핵심 입력 없음 또는 pipeline `CRITICAL` -> `BLOCKED`
- 구조화 증거 부족 -> `UNKNOWN`
- live status, stage, blocking gate 모순 -> `MISALIGNED`
- 관측 부족과 기존 게이트 대기가 일치 -> `ALIGNED_WAITING`
- 기존 게이트가 승격 가능 상태로 일치 -> `ALIGNED_READY`
