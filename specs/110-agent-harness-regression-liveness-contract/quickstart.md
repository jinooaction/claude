# Quickstart: Agent Harness Regression Liveness Contract

## 1. Capture current strict harness output

```bash
uv run python scripts/agent_harness_probe.py --strict > /tmp/agent-harness-strict.txt
```

## 2. Run the pre-release probe

```bash
uv run python scripts/agent_harness_regression_liveness_probe.py \
  --repo-root . \
  --strict-output /tmp/agent-harness-strict.txt \
  --format markdown
```

Expected before released-work sidecar consumes this feature:

- static harness source gates: `PASS`
- suite coverage gate: `PASS`
- strict observation gate: `PASS`
- released-work completion gate: `WAIT`
- overall: `OBSERVATION_WAIT`

## 3. Replay released-work completion locally

```bash
python - <<'PY'
import json
from pathlib import Path

Path("/tmp/agent-harness-released.json").write_text(json.dumps({
    "released_work": [
        {
            "candidate_id": "candidate-agent-harness-regression-liveness-contract",
            "status": "released",
        }
    ]
}), encoding="utf-8")
PY

uv run python scripts/agent_harness_regression_liveness_probe.py \
  --repo-root . \
  --strict-output /tmp/agent-harness-strict.txt \
  --released-work /tmp/agent-harness-released.json \
  --format json
```

Expected:

- `overall_status=CONTRACT_READY`
- `completed_candidate_id=candidate-agent-harness-regression-liveness-contract`
- `next_candidate_id=candidate-operator-report-liveness-contract`

## 4. Replay autonomous-work transition

Use focused tests:

```bash
uv run pytest tests/unit/test_autonomous_work_execution.py -k "agent_harness"
```

Expected: released agent harness liveness advances to `candidate-operator-report-liveness-contract`.

## 5. Full validation

```bash
uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
```
