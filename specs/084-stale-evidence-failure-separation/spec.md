# Feature Specification: Stale Evidence Failure Separation

**Feature Branch**: `Codex/084-stale-evidence-failure-separation`
**Created**: 2026-07-02
**Status**: Draft
**Input**: User description: "남은 관찰 지점은 뭐야? 이것도 남기지 않고 진행하면 되는거 아니야?" and autonomous work packet `candidate-6ee3370e933d`.

## User Scenarios & Testing

### User Story 1 - 오래된 증거를 후보 실패와 분리한다 (Priority: P1)

운영자는 자본 경로 준비도 보고서에서 이미 끝난 후보, 오래된 sidecar, 누락된 sidecar가 실제 전략 성과 실패처럼 섞이지 않고 별도 관측 이슈로 보이기를 원한다.

**Why this priority**: 현재 자율 작업 루프는 `capital-path-readiness`를 다음 작업 입력으로 삼는다. 이 입력이 오래된 증거를 후보 문제로 표현하면 다음 세션이 완료된 후보를 다시 조사하거나, 데이터 생산 지연을 전략 실패로 오해할 수 있다.

**Independent Test**: `capital_path_readiness` 입력에 `released-work`, `pipeline-liveness`, evolution backlog가 함께 들어오면 보고서는 우선 후보와 관측 이슈를 분리하고, 완료된 후보는 우선 후보에서 제외한다.

**Acceptance Scenarios**:

1. **Given** evolution backlog에 이미 출시된 후보가 남아 있음, **When** 자본 경로 준비도 보고서를 생성함, **Then** 해당 후보는 우선 후보가 아니라 억제 후보와 관측 이슈로 기록된다.
2. **Given** pipeline liveness가 stale 또는 missing sidecar를 보고함, **When** 보고서를 생성함, **Then** stale 목록은 `observability_issues`에 기록되고 전략 실패나 돈 경로 차단으로 표현되지 않는다.
3. **Given** pipeline liveness가 OK이고 출시 후보도 없음, **When** 보고서를 생성함, **Then** 관측 이슈 목록은 비어 있고 기존 우선 후보 정렬은 유지된다.

---

### User Story 2 - probe와 workflow가 새 입력을 소비한다 (Priority: P1)

운영자는 매일 발행되는 `capital-path-readiness` sidecar가 `released-work`와 `pipeline-liveness`를 직접 읽어 최신 완료 상태와 증거 신선도 상태를 반영하기를 원한다.

**Why this priority**: 코드가 새 필드를 지원해도 workflow manifest가 새 sidecar를 수집하지 않으면 자동 루프에서 효과가 재현되지 않는다.

**Independent Test**: `scripts/capital_path_readiness_probe.py --manifest`가 새 입력 sidecar를 포함하고, probe 통합 테스트가 JSON/Markdown에 관측 이슈를 출력한다.

**Acceptance Scenarios**:

1. **Given** probe manifest를 실행함, **When** 출력 라인을 확인함, **Then** `released-work`와 `pipeline-liveness` source ref가 포함된다.
2. **Given** 읽기 전용 workflow 파일을 검사함, **When** 금지 토큰을 확인함, **Then** broker/API/order/live 명령이 추가되지 않는다.
3. **Given** Markdown 보고서를 생성함, **When** 내용을 확인함, **Then** 관측 이슈 섹션이 후보 섹션과 따로 보인다.

### Edge Cases

- `released-work` sidecar가 없으면 기존 ledger 억제만 유지하고 후보를 임의로 출시 처리하지 않는다.
- `pipeline-liveness` JSON이 Markdown fence 안에 있거나 raw JSON이어도 읽을 수 있어야 한다.
- liveness check에 `status=OK`만 있으면 관측 이슈를 만들지 않는다.
- malformed sidecar는 probe 실패가 아니라 관측 입력 파싱 상태로 남는다.
- 이 feature는 주문 재시도, 실제 주문, 계좌 자본 배분, whitelist/caps/live 설정, 외부 유료 서비스 호출을 절대 하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST add an `observability_issues` list to `capital_path_readiness.json`.
- **FR-002**: System MUST suppress released candidates from `priority_candidates` when `released-work` says the candidate is released.
- **FR-003**: System MUST record released-candidate echoes as observability issues instead of strategy or execution failures.
- **FR-004**: System MUST convert non-OK pipeline liveness checks into observability issues with source key, status, severity, and Korean next action.
- **FR-005**: System MUST keep money-path readiness state, live money state, and required gates unchanged by observability issues.
- **FR-006**: The probe manifest MUST consume `released-work` and `pipeline-liveness` sidecars.
- **FR-007**: The Markdown report MUST show observability issues in a separate section from priority and suppressed candidates.
- **FR-008**: The workflow and probe MUST remain read-only and MUST NOT call broker APIs, SSH, order commands, live-capital commands, PR commands, or merge commands.
- **FR-009**: The completed Speckit contract MUST mark `candidate-6ee3370e933d` as completed so `released-work` can suppress repeat selection after merge.

### Key Entities

- **Readiness Observability Issue**: A structured non-trading issue that explains stale, missing, malformed, or echoed evidence in Korean.
- **Released Candidate Echo**: A backlog or promotion candidate that is already marked released and must not be selected as new work.
- **Pipeline Liveness Issue**: A non-OK liveness check transformed into an observability issue instead of a strategy-failure signal.

## Success Criteria

- **SC-001**: Unit tests prove released candidates are suppressed and recorded as observability issues.
- **SC-002**: Unit tests prove stale or missing liveness checks become observability issues without changing money-path state.
- **SC-003**: Integration tests prove the probe manifest, JSON output, Markdown output, and workflow read-only contract.
- **SC-004**: Full `uv run pytest`, `uv run ruff check src tests`, `scripts/check_handoff_facts.py`, and strict agent harness pass before merge.

## Assumptions

- `released-work` is the authoritative local/sidecar record of completed autonomous candidates.
- Pipeline liveness reports sidecar freshness, not strategy quality.
- Observability issues should guide the next operator or session, but they must not alter live money gates.
