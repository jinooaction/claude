# Data Model: Stale Evidence Failure Separation

## ReadinessObservabilityIssue

| Field | Type | Description |
|------|------|-------------|
| `issue_id` | string | Deterministic id such as `released-candidate-echo:candidate-id` or `pipeline-liveness:key`. |
| `issue_type` | string | `released_candidate_echo`, `pipeline_liveness`, or `malformed_evidence`. |
| `severity` | string | `info`, `warning`, or `critical`. Critical reflects liveness severity only; it still does not submit orders. |
| `source_key` | string | Evidence key that produced the issue. |
| `status` | string | Raw status such as `RELEASED`, `STALE`, `MISSING`, or `MALFORMED`. |
| `summary_ko` | string | Korean one-line explanation. |
| `next_action_ko` | string | Korean read-only follow-up. |
| `affected_candidate_id` | string or null | Candidate id when the issue is about a released candidate echo. |

## CapitalPathReadinessReport additions

| Field | Type | Description |
|------|------|-------------|
| `observability_issues` | list[ReadinessObservabilityIssue] | Non-trading evidence-quality issues shown separately from candidates. |

## Existing entities unchanged

- `ReadinessCandidate` remains the representation for actionable or suppressed candidates.
- `ReadinessEvidenceSurface` remains the parse/presence summary for each consumed sidecar.
- Money-path state fields remain unchanged by observability issues.
