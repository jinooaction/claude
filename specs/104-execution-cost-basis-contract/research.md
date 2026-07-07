# Research: Execution Cost Basis Contract

## Decision 1: Build a focused cost-basis probe instead of changing execution-quality source generation

**Decision**: Add `execution_cost_basis.py` and `execution_cost_basis_probe.py` as a read-only contract layer over existing sidecars.

**Rationale**: The selected candidate asks whether actual cost-basis evidence is sufficient, not to create new broker samples. A focused probe can consume the current `execution-quality` shape and a future `execution_cost_basis` block without changing the source workflow.

**Alternatives considered**: Add cost-basis fields directly to `execution_quality.py`. Rejected for this slice because current remote evidence has no accepted/fill samples, and changing the producer would not make real cost evidence appear without crossing into live-money collection.

## Decision 2: Treat missing cost-basis block as observation wait

**Decision**: If required sidecars parse but `execution-quality.execution_cost_basis` is absent, return `OBSERVATION_WAIT`.

**Rationale**: Current sidecars are healthy enough to read, but they do not contain accepted/fill cost-basis evidence. That is a normal frontier observation gap, not a broken input.

**Alternatives considered**: Return `BLOCKED`. Rejected because it would confuse schema absence with operational failure and make the autonomous loop look broken while it is simply waiting for sufficient evidence.

## Decision 3: Require measurable accepted/fill basis for ready status

**Decision**: `CONTRACT_READY` requires a complete cost-basis block with accepted/fill or measurable fill evidence.

**Rationale**: Rejected orders and `PREVIEW_ONLY` state cannot prove realized trading cost. The report should prevent overclaiming cost-adjusted edge readiness.

**Alternatives considered**: Treat any accepted/fill count as ready. Rejected because a count without slippage/turnover basis still cannot support cost adequacy.

## Decision 4: Preserve money-path safety context

**Decision**: Read `money-path` for `PREVIEW_ONLY`, real-order submission capability, armed state, accepted/fill count, and broker rejection count, but do not mutate anything.

**Rationale**: Cost-basis evidence is adjacent to live-money behavior. The contract needs the context while keeping the money path read-only.

**Alternatives considered**: Trigger a sample collection or retry path. Rejected because it would be a money-path or broker-side effect and outside the candidate's safety boundary.

## Decision 5: Completion marker advances to broker diagnostic liveness

**Decision**: Record `completed_candidate_id: candidate-execution-cost-basis-contract` and `next_candidate_id: candidate-broker-diagnostic-liveness-contract`.

**Rationale**: 스펙 102의 체결 품질 frontier 순서가 체결 비용 기준 다음에 브로커 진단 생존성을 둔다. 완료 마커를 남기면 released-work가 같은 후보 반복을 막고 autonomous-work가 다음 후보로 전진한다.

**Alternatives considered**: Loop back to cost-adjusted edge experiment. Rejected because frontier order already places broker diagnostic liveness next.
