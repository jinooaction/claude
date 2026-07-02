# Contract: 레짐·성과 후보 점수화

## Probe manifest

`scripts/evolution_loop_probe.py --manifest` must include:

```text
promote-readiness	automation/promote-readiness-last-run	LAST_RUN.md
```

## Candidate backlog JSON

The analysis candidate should expose the performance evidence through the existing candidate contract:

```json
{
  "candidate_id": "candidate-e481b0309206",
  "domain_key": "analysis",
  "title_ko": "레짐·성과 분석을 후보 점수화 입력으로 승격",
  "evidence_refs": [
    "regime-stratify",
    "public-data",
    "promote-readiness"
  ],
  "evidence_dependency": "none",
  "status": "new"
}
```

When `promote-readiness` is stale, missing, malformed, or setup-error-like, the same candidate must remain visible but evidence-dependent:

```json
{
  "candidate_id": "candidate-e481b0309206",
  "evidence_dependency": "sidecar_freshness",
  "status": "evidence_dependent"
}
```

## Safety contract

This feature must not add any of the following to the autonomous evolution workflow:

- broker API calls
- KIS secrets
- SSH commands
- order submission
- capital allocation
- live strategy change
- whitelist/caps change
- PR creation or merge
