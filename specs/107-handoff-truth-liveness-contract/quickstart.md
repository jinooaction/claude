# Quickstart: HANDOFF Truth Liveness Contract

## 1. Probe current checkout

```bash
uv run python scripts/handoff_truth_liveness_probe.py --repo-root . --format json
```

Expected: `overall_status` is `CONTRACT_READY` when `scripts/check_handoff_facts.py` is OK.

## 2. Write local report artifacts

```bash
tmpdir=$(mktemp -d)
uv run python scripts/handoff_truth_liveness_probe.py \
  --repo-root . \
  --json-out "$tmpdir/handoff_truth_liveness.json" \
  --summary-out "$tmpdir/HANDOFF_TRUTH_LIVENESS.md"
```

Expected: both files exist and include `candidate-handoff-truth-liveness-contract` and `candidate-pr-merge-evidence-liveness-contract`.

## 3. Run focused tests

```bash
uv run pytest tests/unit/test_handoff_truth_liveness.py tests/unit/test_autonomous_work_execution.py -q
```

Expected: HANDOFF truth gates and autonomous-work next-candidate transition pass.

## 4. Replay completion transition

```bash
tmpdir=$(mktemp -d)
uv run python scripts/autonomous_work_execution_probe.py \
  --evidence-dir "$tmpdir" \
  --repo-root . \
  --json \
  --now 2026-07-08T03:00:00Z \
  --run-id local-107 \
  --commit "$(git rev-parse --short HEAD)"
```

Expected after this spec's tasks are complete: released-work sees `candidate-handoff-truth-liveness-contract`, and selected work advances to `candidate-pr-merge-evidence-liveness-contract`.

## 5. Full completion gates

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
