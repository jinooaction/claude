# Quickstart: Autonomous Production Approval

1. 회귀 테스트로 preview -> machine approval -> production 의존성과 이벤트 분기를 확인한다.
2. 변경을 main에 머지하고 배포 성공을 확인한다.
3. GitHub API로 production required reviewer를 빈 목록으로 갱신한다.
4. API를 다시 읽어 reviewer 0명, branch policy `main`을 확인한다.
5. `workflow_dispatch`를 실행해 사람 대기 없이 `manual-no-order-preflight`가 성공하고 주문 0건인지 확인한다.
6. money-path와 capital readiness를 갱신해 `REAL_ORDER_PATH_ARMED`와 다음 예약 시각을 확인한다.

## 실패 시

- 환경 정책이 예상과 다르면 사전점검을 중단하고 required reviewer를 복원한다.
- 수동 실행이 `live-canary-order`를 선택하면 즉시 workflow를 취소하고 변경을 되돌린다.
- 서명·센티넬·배포 SHA 검증이 실패하면 키나 서버 검증을 우회하지 않고 원인을 수정한다.

