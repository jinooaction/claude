# Quickstart: Broad No-Edge Vol-Target Drawdown

## Focused Tests

```bash
uv run pytest tests/unit/test_broad_no_edge_vol_target_drawdown.py tests/integration/test_broad_no_edge_vol_target_drawdown_probe.py -q
```

## Local Sidecar Replay

Prepare a directory with:

- `rebalance-paper-forward.md`
- `regime-stratify.md`
- `execution-quality.md`
- `money-path.md`
- `edge-autoarm.md`
- `released-work.md`
- `pipeline-liveness.md`

Then run:

```bash
uv run python scripts/broad_no_edge_vol_target_drawdown_probe.py --sidecar-dir <dir> --repo-root . --json
```

Expected current status after repo-root override: `CONTRACT_READY`.
