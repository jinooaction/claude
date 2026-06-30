# Feature Specification: Candidate Evidence Diagnostics

**Feature Branch**: `Codex/candidate-evidence-diagnostics`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "그럼 다음 작업도 목표 스킬로 꼼꼼하게 준비해서 완수해볼까?"

## User Scenarios & Testing

### User Story 1 - pending 후보의 원인을 구조화 (Priority: P1)

운영자는 후보 결과 실행기에서 `pending`으로 남은 후보를 볼 때, 단순히 "보류"라는 말이 아니라 데이터 부족, 명령 인자 부족, 출력 판독 부족, 시간 초과, 안전 차단처럼 재시도와 보강 방식이 다른 원인을 바로 구분한다.

**Why this priority**: 현재 result executor는 `pass=4`, `pending=5`를 만들지만, `pending` 후보의 다음 행동이 `block_reason_ko`와 출력 일부에 흩어져 있다. 이 상태로는 후보 공장과 승격 루프가 "다음에 무엇을 자동으로 보강해야 하는지"를 안정적으로 소비하기 어렵다.

**Independent Test**: 후보 result fixture에 데이터 미수집 오류, 필수 인자 누락 오류, 통과 증거 부족, 시간 초과, 안전 차단을 넣으면 각 결과 row가 서로 다른 진단 코드, 재시도 가능 여부, 다음 행동을 갖는다.

**Acceptance Scenarios**:

1. **Given** 검증 명령이 "no ingested datasets"를 출력함, **When** result executor가 결과를 만든다, **Then** 결과 row는 데이터 준비 부족 진단과 `ingest-history` 계열 next action을 포함한다.
2. **Given** 검증 명령이 필수 인자 누락 usage 오류를 출력함, **When** result executor가 결과를 만든다, **Then** 결과 row는 명령 계약 보정 진단과 candidate factory 명령 수정 next action을 포함한다.
3. **Given** 검증 명령은 성공했지만 통과 verdict가 없음, **When** result executor가 결과를 만든다, **Then** 결과 row는 출력 판독 부족 진단과 machine-readable verdict 보강 next action을 포함한다.

---

### User Story 2 - 후보 공장과 승격 루프가 진단을 소비 (Priority: P2)

후보 공장과 승격 루프는 result evidence의 `pending`을 단순 보류로만 보지 않고, 후보의 `promotion_evidence`에 진단 요약과 다음 행동을 보존한다. 따라서 다음 자동 루프가 같은 실패를 반복할지, 입력을 보강할지, 명령 계약을 고칠지 판단할 수 있다.

**Why this priority**: 진단이 result sidecar에만 있고 enriched backlog로 전달되지 않으면 다음 승격 scan은 여전히 `BACKTEST_REQUIRED` 또는 `FACTORY_PACKAGE_READY` 정도만 본다. 영구 자율 성장 루프에는 다음 행동이 후보와 함께 이동해야 한다.

**Independent Test**: result evidence에 `diagnostics`와 `next_actions`가 있는 후보를 candidate factory에 넣으면 enriched backlog의 `promotion_evidence`가 같은 정보를 보존하고, 전략 pass evidence를 허위로 만들지 않는다.

**Acceptance Scenarios**:

1. **Given** 전략 후보 result가 pending diagnostics를 가짐, **When** candidate factory가 result evidence를 소비함, **Then** `promotion_evidence`에 `factory_diagnostics`, `factory_next_actions`, `factory_retryable`이 들어간다.
2. **Given** 비전략 후보 result가 명령 계약 오류 진단을 가짐, **When** candidate factory가 result evidence를 소비함, **Then** 후보는 `pending`으로 남고 명령 보정 next action을 보존한다.
3. **Given** result가 `pass`임, **When** candidate factory가 소비함, **Then** 기존 pass 동작은 유지되고 불필요한 보류 진단은 만들지 않는다.

---

### User Story 3 - 운영자와 자동화가 같은 요약을 본다 (Priority: P3)

운영자는 `LAST_RUN.md`와 JSON sidecar에서 pending 후보별 진단 집계를 보고, 자동화는 같은 JSON 필드를 읽는다. 사람이 보는 설명과 기계가 읽는 원인이 어긋나지 않는다.

**Why this priority**: 운영자가 "그래서 다음에 뭘 해야 하냐"를 물을 때마다 사람이 stderr를 재분석하면 자동 루프가 아니다. Markdown 요약과 JSON 계약이 같은 진단 원천에서 나와야 한다.

**Independent Test**: pending이 섞인 result executor run을 만들면 Markdown에는 진단 집계가 나오고 JSON에는 후보별 진단 코드와 next action이 나온다.

**Acceptance Scenarios**:

1. **Given** pending 후보가 여러 원인으로 존재함, **When** `LAST_RUN.md`가 생성됨, **Then** 진단 코드별 개수와 후보별 다음 행동이 표시된다.
2. **Given** result sidecar JSON이 생성됨, **When** 자동화가 읽음, **Then** `diagnostics`와 `next_actions`가 후보별로 기계 판독 가능하다.
3. **Given** 입력 패키지가 없음, **When** executor가 실행됨, **Then** 누락 입력이 진단으로 기록되고 sidecar 발행은 계속된다.

### Edge Cases

- 여러 명령 중 하나는 데이터 부족이고 다른 하나는 통과 증거 부족이면 가장 보수적인 진단을 대표 원인으로 삼고 전체 진단 목록은 보존한다.
- 안전 차단은 재시도 가능한 `pending`이 아니라 `blocked`로 유지한다.
- 진단은 비밀값, 계좌값, 토큰, 원문 전체 로그를 노출하지 않고 제한된 excerpt와 코드만 남긴다.
- 진단이 생겨도 `pass` 기준은 완화하지 않는다.
- 진단이 생겨도 실거래 주문, 브로커 API, 자본 사다리, whitelist, caps, live sentinel, live 전략 설정은 변경하지 않는다.

## Requirements

### Functional Requirements

- **FR-001**: System MUST attach a machine-readable diagnostic object to every `pending` or `blocked` candidate result row.
- **FR-002**: System MUST classify common pending causes at minimum into data preparation missing, command contract error, insufficient pass evidence, timeout, unsafe command, unsupported package, missing command, and execution failure.
- **FR-003**: System MUST include for each diagnostic a stable code, Korean summary, retryable flag, severity, evidence source, and one or more safe next actions.
- **FR-004**: System MUST preserve raw execution excerpts only after sensitive-value masking and bounded truncation.
- **FR-005**: System MUST keep existing `pass`, `fail`, `pending`, and `blocked` semantics unchanged; diagnostics must not turn a candidate into `pass`.
- **FR-006**: System MUST propagate pending diagnostics from result evidence into candidate factory `promotion_evidence`.
- **FR-007**: System MUST keep non-strategy diagnostics under factory validation context and must not synthesize strategy backtest evidence for them.
- **FR-008**: System MUST summarize diagnostic counts and candidate next actions in the result executor Markdown report.
- **FR-009**: System MUST publish diagnostics in `candidate_result_executor.json` and `candidate_results.json` without requiring broker secrets.
- **FR-010**: System MUST keep the result executor sidecar-only and no-live: no orders, broker API calls, capital changes, whitelist/caps edits, live strategy changes, sentinels, or secret writes.
- **FR-011**: System MUST add tests proving diagnostics flow through result executor, candidate factory, and promotion scan inputs without creating false pass evidence.
- **FR-012**: System MUST keep the `Backtest -> Canary -> Full` order intact; a diagnosed pending strategy may only move after the underlying evidence truly passes.

### Key Entities

- **CandidateEvidenceDiagnostic**: A structured explanation for why a result is pending or blocked, including code, severity, retryability, evidence source, Korean summary, and safe next actions.
- **CandidateNextAction**: A safe, non-live action recommendation that another loop or operator can use to reduce pending state.
- **CandidateResultRow**: Existing candidate result evidence row extended with diagnostics and next actions.
- **PromotionEvidencePatch**: Candidate factory patch that carries diagnostics into enriched backlog without changing pass semantics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of `pending` and `blocked` result rows include at least one diagnostic code and at least one Korean next action.
- **SC-002**: Current 9-package sidecar fixture can be reprocessed with the same `pass=4`, `pending=5`, `fail=0`, `blocked=0` counts while adding diagnostics to all 5 pending rows.
- **SC-003**: Candidate factory preserves diagnostics for every pending result it consumes and does not increase `evidence_passed` count unless pass evidence is present.
- **SC-004**: Result Markdown report includes diagnostic counts and pending next actions, so an operator can identify the next safe work without inspecting raw stderr.
- **SC-005**: Full test and lint gates remain green, and strict agent harness plus handoff fact checks remain OK before merge.

## Assumptions

- The first implementation diagnoses evidence results and carries next actions; it does not automatically run data ingestion, rewrite candidate package commands, or submit new strategy candidates.
- Existing `candidate_results.json` consumers tolerate additive fields.
- Safe next actions are recommendations or future automation inputs, not live money actions.
- The feature is risk grade 2 because it changes operating evidence flow, but it does not change the safety perimeter or money path.
