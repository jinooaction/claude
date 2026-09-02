# Data Model: 오너 단회 장중 긴급 배포

## EmergencyDeployRequest

루트 helper가 신뢰된 GitHub 승인에서 만든 단회 요청이다.

| 필드 | 형식 | 검증 |
|---|---|---|
| `schema_version` | 문자열 | 정확히 `1.0` |
| `request_id` | 문자열 | `github-run-<workflow_run_id>`; 감사 장부에서 유일 |
| `target_sha` | 문자열 | 40자리 소문자 Git SHA, 현재 `origin/main`과 정확히 같음 |
| `actor` | 문자열 | 워크플로가 namespace 소유자 또는 헌법에 고정 등록된 시스템 오너로 확인한 actor |
| `workflow_run_id` | 문자열 | 양의 십진 정수 |
| `source` | 문자열 | 정확히 `github-actions-workflow-dispatch` |
| `reason_sha256` | 문자열 | 이유 원문의 64자리 소문자 SHA-256 |
| `issued_at_epoch` | 정수 | 현재보다 미래가 아니고 만료보다 작음 |
| `expires_at_epoch` | 정수 | 발급 후 최대 900초, 검증 시 아직 지나지 않음 |

### 파일 불변식

- 고정 경로 `/run/auto-invest-deploy/emergency-request.json`의 정규 파일이다.
- root 소유, `auto-invest` 그룹 읽기 전용이며 group/world 쓰기 권한이 없다.
- 심볼릭 링크를 허용하지 않는다.
- 루트 helper가 파일 설치 전에 감사 장부에 `request_id`를 한 번 기록하고, 배포 실행기는 같은 내용과 상관관계 식별자를 재검증한다. 같은 상관관계에 `DEPLOY_STARTED`가 생기면 소비 완료다.
- helper는 실행 결과와 무관하게 요청 파일을 제거한다.

### 상태 전이

`CREATED -> VALIDATED -> PREAUTHORIZED -> CONSUMED -> REMOVED`

- 모든 검증 실패는 `REJECTED -> REMOVED`다.
- `PREAUTHORIZED` 또는 `CONSUMED` 요청 ID는 새 승인으로 다시 만들 수 없다. 배포 실행기는 정확히 일치하고 아직 `DEPLOY_STARTED`가 없는 `PREAUTHORIZED` 한 건만 이어받는다.

## DeployMaintenanceInterlock

배포와 실주문이 겹치지 않게 하는 루트 소유 상태다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `request_id` | 문자열 | 잠금을 만든 긴급 요청 |
| `target_sha` | 문자열 | 배포 대상 |
| `workflow_run_id` | 문자열 | 운영 추적 ID |
| `created_at_epoch` | 정수 | 잠금 설치 시각 |
| `state` | 열거 | `QUIESCED`, `DEPLOYING`, `HEALTHY`, `ROLLED_BACK`, `HALTED` |
| `reason` | 문자열 | 정화된 상태 이유 |

### 불변식

- 고정 경로 `/run/auto-invest-deploy/live-order-maintenance.lock`이다.
- root 소유이고 신뢰하지 않는 사용자가 쓸 수 없다.
- 파일이 존재하는 동안 두 scheduler는 거래일 선점 전, 주문 router는 각 중개사 쓰기 직전에 거부한다.
- 루트 helper는 이전 버전이 이 파일을 모를 수 있으므로 기존 scheduler timer, 실행 중인 scheduler service, 장기 worker를 명시적으로 중지하고 비활성 상태를 확인한 뒤 KIS smoke를 수행한다.
- `HEALTHY` 또는 `ROLLED_BACK`이 검증됐을 때만 제거된다.
- `HALTED`는 자동 만료되지 않는다.
- 새 등록 오너 단회 요청은 root 소유 정규 파일·닫힌 HALTED 스키마·배타 잠금과 이전 요청의 유일한 `DEPLOY_EMERGENCY_AUTHORIZED`·`DEPLOY_STARTED=0`을 함께 증명한 경우에만 잠금을 인계한다.
- 요청 파일과 `QUIESCED` 잠금이 함께 남은 terminal rollback orphan은 두 파일의 root 소유·0640·닫힌 스키마·동일 신원, 배타 잠금, 승인 1·시작 1·실패 1·커널 변경 0~1·롤백 1·완료 0·예상 밖 사건 0, 최신 롤백이 모두 증명되어야 한다. production HEAD가 rollback 기준이면 기존 복구를 계속하고, 이미 정확한 current-main으로 전진했으면 rollback 기준의 Git 후손, rollback 뒤 current-main 일반 live 배포의 유일한 시작·완료와 실패/롤백 0, in-window worker 시작, 현재 worker/timer active, 미체결 0건을 추가로 증명한 cleanup-only 복구만 허용한다.
- 그 밖의 `DEPLOY_STARTED`, 불완전한 롤백, 장부·파일·생산 HEAD 모호성은 인계하지 않고 주문 잠금을 유지한다.

## DeployEmergencyAuthorizedAudit

기존 `audit_log`의 새 추가 전용 사건이다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `event_type` | 문자열 | `DEPLOY_EMERGENCY_AUTHORIZED` |
| `request_id` | 문자열 | 단회 요청 ID |
| `target_sha` | 문자열 | 승인된 정확한 커밋 |
| `actor` | 문자열 | 정확한 등록 오너 actor |
| `workflow_run_id` | 문자열 | 신뢰된 실행 ID |
| `source` | 문자열 | 고정 승인 출처 |
| `reason_sha256` | 문자열 | 이유 다이제스트 |
| `issued_at_epoch` | 정수 | 발급 시각 |
| `expires_at_epoch` | 정수 | 만료 시각 |

`correlation_id`는 뒤따르는 `DEPLOY_STARTED`, `DEPLOY_COMPLETED` 또는 `DEPLOY_FAILED`, `DEPLOY_ROLLED_BACK`과 같다.

## DeployEmergencyRecoveryCompletedAudit

후속 정상 배포가 이미 생산을 전진시킨 terminal rollback orphan을 코드·서비스 재변경 없이 회수한 추가 전용 사건이다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `event_type` | 문자열 | `DEPLOY_EMERGENCY_RECOVERY_COMPLETED` |
| `request_id` | 문자열 | 이번 exact-main 등록 오너 요청 |
| `target_sha` | 문자열 | 현재 생산 HEAD와 같은 정확한 current-main |
| `actor` | 문자열 | 정확한 등록 오너 actor |
| `workflow_run_id` | 문자열 | 이번 신뢰 실행 ID |
| `prior_request_id` | 문자열 | 남아 있던 rollback orphan 요청 |
| `prior_correlation_id` | 문자열 | 검증한 rollback 감사 체인 |
| `completed_deploy_correlation_id` | 문자열 | 현재 target의 검증된 정상 live 배포 체인 |
| `recovery_basis` | 문자열 | 정확히 `subsequent-live-deploy-completed` |
| `open_unfilled` | 정수 | 정확히 `0` |

이 사건은 이번 `DEPLOY_EMERGENCY_AUTHORIZED`와 같은 새 `correlation_id`를 사용한다. 이 체인은 코드 배포가 아니라 잠금 복구이므로 `DEPLOY_STARTED`를 만들지 않는다.

## DeployEmergencyOrphanRecoveredAudit

생산이 rollback 기준과 새 승인 대상 사이의 검증된 건강한 일반 배포에 있을 때, 이전 orphan 잠금을 새 exact-target 긴급 배포로 인계한 추가 전용 비종료 사건이다.

| 필드 | 형식 | 설명 |
|---|---|---|
| `event_type` | 문자열 | `DEPLOY_EMERGENCY_ORPHAN_RECOVERED` |
| `request_id` | 문자열 | 이번 exact-target 등록 오너 요청 |
| `target_sha` | 문자열 | 새 정확한 current-main 대상 |
| `actor` | 문자열 | 정확한 등록 오너 actor |
| `workflow_run_id` | 문자열 | 이번 신뢰 실행 ID |
| `prior_request_id` | 문자열 | 남아 있던 rollback orphan 요청 |
| `prior_correlation_id` | 문자열 | 검증한 rollback 감사 체인 |
| `completed_deploy_correlation_id` | 문자열 | 현재 생산 SHA의 검증된 정상 live 배포 체인 |
| `recovered_production_sha` | 문자열 | 잠금 인계 시점의 건강한 생산 HEAD |
| `recovery_basis` | 문자열 | 정확히 `subsequent-live-deploy-forward-handoff` |
| `open_unfilled` | 정수 | 정확히 `0` |

이 사건은 성공 종료가 아니다. 같은 상관관계에서 뒤따르는 `DEPLOY_STARTED`와 최종 `DEPLOY_COMPLETED` 또는 `DEPLOY_ROLLED_BACK`이 있어야 잠금을 해제할 수 있다.

## EmergencyDeployOutcome

| 상태 | 잠금 | 요청 | 감사 |
|---|---|---|---|
| 성공 | 건강 검사 뒤 제거 | 제거·소비됨 | AUTHORIZED -> STARTED -> COMPLETED |
| 이전 버전 복구 성공 | 복구 건강 확인 뒤 제거 | 제거·소비됨 | AUTHORIZED -> STARTED -> FAILED -> ROLLED_BACK |
| 복구 실패 | 유지 | 제거·소비됨 | AUTHORIZED -> STARTED -> FAILED -> FAILED(rollback) |
| 사전 검증 실패 | 생성 전 또는 안전 제거 | 제거·미소비/거부 | FAILED(precondition) |
| 후속 정상 배포 증명 뒤 잠금만 복구 | 기존 worker/timer를 유지한 채 제거 | 이전 orphan 제거 | AUTHORIZED -> EMERGENCY_RECOVERY_COMPLETED |
| 건강한 중간 배포에서 새 대상 인계 | 같은 잠금 유지 | 이전 orphan 제거 뒤 새 요청 설치 | AUTHORIZED -> EMERGENCY_ORPHAN_RECOVERED -> STARTED -> COMPLETED/ROLLED_BACK |
