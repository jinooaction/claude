# Quickstart: Candidate Implementation Factory

## Local smoke

```bash
mkdir -p /tmp/candidate-factory
git fetch origin automation/autonomous-evolution-last-run automation/autonomous-promotion-last-run
git show origin/automation/autonomous-evolution-last-run:candidate_backlog.json \
  > /tmp/candidate-factory/candidate_backlog.json
git show origin/automation/autonomous-promotion-last-run:promotion_summary.json \
  > /tmp/candidate-factory/promotion_summary.json

uv run python scripts/candidate_factory_probe.py \
  --candidate-backlog /tmp/candidate-factory/candidate_backlog.json \
  --promotion-summary /tmp/candidate-factory/promotion_summary.json \
  --summary-out /tmp/candidate-factory/LAST_RUN.md \
  --json-out /tmp/candidate-factory/candidate_factory.json \
  --enriched-backlog-out /tmp/candidate-factory/candidate_backlog.enriched.json \
  --package-plan-out /tmp/candidate-factory/candidate_packages.json \
  --run-id local
```

## Promotion scan with enriched backlog

```bash
mkdir -p /tmp/promotion_evidence
cp /tmp/candidate-factory/candidate_backlog.enriched.json \
  /tmp/promotion_evidence/candidate_backlog.json
uv run python scripts/promotion_loop_probe.py \
  --evidence-dir /tmp/promotion_evidence \
  --json-out /tmp/promotion_summary.json
```

## Verification

```bash
uv run pytest tests/unit/test_candidate_factory.py tests/integration/test_candidate_factory_probe.py
uv run ruff check src tests scripts/candidate_factory_probe.py
```
