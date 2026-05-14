# Contract — `canary-run.json`

**Author**: spec 007 (this PR)
**Path on disk**: `data/canary/<canary_run_id>/canary-run.json`
**Producer**: `auto_invest.canary.report.write_report`
**Consumers**:
- Operator forensic readers (humans).
- Future spec 005 autonomous tuner (machine-readable summary of canary outcomes).
- Future spec 006 deploy runner (consults audit log only; does NOT read this file — but may surface its path in error messages).

## Schema (pydantic v2; serialized via `model_dump_json(indent=2, sort_keys=True)`)

```json
{
  "canary_run_id": "8d3e9c0a-...",            // UUID4
  "candidate_rev": "abcdef0123456789...",     // SHA-40
  "baseline_rev": "fedcba9876543210...",      // SHA-40
  "tier": "L2",                                // "L2" | "L3"
  "window_trading_days": 30,
  "window_start_date": "2026-03-31",
  "window_end_date": "2026-05-13",
  "started_at": "2026-05-14T08:30:00.000Z",
  "finished_at": "2026-05-14T08:42:17.412Z",  // null if outcome == "in_progress"
  "outcome": "passed",                         // "passed" | "failed" | "in_progress"
  "failing_metrics": [],                       // subset of MetricResult.id when outcome == "failed"
  "kernel_touches": [
    {
      "group": "K4",
      "files": ["src/auto_invest/persistence/audit.py"]
    }
  ],
  "metrics": {
    "pnl_drawdown_pct": {
      "observed_value": 1.83,
      "band_upper": 3.0,
      "band_must_equal": null,
      "inside_band": true,
      "source": "window_replay"
    },
    "risk_gate_violations": {
      "observed_value": 0,
      "band_upper": null,
      "band_must_equal": 0,
      "inside_band": true,
      "source": "synthetic_shock"
    },
    "audit_integrity_failures": {
      "observed_value": 0,
      "band_upper": null,
      "band_must_equal": 0,
      "inside_band": true,
      "source": "window_replay"
    },
    "latency_p95_regression_pct": {
      "observed_value": 4.2,
      "band_upper": 20.0,
      "band_must_equal": null,
      "inside_band": true,
      "source": "window_replay"
    },
    "llm_cost_regression_pct": {
      "observed_value": -1.7,
      "band_upper": 10.0,
      "band_must_equal": null,
      "inside_band": true,
      "source": "window_replay"
    }
  },
  "seed_bundle": {
    "hypothesis_database_seed": 1234567890,
    "hypothesis_iterations": 10000,
    "synthetic_shock_dates": ["2020-03-12", "2020-04-20", "2024-08-05", "2026-03-20"],
    "quarterly_opex_resolved_for": "2026-05-14"
  }
}
```

## Field-level contract

- `canary_run_id` — UUID4, stringified; matches the directory name on disk.
- `candidate_rev` / `baseline_rev` — 40-character lowercase hex SHA. Symbolic refs are resolved at canary start and NOT preserved here (the resolved SHA is the reproducibility key).
- `tier` — `L2` or `L3` only. v1 rejects all other values at CLI parse time.
- `window_trading_days` — integer ≥ 30 (L2 minimum per FR-C02) or ≥ 45 (L3 minimum).
- `window_start_date` / `window_end_date` — ISO 8601 dates (YYYY-MM-DD); both are trading days on the XNYS calendar (no weekend / holiday endpoints).
- `started_at` / `finished_at` — UTC ISO 8601 with millisecond precision; both end with `Z`. `finished_at` is `null` iff `outcome == "in_progress"` (only seen on crashed runs).
- `outcome` — terminal `passed` or `failed`; transient `in_progress` only for crash forensics. The audit-log row is the SOURCE OF TRUTH for the terminal decision; this JSON is a forensic snapshot.
- `failing_metrics` — list of metric ids (subset of `{"pnl_drawdown_pct", "risk_gate_violations", "audit_integrity_failures", "latency_p95_regression_pct", "llm_cost_regression_pct"}`). Empty iff `outcome == "passed"`.
- `kernel_touches` — empty list if the candidate diff against baseline does not intersect `kernel.toml`. Non-empty lists carry one entry per touched group; `files` is the full path list within that group.
- `metrics.<id>` — one `MetricResult` per metric. `inside_band` is the AND of `(observed_value <= band_upper)` and `(observed_value == band_must_equal)` for whichever constraint applies (exactly one is non-null per metric).
- `seed_bundle.hypothesis_database_seed` — top-level seed; reproducibility key for the fuzz pass.
- `seed_bundle.synthetic_shock_dates` — resolved at canary start (per R-C3); recording them preserves SC-C04 across operator amendments to `config/synthetic_shocks.toml`.

## Byte-identicality (SC-C04)

For two invocations with the same `(candidate_rev, baseline_rev, tier, window_trading_days, window_start_date, hypothesis_database_seed, history_dir, bands_toml, shocks_toml)`:

- All fields EXCEPT `canary_run_id`, `started_at`, and `finished_at` MUST be byte-identical.
- Floats MUST be serialised via `model_dump_json` (not `json.dumps` on `model_dump()`) — pydantic v2 uses canonical IEEE 754 repr; raw `json.dumps` is locale-sensitive on some platforms.
- `kernel_touches[].files` is sorted lexicographically.
- `failing_metrics` is sorted lexicographically.
- Map key order is forced by `sort_keys=True`.

Verified by `tests/integration/test_canary_reproducibility.py`.

## Spec 006 integration (forward contract)

Spec 006's future deploy runner reads `audit_log` (not this file) to determine deploy eligibility:

```sql
SELECT payload FROM audit_log
WHERE event_type = 'CANARY_PASSED'
  AND json_extract(payload, '$.candidate_rev') = ?
ORDER BY ts_utc DESC
LIMIT 1;
```

If the query returns zero rows, the deploy is refused with `DEPLOY_BLOCKED_NO_CANARY` (a new audit event type spec 006 will add when its runner ships). Spec 007 does NOT add `DEPLOY_BLOCKED_NO_CANARY` — that belongs to spec 006.

The `canary-run.json.artefact_path` value emitted in `CANARY_PASSED.payload.artefact_path` lets spec 006 reference the forensic artefact in its own deploy-decision audit row if it wants to.
