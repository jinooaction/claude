# Data Model: 자율 루프 품질 폐쇄

## CodexExecutionContract

- `autonomy_level`: `CODEX_AUTONOMOUS_START`, `OPERATOR_APPROVAL_REQUIRED`, `RECOVERY_REQUIRED`, `CLOSED_RELEASED`, `CLOSED_SUPPRESSED` 중 하나.
- `start_guidance_ko`: 다음 세션이 어떤 절차로 시작할지 설명한다.
- `completion_gates`: 완료 전 통과해야 하는 검증·인계 관문 목록.
- `required_inputs`: 작업 시작 전 읽어야 하는 sidecar 또는 문서 목록.
- `safety_boundary`: 보존해야 하는 안전 경계 목록.

## ObservationSnapshotSkew

- `severity`: 정보성 시점 차이로 표시한다.
- `gate_key`: `snapshot_provenance`.
- `observed`: 출처별 관측 수와 범위.
- `reason_ko`: 같은 결론 안의 정상 시점 차이인지 설명한다.
- `next_action_ko`: 다음 aligned run에서 숫자가 자연스럽게 수렴하는지 확인하라는 행동.

## PostStatusLivenessRefresh

- `trigger_source`: operator-status workflow 완료.
- `target_workflow`: pipeline-liveness workflow.
- `safety_boundary`: 읽기 전용 sidecar 수집과 자기 sidecar 발행만 허용한다.
