# Research: Macro Candidate Map Regenerator

## Decision: Put the map in autonomous-work execution, not evolution-loop

**Rationale**: The failing operational surface is `selected_work` in the autonomous-work report after released-work closes frontier discovery. Adding the map at the final selection layer lets the system preserve existing pipeline repair, operator approval, blocked, released, and suppressed ordering.

**Alternatives considered**:

- Add only upstream evolution-loop candidates. Rejected because same-push ordering can lag and autonomous-work still needs a closed-queue fallback.
- Add a new workflow. Rejected because the existing sidecar already reports the next Codex work packet and must remain the single selection surface.

## Decision: Regenerator is itself a completed candidate, then domain frontier candidates follow

**Rationale**: The current task implements the ability to regenerate candidates. It should be closed by released-work as `candidate-macro-candidate-map-regenerator`. After that is released, the new logic must emit the highest-priority unreleased map-derived frontier candidate, proving the loop does not stop at its own implementation.

**Alternatives considered**:

- Mark the first map-derived candidate as this spec's completed candidate. Rejected because it would falsely claim the next frontier work was already implemented.
- Never mark the regenerator as released. Rejected because released-work must be the source of truth for completed work.

## Decision: First regenerated domain biases toward investment edge

**Rationale**: Recent autonomous-loop work has mainly improved operating-system quality. The operator's broader goal is measured financial growth, so the first regenerated frontier should point at investment-edge candidate generation while still staying read-only and SDD-gated.

**Alternatives considered**:

- Continue agent-ops candidates. Rejected because it risks an operating-quality local optimum.
- Generate live-money candidates. Rejected because that crosses safety and operator boundaries.

## Decision: JSON and Markdown both expose the map

**Rationale**: Machine-readable JSON supports workflow and regression tests; Markdown supports next-session handoff and operator interpretation.

**Alternatives considered**:

- JSON only. Rejected because the operator and next session read `LAST_RUN.md`.
- Markdown only. Rejected because tests and future tools need stable keys.
