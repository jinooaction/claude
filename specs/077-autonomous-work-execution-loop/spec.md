# 스펙 077: 자율 작업 실행 루프

**기능 브랜치**: `Codex/077-autonomous-work-execution-loop`  
**작성일**: 2026-07-01  
**상태**: Draft  
**위험 등급**: 등급 2(운영 체계 변경, 읽기 전용 보고 루프)

## 사용자 시나리오 및 테스트

### 사용자 이야기 1 - 다음 작업을 자동으로 고른다 (우선순위: P1)

운영자는 매번 "다음엔 뭘 해야 하냐"고 묻지 않아도, 시스템이 최신 자율 루프 산출물을 읽고 돈을 더 벌 확률을 높이는 다음 작업 패킷을 자동으로 발행하길 원한다.

**독립 테스트**: 최신 sidecar 스냅샷을 probe에 넣으면 JSON과 Markdown에 `selected_work`가 생기고, 후보 식별자, 근거, 위험 등급, 다음 행동이 표시된다.

**인수 시나리오**:

1. **Given** `capital-path-readiness`, `autonomous-evolution`, `pipeline-liveness` sidecar가 존재한다.
2. **When** 자율 작업 실행 probe가 실행된다.
3. **Then** 최고 우선순위 후보가 `EXECUTION_READY` 또는 `OPERATOR_APPROVAL_REQUIRED` 상태의 작업 패킷으로 발행된다.

### 사용자 이야기 2 - 위험한 일은 실행 가능으로 올리지 않는다 (우선순위: P1)

실제 주문, 자본 배분, 허용 종목 확대, 포지션 한도 완화, 비밀값, 헌법·커널, 유료 외부 서비스가 닿는 후보는 자동 실행 후보가 아니라 운영자 승인 필요 후보로 분리되어야 한다.

**독립 테스트**: 후보 제목이나 다음 행동에 주문·자본·한도·비밀값·커널·유료 서비스 키워드가 들어가면 작업 패킷 상태가 `OPERATOR_APPROVAL_REQUIRED`로 바뀐다.

**인수 시나리오**:

1. **Given** 후보가 "실제 주문 제출 자동화"를 제안한다.
2. **When** 자율 작업 실행 루프가 후보를 평가한다.
3. **Then** `selected_work.status` 또는 억제 목록에 `OPERATOR_APPROVAL_REQUIRED`가 표시되고, workflow에는 주문·브로커 명령이 없다.

### 사용자 이야기 3 - 다음 세션이 바로 이어받는다 (우선순위: P2)

다음 Codex 세션은 최신 `automation/autonomous-work-execution-last-run` sidecar만 읽어도 착수할 작업, 근거, 필요한 입력, 안전 경계를 이해할 수 있어야 한다.

**독립 테스트**: workflow가 `LAST_RUN.md`와 `autonomous_work_execution.json`을 발행하고, pipeline liveness 레지스트리에 이 sidecar가 등록된다.

**인수 시나리오**:

1. **Given** workflow가 main에서 실행된다.
2. **When** sidecar 브랜치를 확인한다.
3. **Then** Markdown 요약과 기계 판독 JSON이 모두 존재하고, 생존 감시가 이 루프의 신선도를 추적한다.

## 요구사항

### 기능 요구사항

- **FR-001**: 시스템은 기존 automation sidecar를 읽어 결정론적으로 작업 후보를 수집해야 한다.
- **FR-002**: 시스템은 `capital-path-readiness`의 우선 후보를 자본 경로 정렬 후보로 반영해야 한다.
- **FR-003**: 시스템은 `autonomous-evolution` backlog, learning ledger, promotion summary, candidate factory, candidate result evidence를 읽어 후보를 보강해야 한다.
- **FR-004**: 시스템은 `pipeline-liveness`가 `CRITICAL`이면 일반 후보보다 파이프라인 복구 작업을 우선해야 한다.
- **FR-005**: 시스템은 후보별 `risk_grade`, `safety_impact`, 제목, 문제, 다음 행동을 보고 자동 실행 가능 여부를 분류해야 한다.
- **FR-006**: 시스템은 등급 3 이상 또는 주문·자본·허용 종목·한도·비밀값·배포 제한·헌법/커널·라이브 전략·유료 외부 서비스 표면을 가진 후보를 `OPERATOR_APPROVAL_REQUIRED`로 표시해야 한다.
- **FR-007**: 시스템은 실제 코드 수정, 브랜치 생성, 풀 리퀘스트 생성, 머지, 주문, 자본 배분, 브로커 호출, 외부 유료 서비스 사용을 수행하지 않아야 한다.
- **FR-008**: 시스템은 `LAST_RUN.md`와 `autonomous_work_execution.json`을 발행해야 한다.
- **FR-009**: 시스템은 모든 입력 증거의 존재 여부와 파싱 상태를 보고해야 한다.
- **FR-010**: 시스템은 pipeline liveness 레지스트리에 등록되어 침묵 실패가 드러나야 한다.

### 핵심 엔티티

- **EvidenceSurface**: 입력 sidecar 한 개의 출처, 존재 여부, 파싱 상태, 요약.
- **WorkPacket**: 다음 Codex 작업 단위. 후보 식별자, 영역, 제목, 점수, 위험 등급, 상태, 근거, 필요한 입력, 안전 경계를 포함한다.
- **AutonomousWorkExecutionReport**: 선택된 작업, 후보 순위, 억제 후보, 입력 증거, 안전 불변조건을 담은 최종 보고.

## 안전 경계

- 읽기 전용이다. 기존 sidecar와 repo 문서를 읽고 자기 sidecar만 발행한다.
- 실거래, 주문, 계좌 자본 배분, 라이브 전략 변경, 허용 종목·포지션 한도 변경을 하지 않는다.
- 운영자 승인 없는 외부 비용 발생을 하지 않는다.
- 이 루프의 산출물은 "다음 작업 패킷"이지 자동 코드 작성 명령이 아니다. 실제 구현·검증·머지는 기존 Codex 작업 절차와 PR 품질 관문을 통과해야 한다.

## 성공 기준

- **SC-001**: 같은 입력 sidecar로 두 번 실행하면 같은 `selected_work`와 후보 순서가 나온다.
- **SC-002**: 위험 후보는 자동 실행 가능 상태가 되지 않는다.
- **SC-003**: 최신 실제 sidecar를 수집한 로컬 smoke에서 JSON과 Markdown이 생성된다.
- **SC-004**: `uv run pytest`와 `uv run ruff check src tests`가 통과한다.
- **SC-005**: 새 workflow에는 브로커, 주문, 라이브 전환, 외부 배포 명령이 포함되지 않는다.

## 비목표

- Codex가 스스로 코드를 수정하거나 PR을 생성하는 완전 자동 구현자는 이번 범위가 아니다.
- 실제 매매, 실거래 전환, 계좌 자본 배분은 이번 범위가 아니다.
- 헌법, 커널 목록, 주문 제한, 감사 로그, 비밀값 정책을 바꾸지 않는다.
