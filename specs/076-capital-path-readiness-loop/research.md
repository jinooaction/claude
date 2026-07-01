# Research: Capital Path Readiness Loop

## Decision: Build a new read-only analytics module

**Rationale**: `money_path.py` already has a narrow responsibility: first-capital path and live money state. The requested loop needs to combine money-path with reassign, KIS smoke, promotion, evolution backlog, and learning ledger. A new module keeps responsibilities clear and avoids destabilizing the money-path safety surface.

**Alternatives considered**: Extending `money_path.py` directly would reduce files but mix first-capital ETA logic with cross-loop candidate routing.

## Decision: Use sidecar JSON/Markdown only

**Rationale**: The loop must not call broker, KIS, SSH, order, capital, or live configuration paths. Existing sidecars already provide enough information for readiness classification.

**Alternatives considered**: Recomputing forward verdicts or broker state would be fresher but would cross safety and external-effect boundaries.

## Decision: Publish a dedicated automation sidecar

**Rationale**: A durable `automation/capital-path-readiness-last-run` sidecar lets future sessions and loops consume the same conclusion without redoing cross-surface reasoning.

**Alternatives considered**: Embedding this in autonomous evolution would make the candidate loop heavier and hide a money-path-specific state surface.

## Decision: Register the loop in pipeline liveness as noncritical at launch

**Rationale**: Staleness should be visible, but direct money safety is still enforced by money-path, edge-autoarm, live canary, KIS smoke, and reassign gates.

**Alternatives considered**: Marking it critical immediately could create noisy false failures before the sidecar has one successful scheduled run.
