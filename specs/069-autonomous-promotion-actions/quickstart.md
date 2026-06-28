# Quickstart: Autonomous Promotion Actions

## 로컬 action 루프 실행

```bash
uv run python scripts/promotion_action_probe.py \
  --promotion-summary tests/fixtures/promotion_actions/fresh/promotion_summary.json \
  --forward-registry tests/fixtures/promotion_actions/fresh/promotion-forward-registry.json \
  --canary-submissions tests/fixtures/promotion_actions/fresh/promotion-canary-submissions.json \
  --summary-out /tmp/promotion-actions-LAST_RUN.md \
  --json-out /tmp/promotion-actions.json \
  --forward-registry-out /tmp/promotion-forward-registry.next.json \
  --canary-submissions-out /tmp/promotion-canary-submissions.next.json \
  --now 2026-06-29T00:00:00Z \
  --commit local
```

## CLI 실행

```bash
uv run auto-invest promotion-actions \
  --promotion-summary tests/fixtures/promotion_actions/fresh/promotion_summary.json \
  --forward-registry tests/fixtures/promotion_actions/fresh/promotion-forward-registry.json \
  --canary-submissions tests/fixtures/promotion_actions/fresh/promotion-canary-submissions.json \
  --format json
```

## 검증

```bash
uv run pytest \
  tests/unit/test_promotion_actions.py \
  tests/integration/test_promotion_action_probe.py \
  tests/unit/test_pipeline_liveness.py \
  tests/unit/test_safety_command_registry.py

uv run ruff check \
  src/auto_invest/analytics/promotion_actions.py \
  scripts/promotion_action_probe.py \
  tests/unit/test_promotion_actions.py \
  tests/integration/test_promotion_action_probe.py
```

## 사이드카 확인

```bash
git fetch origin automation/autonomous-promotion-actions-last-run || true
git show origin/automation/autonomous-promotion-actions-last-run:LAST_RUN.md

git fetch origin automation/promotion-forward-last-run || true
git show origin/automation/promotion-forward-last-run:LAST_RUN.md

git fetch origin automation/promotion-canary-last-run || true
git show origin/automation/promotion-canary-last-run:LAST_RUN.md
```
