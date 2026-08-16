# Quickstart: Uncertainty-Aware ML Edge Ensemble

```bash
uv run python scripts/ml_edge_ensemble_probe.py --json > /tmp/ml-edge-report.json
uv run python scripts/ml_edge_ensemble_probe.py > /tmp/ml-edge-report.md
```

Expected:

- no order, broker, live config, sentinel, or capital write;
- at least 20 disjoint test folds;
- 10, 25, and 50bp cost scenarios;
- both passive and incumbent trend benchmarks;
- deterministic fingerprints and one explicit verdict.

Focused validation:

```bash
uv run pytest tests/unit/test_ml_edge_ensemble.py tests/integration/test_ml_edge_ensemble_probe.py
uv run ruff check src tests
git diff --check
```
