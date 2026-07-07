# Research: Broker Diagnostic Liveness Contract

## Decision 1: Build a focused liveness probe instead of changing KIS smoke or execution-quality producers

**Decision**: Add `broker_diagnostic_liveness.py` and `broker_diagnostic_liveness_probe.py` as a read-only contract layer over existing sidecars.

**Rationale**: The selected candidate asks whether existing broker diagnostic evidence is alive, not to create new broker checks. A focused probe can consume current KIS smoke, execution-quality, and pipeline-liveness evidence without changing workflows or touching broker APIs.

**Alternatives considered**: Add fields directly to `execution_quality.py`. Rejected for this slice because execution-quality already contains broker smoke evidence; the missing piece is the cross-surface PASS/WAIT/FAIL contract.

## Decision 2: Treat missing embedded broker smoke as observation wait when KIS smoke is healthy

**Decision**: If required sidecars parse and standalone KIS smoke is healthy but `execution-quality.broker_smoke` is absent, return `OBSERVATION_WAIT`.

**Rationale**: Healthy standalone KIS smoke means the broker diagnostic itself is not dead, but missing embedded execution-quality evidence means the cross-surface contract is not fully proved.

**Alternatives considered**: Return `BLOCKED`. Rejected because schema absence in one summary would overstate an operational failure while direct KIS smoke remains healthy.

## Decision 3: Treat smoke failure or stale critical pipeline status as blocked

**Decision**: Failed KIS smoke, invalid key, nonzero exit, or stale/critical liveness checks for KIS smoke or execution-quality return `BLOCKED`.

**Rationale**: Broker diagnostic liveness is specifically about whether the diagnostic path is alive. Failure or stale critical evidence means the system cannot safely claim the diagnostic channel is live.

**Alternatives considered**: Return `OBSERVATION_WAIT`. Rejected because these states need repair, not passive observation.

## Decision 4: Keep live-money interpretation out of the ready signal

**Decision**: A ready diagnostic liveness report says broker diagnostics are alive, not that real orders can be submitted.

**Rationale**: Current money-path state is `PREVIEW_ONLY`. Conflating diagnostic health with live-money permission would weaken the safety boundary.

**Alternatives considered**: Include money-path as a required ready gate. Rejected because this candidate is about diagnostics, not capital readiness. Safety invariants and capital-path context are sufficient to prevent overclaiming.

## Decision 5: Completion marker advances to agent-ops frontier

**Decision**: Record `completed_candidate_id: candidate-broker-diagnostic-liveness-contract` and `next_candidate_id: candidate-agent-ops-frontier-map`.

**Rationale**: 브로커 진단 생존성은 체결 품질 frontier의 마지막 열린 후보다. 완료 마커를 남기면 released-work가 같은 후보 반복을 막고 autonomous-work가 다음 거시 미탐색 영역으로 전진한다.

**Alternatives considered**: Loop back to execution-quality frontier. Rejected because all execution-quality frontier entries are released after this candidate closes.
