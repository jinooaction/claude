# Research: Broad Validation Failure Frontier

## Decision: Add a nested frontier map after the validation-failure parent

**Rationale**: The current sidecar chain can correctly synthesize `candidate-broad-frontier-expansion-validation-failures-22f38b8629eb`, but after that exact parent is released the same evidence can otherwise collapse to passive waiting. A nested map preserves progress by turning the same failure fingerprint into concrete no-live work.

**Alternatives considered**:

- Wait for fresh sidecars: rejected because the user explicitly called out the repeated narrow loop.
- Force rerun of blocked packages: rejected because the package evidence says the factory already blocked them, and blind rerun does not improve diagnosis.
- Open live trading or lower edge gates: rejected because this is a risk grade 4 money-path action and current evidence still says `PREVIEW_ONLY` / `NO_EDGE_YET`.

## Decision: Use four first frontier entries

**Rationale**: The current blockers include strategy and portfolio backtests with the same `execution_failed` diagnosis. Four entries cover the practical failure dimensions without overfitting: command replay, data readiness, package-kind expansion, and promotion recheck.

**Alternatives considered**:

- One generic "inspect failure" candidate: rejected because it would keep the scope too narrow.
- Separate one candidate per package id: rejected because it would duplicate the same diagnosis and ignore common root causes.

## Decision: Keep all work no-live and read-only

**Rationale**: The value is faster evidence production, not bypassing the safety system. The emitted packets must carry blocked package refs and safety boundaries while leaving orders, capital, live config, broker calls, secrets, whitelist/caps, constitution, and kernel untouched.

**Alternatives considered**:

- Auto-arm live after broader review: rejected because no edge is confirmed and the user did not give a concrete grade 4 approval.
