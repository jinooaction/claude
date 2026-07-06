# Research: Data Evidence Frontier Map

## Decision: Treat data evidence as a nested map, not a fresh collection job

**Rationale**: The macro candidate map correctly selects `candidate-data-evidence-frontier-map` after investment-edge work is released. If this candidate merely releases and skips ahead, the loop never explains which data input-quality surface should improve next. A nested map keeps the loop evidence-driven while avoiding new external collection or money-path changes.

**Alternatives considered**:

- Run `collect-public-data` directly. Rejected because this feature should generate work packets and must not create fresh external side effects.
- Mark the first data-quality candidate as this spec's completed candidate. Rejected because this spec implements the map and candidate generation, not the later input-quality contract.

## Decision: Use public-data and regime-stratify sidecars as read-only evidence inputs

**Rationale**: The current repository already publishes `automation/public-data` with `LAST_RUN.md`, `summary.json`, `regime.json`, and `regime_timeline.csv`, plus `automation/regime-stratify-last-run:LAST_RUN.md`. These are the exact surfaces named by the selected work packet and can be read without secrets, broker calls, or network collection.

**Alternatives considered**:

- Add new required source branches before the first map exists. Rejected because the current sidecars already expose enough scope to generate the next candidate.
- Use pipeline-liveness alone. Rejected because liveness shows freshness, not data coverage or cross-check scope.

## Decision: First data evidence candidate is public-data input quality contract

**Rationale**: Public data currently has cross-check summaries, regime reports, and a timeline, but autonomous-work does not yet turn those surfaces into an explicit input-quality contract. This is the highest-leverage next candidate because investment-edge experiments depend on trustworthy public/regime context.

**Alternatives considered**:

- Start with execution-quality data. Rejected because execution-quality is already a separate macro frontier.
- Start with agent-ops handoff data. Rejected because agent operations is also a separate macro frontier and recent work already improved that loop.
