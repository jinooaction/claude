# Research: 자율 루프 품질 폐쇄

## Decision: Codex 실행 계약은 작업 패킷 안에 둔다

**Rationale**: 다음 세션이 가장 먼저 읽는 표면은 `automation/autonomous-work-execution-last-run`이다. 실행 계약을 별도 문서에 두면 또 다른 진입점이 생긴다. 작업 패킷 JSON과 Markdown에 자율 착수 수준, 착수 설명, 완료 관문을 넣으면 한 표면으로 판단이 끝난다.

**Alternatives considered**:

- 완전 자동 코드 수정 루프를 만든다. 거부: 현재 안전 경계상 코드 변경은 Codex 작업 절차, 검증, PR 품질 관문, 자동 머지 조건을 통과해야 한다.
- HANDOFF에만 문구를 추가한다. 거부: HANDOFF는 사람 진입점이고 자동 루프의 기계 판독 계약이 아니다.

## Decision: 관측 수 차이는 정보성 provenance로 보고한다

**Rationale**: `14/20`과 `15/20`이 함께 보이는 것은 서로 다른 sidecar 실행 시각에서 자연스럽게 생길 수 있다. live 상태와 stage가 같고 모든 게이트가 관측 부족 대기를 말하면 장애로 올리지 않고, 관측 범위와 출처를 표시한다.

**Alternatives considered**:

- 항상 최신 숫자 하나로 덮어쓴다. 거부: 어떤 sidecar가 어떤 시각에 판단했는지 사라져 사후 재현성이 떨어진다.
- 모든 숫자 차이를 `MISALIGNED`로 올린다. 거부: 정상 스케줄 차이를 장애로 오판한다.

## Decision: operator-status 뒤 pipeline-liveness를 workflow_run으로 다시 실행한다

**Rationale**: operator-status는 09:25 UTC에 실행되고 기존 pipeline-liveness는 더 이른 시간 또는 관련 코드 push에 실행될 수 있다. operator-status 완료 뒤 생존 감시가 한 번 더 돌 수 있으면 다음 세션이 최신 상태를 읽는다.

**Alternatives considered**:

- pipeline-liveness cron만 늦춘다. 거부: 기존 이른 감시의 가치가 줄고 push 직후 지연을 완전히 해결하지 못한다.
- operator-mobile-alerts 안에서 GitHub CLI로 workflow를 직접 dispatch한다. 거부: 권한과 실패 처리가 더 복잡하고, 단순 완료 이벤트보다 취약하다.
