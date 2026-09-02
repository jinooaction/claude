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
- `DEPLOY_STARTED`가 하나라도 있거나 장부·파일이 모호하면 인계하지 않고 `HALTED`를 유지한다.

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

## EmergencyDeployOutcome

| 상태 | 잠금 | 요청 | 감사 |
|---|---|---|---|
| 성공 | 건강 검사 뒤 제거 | 제거·소비됨 | AUTHORIZED -> STARTED -> COMPLETED |
| 이전 버전 복구 성공 | 복구 건강 확인 뒤 제거 | 제거·소비됨 | AUTHORIZED -> STARTED -> FAILED -> ROLLED_BACK |
| 복구 실패 | 유지 | 제거·소비됨 | AUTHORIZED -> STARTED -> FAILED -> FAILED(rollback) |
| 사전 검증 실패 | 생성 전 또는 안전 제거 | 제거·미소비/거부 | FAILED(precondition) |
