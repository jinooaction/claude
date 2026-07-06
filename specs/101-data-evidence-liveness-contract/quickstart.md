# Quickstart: Data Evidence Liveness Contract

## Local sidecar replay

```bash
uv run python scripts/data_evidence_liveness_probe.py \
  --repo-root . \
  --format markdown \
  --summary-out /tmp/data_evidence_liveness_LAST_RUN.md \
  --json-out /tmp/data_evidence_liveness.json
```

Expected result with current healthy data sidecars:

- `overall_status`: `CONTRACT_READY`
- `completed_candidate_id`: `candidate-data-evidence-liveness-contract`
- `next_candidate_id`: `candidate-execution-quality-frontier-map`
- `data_liveness_status` gate: `PASS`
- `source_timestamp_consistency` gate: `PASS`

## Deterministic manifest replay

```bash
cat >/tmp/data-evidence-liveness-manifest.tsv <<'EOF'
public-data-last-run	automation/public-data	LAST_RUN.md
public-data-summary	automation/public-data	summary.json
public-data-regime	automation/public-data	regime.json
public-data-regime-timeline	automation/public-data	regime_timeline.csv
regime-stratify	automation/regime-stratify-last-run	LAST_RUN.md
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
released-work	automation/released-work-last-run	released_work.json
capital-path-readiness	automation/capital-path-readiness-last-run	capital_path_readiness.json
EOF

uv run python scripts/data_evidence_liveness_probe.py \
  --repo-root . \
  --manifest /tmp/data-evidence-liveness-manifest.tsv \
  --format json \
  --now 2026-07-07T00:00:00Z
```

## Required validation

```bash
uv run pytest tests/unit/test_data_evidence_liveness.py \
  tests/integration/test_data_evidence_liveness_probe.py \
  tests/unit/test_autonomous_work_execution.py

uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md
```
