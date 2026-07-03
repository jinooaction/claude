# Contract: Evolution Source Diversification

## Released Work Marker

```yaml
completed_candidate_id: candidate-evolution-source-diversification
feature: 089-evolution-source-diversification
risk_grade: 2
safety_boundary:
  - no broker API call
  - no orders
  - no capital allocation
  - no live strategy change
  - no whitelist/caps change
  - no secret read/write
  - no external paid service
```

## Candidate Output Contract

When the static autonomous evolution candidate set is closed after ledger and promotion failure application, `candidate_backlog.json` must include at least one candidate with:

```json
{
  "domain_key": "agent_ops",
  "title_ko": "증거 기반 후보 소스 다변화",
  "breakthrough_type": "operator_leverage",
  "risk_grade": 2,
  "safety_impact": [],
  "status": "new"
}
```

The exact stable `candidate_id` is implementation-derived, but tests must pin it once generated.

## Non-Goals

- No order submission or broker API call.
- No live strategy, capital ladder, whitelist/caps, secret, constitution, or kernel change.
- No new paid data or external service.
