# Feature Specification: 레짐·성과 후보 점수화

**Feature Branch**: `Codex/082-regime-performance-candidate-scoring`  
**Created**: 2026-07-02  
**Status**: Draft  
**Input**: User description: "candidate-e481b0309206 — 레짐·성과 분석을 후보 점수화 입력으로 승격"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 성과 표면을 후보 점수에 반영 (Priority: P1)

운영자는 자율 성장 루프가 레짐 층화와 승격 준비 성과 표면을 단순 참고 문구가 아니라 후보 점수의 증거 신뢰도와 성장 레버리지에 반영하기를 원한다.

**Why this priority**: 이 후보의 핵심 목표다. 자율 루프가 성과 측정을 점수에 쓰지 못하면 후보 순위가 오래된 정적 가중치에 머문다.

**Independent Test**: 최신과 유사한 sidecar 입력으로 자율 성장 루프를 실행하면 분석 후보의 evidence refs에 레짐과 성과 표면이 함께 나타나고, 성과 표면이 양호할 때 점수가 결정론적으로 보강된다.

**Acceptance Scenarios**:

1. **Given** `regime-stratify`, `public-data`, `promote-readiness` sidecar가 모두 신선함, **When** 자율 성장 루프가 후보를 생성함, **Then** 분석 후보는 세 표면을 evidence refs로 포함하고 성과 기반 보강 점수를 반영한다.
2. **Given** `promote-readiness`가 `READY=false`지만 정상적으로 발행됨, **When** 점수를 계산함, **Then** 후보는 실거래 승격으로 오인되지 않고 읽기 전용 성과 증거로만 사용된다.

---

### User Story 2 - 성과 표면 이상을 과신하지 않음 (Priority: P2)

운영자는 성과 표면이 누락·오래됨·셋업 오류일 때 자율 루프가 이를 수익 기회로 과대평가하지 않고 증거 신뢰도 하락 또는 증거 의존 상태로 분리하기를 원한다.

**Why this priority**: 성과 입력을 점수에 넣는 순간, stale 성과를 강한 신호로 오해하는 위험도 같이 생긴다.

**Independent Test**: `promote-readiness` sidecar가 누락되거나 stale이면 분석 후보의 evidence dependency가 sidecar freshness로 표시되고, 후보 점수는 신선한 성과 입력이 있을 때보다 낮아진다.

**Acceptance Scenarios**:

1. **Given** `promote-readiness` sidecar가 누락됨, **When** 자율 성장 루프가 실행됨, **Then** `promote-readiness`는 stale evidence 목록에 포함되고 분석 후보는 증거 의존 상태가 된다.
2. **Given** `promote-readiness`가 셋업 오류를 보고함, **When** 후보 점수를 계산함, **Then** 성과 보강은 적용되지 않고 다음 행동은 성과 표면 복구 또는 재확인을 요구한다.

---

### User Story 3 - 다음 루프가 새 입력을 수집함 (Priority: P3)

운영자는 GitHub Actions의 자율 성장 루프가 새 성과 표면을 실제로 수집해 sidecar 결과에 반영하기를 원한다.

**Why this priority**: 코드가 새 표면을 읽을 수 있어도 workflow manifest가 수집하지 않으면 운영에서는 아무 효과가 없다.

**Independent Test**: `evolution_loop_probe.py --manifest` 출력과 workflow 테스트가 `promote-readiness` 수집 계약을 포함하는지 확인한다.

**Acceptance Scenarios**:

1. **Given** workflow가 evidence sidecar를 수집함, **When** manifest가 출력됨, **Then** `promote-readiness`가 `automation/promote-readiness-last-run:LAST_RUN.md`로 포함된다.
2. **Given** 자율 성장 루프 workflow가 실행됨, **When** sidecar 수집 단계가 돌면, **Then** 새 성과 표면은 읽기 전용 입력으로만 수집되고 SSH, KIS, 주문 경로는 추가되지 않는다.

### Edge Cases

- `promote-readiness`가 `READY=true`여도 이 기능은 승격을 수행하지 않는다. 점수 입력으로만 사용한다.
- `promote-readiness`가 `READY=false`인 정상 상태는 장애가 아니다. live 기간·트랙레코드 부족 같은 보수적 불합격은 성과 표면의 신뢰 가능한 정보다.
- `regime-stratify`가 신선하지만 `promote-readiness`가 stale이면 후보는 부분 증거 상태로 남고 성과 보강은 제한된다.
- sidecar 원문에 계좌 번호나 비밀값처럼 보이는 값이 있으면 기존 마스킹 규칙을 유지해야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include the `promote-readiness` sidecar as an evidence requirement for autonomous evolution scanning.
- **FR-002**: System MUST include `promote-readiness` in the analysis candidate's evidence refs.
- **FR-003**: System MUST adjust the analysis candidate's score using deterministic regime and performance evidence signals.
- **FR-004**: System MUST reduce or withhold performance score boost when `promote-readiness` is missing, stale, malformed, or setup-error-like.
- **FR-005**: System MUST keep the candidate read-only: no broker API, no orders, no capital allocation, no live strategy change, no whitelist/caps change.
- **FR-006**: System MUST keep `READY=true` and `READY=false` as reporting signals only; neither may trigger promotion, order placement, or capital changes.
- **FR-007**: System MUST expose the new evidence dependency in JSON and Markdown sidecar outputs through existing candidate fields, without adding a new operator entrypoint.
- **FR-008**: System MUST update tests and workflow contract checks so future changes cannot silently drop the performance sidecar from the autonomous evolution loop.

### Key Entities

- **Regime Performance Evidence**: The combined read-only signal from `regime-stratify`, `public-data`, and `promote-readiness`.
- **Analysis Candidate Score**: The candidate score components that rank `candidate-e481b0309206` and related analysis work.
- **Evidence Freshness State**: Whether each required sidecar is fresh, late, stale, missing, or unknown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `evolution_loop_probe.py --manifest` lists `promote-readiness` with the expected automation branch and filename.
- **SC-002**: Unit tests prove a fresh `promote-readiness` sidecar increases or preserves the analysis candidate score relative to missing/stale performance evidence.
- **SC-003**: Unit tests prove missing/stale `promote-readiness` keeps the analysis candidate evidence-dependent rather than overconfident.
- **SC-004**: Integration tests prove the workflow remains read-only and still publishes only the autonomous evolution sidecar.
- **SC-005**: Full validation passes with `uv run pytest`, `uv run ruff check src tests`, strict harness, HANDOFF fact check, and PR quality gate.

## Assumptions

- `promote-readiness` is the current operational surface that best represents live/canary performance readiness for this candidate.
- This feature does not create a new performance workflow; it consumes existing sidecars.
- Any future real-money promotion remains governed by existing capital ladder and reassignment gates, not by this score.
- The work is risk grade 2 because it changes operating automation and candidate ranking, but it does not change safety boundaries or money paths.
