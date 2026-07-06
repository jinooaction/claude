# Quickstart: Regime Timeline Coverage Contract

## Focused Tests

```bash
uv run pytest tests/unit/test_regime_timeline_coverage.py tests/integration/test_regime_timeline_coverage_probe.py tests/unit/test_autonomous_work_execution.py
```

## Local Sidecar Replay

```bash
tmpdir="$(mktemp -d)"
mkdir -p "${tmpdir}/automation/public-data" \
  "${tmpdir}/automation/regime-stratify-last-run" \
  "${tmpdir}/automation/pipeline-liveness-last-run" \
  "${tmpdir}/automation/released-work-last-run"
git show origin/automation/public-data:regime_timeline.csv \
  > "${tmpdir}/automation/public-data/regime_timeline.csv"
git show origin/automation/regime-stratify-last-run:LAST_RUN.md \
  > "${tmpdir}/automation/regime-stratify-last-run/LAST_RUN.md"
git show origin/automation/pipeline-liveness-last-run:LAST_RUN.md \
  > "${tmpdir}/automation/pipeline-liveness-last-run/LAST_RUN.md"
git show origin/automation/released-work-last-run:released_work.json \
  > "${tmpdir}/automation/released-work-last-run/released_work.json"
uv run python scripts/regime_timeline_coverage_probe.py \
  --repo-root "${tmpdir}" \
  --format json \
  --now 2026-07-06T13:30:00Z \
  | jq '{overall_status, completed_candidate_id, next_candidate_id, gates:[.quality_gates[] | {key,status}]}'
```

Expected with current sidecars:

- `completed_candidate_id` is `candidate-regime-timeline-coverage-contract`.
- `next_candidate_id` is `candidate-data-evidence-liveness-contract`.
- timeline shape and forward join quality pass.
- overall status is `OBSERVATION_WAIT` because `RISK_OFF` has fewer than 20 joined return days in the current regime-stratify sidecar.
- No broker, order, capital, live strategy, secret, or external collection side effects occur.

## Released-Work Closure

```bash
uv run python scripts/released_work_probe.py --repo-root . --json \
  | jq '[.released_work[] | select(.candidate_id=="candidate-regime-timeline-coverage-contract")]'
```

Expected after tasks are complete:

- released-work includes `candidate-regime-timeline-coverage-contract`.

## Autonomous-Work Advancement

```bash
uv run python scripts/autonomous_work_execution_probe.py --repo-root . --json \
  | jq '.selected_work.candidate_id'
```

Expected after released-work sees the completion marker:

- selected candidate advances to `candidate-data-evidence-liveness-contract` unless a higher-priority repair or regular candidate exists.

## Safety

This feature only reads existing sidecar snapshots and emits a contract report. It must not submit orders, call broker APIs, allocate capital, change live strategy, widen whitelist/caps, touch secrets, modify constitution/kernel files, or run fresh public-data collection.
