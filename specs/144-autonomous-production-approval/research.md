# Research: Autonomous Production Approval

## Decision 1: production 환경은 유지하고 required reviewer만 제거

- **선택**: `environment: production`, 환경 전용 `LIVE_ORDER_SIGNING_KEY`, `main` custom branch policy를 유지한다.
- **이유**: 사람 대기만 없애면서 개인키의 노출 범위와 배포 branch 제한을 그대로 보존한다.
- **기각**: 환경을 제거하고 개인키를 repository secret으로 옮기는 방식은 다른 workflow가 키를 받을 수 있어 비밀 경계를 넓힌다.

## Decision 2: production 작업 앞에 환경 비밀값 없는 기계 승인 작업 추가

- **선택**: preview 결과의 무장·자본과 GitHub event·ref를 별도 job에서 검증하고 명시적 결정을 출력한다.
- **이유**: 사람 검토자가 하던 “이 run이 주문 경로로 가도 되는가”를 코드와 테스트로 재현할 수 있다.
- **기각**: 기존 production job에서만 검사하면 환경 진입과 승인 판단이 한 단계에 섞여 자동화 경계가 보이지 않는다.

## Decision 3: 수동 실행은 계속 주문 없는 검증

- **선택**: `workflow_dispatch`는 `manual-no-order-preflight`, `schedule`만 `scheduled-real-order`로 결정한다.
- **이유**: 배포 직후 서명·서버 권위를 안전하게 검증할 수 있고 휴장일 수동 주문을 막는다.
- **기각**: 모든 비-push 이벤트를 주문으로 취급하면 새 이벤트 추가 때 주문 권한이 뜻하지 않게 넓어진다.

## Rollback

GitHub API로 production 환경에 `jinooaction` required reviewer를 다시 추가하면 다음 run부터 즉시 사람 승인 대기로 돌아간다. 코드의 기계 승인과 서버 검증은 그대로 남아 방어층이 줄지 않는다.

