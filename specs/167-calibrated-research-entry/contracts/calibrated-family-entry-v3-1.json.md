# Contract: Calibrated Family Entry v3.1

```json
{
  "gate_version": "3.1",
  "program_research_family_count": 17,
  "research_family_audit": [
    {
      "research_family_id": "options-variance-risk-premium",
      "candidate_count": 16,
      "candidate_identity_digest": "sha256:...",
      "status_counts": {"complete": 16}
    }
  ],
  "repository_gate_calibration": {
    "gate_version": "2.0",
    "research_entry_gate_version": "3.1",
    "thresholds": {
      "holdout_psr_min": 0.95,
      "research_entry_pbo_max": 0.25
    },
    "required": {
      "family_false_acceptance_max": 0.01,
      "detection_min": 0.8,
      "program_false_acceptance_budget": 0.2,
      "maximum_research_families": 20
    },
    "family_calibrations": {
      "16": {"research_entry_calibrated": true},
      "64": {"research_entry_calibrated": true}
    }
  },
  "decision": {
    "verdict": "FACTORY_EDGE",
    "research_canary_eligible": true,
    "psr": "0.96",
    "dsr": "0.80",
    "pbo": "0.20"
  }
}
```

## Blocking v3.1 Checks

- all v3 raw-row, selected identity, point-in-time, non-reuse, benchmark parity, live parity, producer gate, and fundability checks
- exact family classification, count, summary, and calibration identity
- selected candidate equals the consumer-recomputed development winner
- selected holdout PSR >= 0.95
- claimed and recomputed PBO match and PBO <= 0.25
- claimed and recomputed DSR match and remain in [0, 1]
- family calibration false acceptance <= 0.01 and target detection >= 0.80 for 16 and 64 candidates
- `family_count * 0.01 <= 0.20`

## Diagnostic-only v3.1 Checks

- DSR >= 0.95
- raw-candidate Bonferroni across all 752 audit rows

## Compatibility

- `gate_version=3.0`: `family-complete-v3-diagnostic`
- `gate_version=2.0`: `family-complete-v2-diagnostic`
- missing/legacy: `legacy-64-diagnostic`
