# Research: Broker Rejection Taxonomy Contract

## Decision 1: Build a focused taxonomy probe instead of extending execution-quality in place

**Decision**: Add `broker_rejection_taxonomy.py` and `broker_rejection_taxonomy_probe.py` as a read-only contract layer over existing sidecars.

**Rationale**: `execution-quality` already aggregates monitor, history, broker rejection counts, and KIS smoke state. The selected candidate asks for a narrower classification contract: cause family, recurrence risk, confidence, and no-retry action. A focused probe keeps the source package stable and gives released-work a clean completion marker.

**Alternatives considered**: Add more fields directly to `execution_quality.py`. Rejected because it would mix raw evidence packaging with candidate-specific contract interpretation and make future execution-quality candidates harder to separate.

## Decision 2: Classify `APBK1672` as observed KIS order response rejection, not whole-broker outage

**Decision**: Treat `APBK1672` as a stable observed broker response rejection signature with high confidence when it appears in parsed rejected-order rows and KIS smoke is healthy.

**Rationale**: Current evidence shows rejected orders 2, parsed broker errors 2, KIS code `APBK1672` 2, and KIS smoke success. That supports "the order response was rejected and parsed" but does not prove the entire broker is unavailable or that a future order would be accepted.

**Alternatives considered**: Label it as broker outage. Rejected because KIS smoke success and HTTP 200 response evidence contradict a blanket outage claim.

## Decision 3: Gate readiness on parseability and observed rejected-order evidence

**Decision**: Use `CONTRACT_READY` only when required evidence is parseable and at least one broker rejection signature is classified. Use `OBSERVATION_WAIT` for parseable but insufficient observations, and `BLOCKED` for missing/malformed required inputs.

**Rationale**: The contract is a classifier. It should not fail just because no new rejection exists, but it also should not claim readiness when the primary source cannot be parsed.

**Alternatives considered**: Always emit ready with an empty taxonomy. Rejected because it would let released-work close a candidate whose core classification did not run.

## Decision 4: Live intent loss blocks retry guidance

**Decision**: When micro GTAA reports `latest_intent_loss`, the taxonomy report preserves that context and says not to retry orders automatically.

**Rationale**: The current safety posture is that latest rejected-order opportunity signal blocks live attempts. This candidate is diagnostic only; it must not weaken the strategy-intent gate.

**Alternatives considered**: Recommend broker/order retry once KIS smoke is healthy. Rejected because that would cross from evidence classification into live money behavior.

## Decision 5: Completion marker advances to execution cost basis

**Decision**: Record `completed_candidate_id: candidate-broker-rejection-taxonomy-contract` and `next_candidate_id: candidate-execution-cost-basis-contract`.

**Rationale**: 스펙 102의 체결 품질 frontier 순서가 이미 브로커 거부 분류 다음에 체결 비용 기준을 둔다. 완료 마커를 남기면 released-work가 같은 후보 반복을 막고 autonomous-work가 다음 후보로 전진한다.

**Alternatives considered**: Move directly to broker diagnostic liveness. Rejected because the configured frontier order places execution cost basis first.
