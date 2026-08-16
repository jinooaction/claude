# Data Model: Autonomous Production Approval

## AutonomousApprovalDecision

| Field | Type | Constraint |
|-------|------|------------|
| event | string | `schedule` 또는 `workflow_dispatch` |
| ref | string | `refs/heads/main` |
| armed | boolean | 반드시 true |
| blocked | boolean | 반드시 false |
| capital_usd | decimal | 기존 자본 검증 스크립트 통과 |
| decision | enum | `scheduled-real-order` 또는 `manual-no-order-preflight` |

상태 전이는 `preview-valid -> machine-approved -> production-environment -> server-authorized` 순서다.
어느 단계든 실패하면 뒤 단계는 실행하지 않는다.

## ProductionEnvironmentPolicy

| Field | Required Value |
|-------|----------------|
| environment | `production` |
| required_reviewers | 빈 목록 |
| custom_branch_policies | true |
| allowed_branch | `main` 한 개 |
| signing_secret_scope | environment only |

