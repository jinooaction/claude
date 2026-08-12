# Research: Broad NO_EDGE Data Gap Audit

## Decision: Treat the audit as read-only classification, not fresh data collection

**Rationale**: The selected work packet asks to read `public-data` summary, `regime.json`, and `regime_timeline.csv`. Fetching live public sources would add external effects and make results non-reproducible across sessions.

**Alternatives considered**: Re-running public-data collection was rejected because this candidate is an audit of existing evidence, not a data collection repair.

## Decision: Classify data gaps without automatically invalidating NO_EDGE

**Rationale**: Current evidence has a clear CPI/inflation gap, but regime labels and stratified joins still exist. The correct outcome is to separate "interpretation limited" from "NO_EDGE verdict invalid."

**Alternatives considered**: Failing the entire report on any missing public-data item was rejected because it would hide useful treasury, VIX, Sahm, timeline, and forward evidence.

## Decision: Use deterministic impact levels

**Rationale**: The report needs stable machine-readable output. Impact levels are `LOW`, `MEDIUM`, `HIGH`, and `UNKNOWN`, based on whether gaps affect auxiliary interpretation, canonical labels, or critical sidecar parseability.

**Alternatives considered**: Free-form prose-only diagnosis was rejected because autonomous-work and PR verification need stable fields.

## Decision: Complete the broad no-edge sequence with a released-work marker

**Rationale**: `candidate-broad-no-edge-data-gap-audit` is the fourth broad no-edge child. Once complete, broad no-edge frontier entries should all be released and the loop should not select the same child again.

**Alternatives considered**: Leaving the candidate open after report generation was rejected because it would cause repeated work in later sessions.
