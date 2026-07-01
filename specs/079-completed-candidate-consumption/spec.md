# 스펙 079: 완료 후보 소비 및 차순위 자동 승격 루프

**기능 브랜치**: `Codex/079-completed-candidate-consumption`  
**작성일**: 2026-07-02  
**상태**: Draft  
**위험 등급**: 등급 2(운영 자동화 변경, 읽기 전용 후보 상태 소비)

## 사용자 시나리오 및 테스트

### 사용자 이야기 1 - 완료된 후보를 다시 고르지 않는다 (우선순위: P1)

운영자는 이미 구현·머지·인계까지 끝난 후보가 다음 자율 작업으로 반복 선택되는 것을 보지 않아야 한다.

**독립 테스트**: 완료 장부에 `candidate-fd04772a23c5`가 있으면 자율 작업 실행 루프는 이 후보를 실행 가능 목록에서 제외하고 차순위 후보를 선택한다.

**인수 시나리오**:

1. **Given** 스펙 078이 완료되어 `candidate-fd04772a23c5`가 출시 완료 장부에 있다.
2. **When** 자율 작업 실행 루프가 최신 후보 backlog와 완료 장부를 함께 읽는다.
3. **Then** `candidate-fd04772a23c5`는 `RELEASED`로 억제되고, 다음 실행 가능 후보가 선택된다.

### 사용자 이야기 2 - 완료 장부를 자동 발행한다 (우선순위: P1)

완료 후보 상태는 채팅이나 handoff 문장에만 남지 않고 자동 sidecar로 발행되어야 한다.

**독립 테스트**: repository scan probe가 완료된 spec 디렉터리와 명시 후보 식별자를 읽어 `released_work.json`과 `LAST_RUN.md`를 만든다.

**인수 시나리오**:

1. **Given** 어떤 spec의 `tasks.md`가 모두 완료됐고 계약 문서에 `selected_work_candidate`가 있다.
2. **When** 완료 작업 장부 probe가 실행된다.
3. **Then** 해당 후보는 `released` entry로 발행되고 원천 spec 경로가 함께 기록된다.

### 사용자 이야기 3 - 자동 루프 생존 감시가 완료 장부도 추적한다 (우선순위: P2)

다음 세션은 완료 후보 소비 기능이 멈췄는지 pipeline liveness에서 확인할 수 있어야 한다.

**독립 테스트**: pipeline liveness 기본 감시 목록에 `released-work`가 비핵심 sidecar로 등록된다.

**인수 시나리오**:

1. **Given** `released-work` workflow가 sidecar를 발행한다.
2. **When** pipeline liveness가 실행된다.
3. **Then** `released-work` 신선도가 감시 표면에 포함된다.

### 예외 상황

- 완료 장부가 없으면 기존 자율 작업 선택은 fail-open으로 계속된다.
- 완료 장부가 깨졌으면 해당 증거만 `malformed`로 표시하고, 후보 선택은 기존 evidence로 계속한다.
- 완료 장부가 후보를 `released`로 표시하면 같은 후보가 다른 source에서 `new`로 올라와도 실행 가능 후보가 될 수 없다.
- 완료 장부는 실거래 상태나 자본 준비도를 바꾸지 않는다.

## 요구사항

### 기능 요구사항

- **FR-001**: 시스템은 완료된 자율 작업 후보를 `released_work.json` sidecar로 발행해야 한다.
- **FR-002**: 시스템은 완료된 spec의 `tasks.md`가 모두 체크됐는지 확인해야 한다.
- **FR-003**: 시스템은 완료된 spec 안의 명시적 후보 식별자 필드(`selected_work_candidate`, `released_candidate_id`, `completed_candidate_id`)만 출시 후보로 해석해야 한다.
- **FR-004**: 시스템은 `released_work.json`의 후보를 `RELEASED` 상태로 표시하고 자율 작업 실행 가능 후보에서 제외해야 한다.
- **FR-005**: 시스템은 완료 후보가 다른 source에서 다시 `new`로 올라와도 완료 장부를 우선해야 한다.
- **FR-006**: 시스템은 완료 장부가 없거나 malformed여도 기존 후보 선택 루프를 중단하지 않아야 한다.
- **FR-007**: 시스템은 workflow 실행 시 repository scan 결과를 즉시 자율 작업 실행 루프에 넣어 main push 경합으로 완료 후보가 다시 선택되는 일을 줄여야 한다.
- **FR-008**: 시스템은 `LAST_RUN.md`와 `released_work.json`을 발행해야 한다.
- **FR-009**: 시스템은 pipeline liveness에 `released-work` sidecar를 등록해야 한다.
- **FR-010**: 시스템은 주문, 자본 배분, 브로커 호출, live 설정 변경, 허용 종목·포지션 한도 변경, 비밀값 접근, 외부 유료 서비스 호출을 수행하지 않아야 한다.

### 핵심 엔티티

- **ReleasedWorkEntry**: 출시 완료 후보 식별자, 상태, 원천 spec, 원천 증거 파일, 사유, 발견 시각을 포함한다.
- **ReleasedWorkReport**: 실행 메타데이터, 완료 후보 목록, 스캔된 spec 수, 안전 불변조건을 포함한다.
- **WorkPacket**: 기존 자율 작업 실행 후보. 완료 장부에 있으면 상태가 `RELEASED`로 바뀐다.

## 안전 경계

- 읽기 전용이다. repository 문서와 기존 sidecar를 읽고 자기 sidecar만 발행한다.
- 실거래, 주문, 계좌 자본 배분, 라이브 전략 변경, 허용 종목·포지션 한도 변경을 하지 않는다.
- 헌법, 커널 목록, 자본 사다리 공식, 브로커 비밀값, 감사 로그 기록 방식을 바꾸지 않는다.
- 완료 장부는 후보 선택 반복을 막는 운영 장부다. 후보의 투자 판단, 승격 게이트, 자본 게이트를 대체하지 않는다.

## 성공 기준

- **SC-001**: 같은 repository 입력으로 두 번 실행하면 같은 released candidate 목록과 같은 entry id가 나온다.
- **SC-002**: 스펙 078 완료 상태에서 `candidate-fd04772a23c5`가 `released`로 발행된다.
- **SC-003**: 자율 작업 실행 루프는 완료 장부를 읽으면 `candidate-fd04772a23c5` 대신 차순위 실행 가능 후보를 선택한다.
- **SC-004**: 완료 장부가 없거나 깨진 입력에서도 기존 후보 선택 테스트가 통과한다.
- **SC-005**: `uv run pytest`와 `uv run ruff check src tests`가 통과한다.
- **SC-006**: 새 workflow에는 브로커, 주문, 라이브 전환, 원격 서버 명령, 외부 배포 명령이 포함되지 않는다.

## 가정

- 완료 후보의 신뢰 가능한 자동 근거는 완료된 spec 산출물이다.
- 완료 후보 식별자는 임의의 `candidate-...` 언급이 아니라 명시 필드로만 해석한다.
- 이미 출시된 스펙 078은 `selected_work_candidate` 필드로 `candidate-fd04772a23c5`를 기록한다.
- 기존 `learning_ledger.json`은 실패·증거 의존·운영자 검토 상태를 담고, 새 `released-work` 장부는 출시 완료 상태를 담는다.

## 비목표

- 실제 매매, 실거래 전환, 자본 배분, 전략 교체를 수행하지 않는다.
- 완료 후보를 GitHub PR이나 commit에서 자연어로 추론하지 않는다.
- 실패 후보 장부의 의미를 바꾸지 않는다.
- workflow 안에서 코드 자동 수정, PR 생성, 자동 머지를 수행하지 않는다.
