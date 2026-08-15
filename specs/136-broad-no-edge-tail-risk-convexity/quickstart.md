# Quickstart: Broad No-Edge Tail-Risk Convexity

```bash
uv run pytest tests/unit/test_broad_no_edge_tail_risk_convexity.py \
  tests/integration/test_broad_no_edge_tail_risk_convexity_probe.py
```

Replay current sidecars:

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/broad_no_edge_tail_risk_convexity_probe.py --manifest |
while IFS=$'\t' read -r key branch file; do
  git show "origin/${branch}:${file}" > "${tmpdir}/${key}.md"
done
uv run python scripts/broad_no_edge_tail_risk_convexity_probe.py \
  --sidecar-dir "$tmpdir" \
  --repo-root . \
  --json
```

Expected local replay status after this spec exists: `CONTRACT_READY`.
