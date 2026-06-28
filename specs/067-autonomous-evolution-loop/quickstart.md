# Quickstart: Autonomous Evolution Loop

This quickstart describes the intended verification path for the first implementation slice.

## 1. Collect Evidence Fixtures

Create a temporary evidence directory with representative current surfaces:

```bash
tmpdir="$(mktemp -d)"
uv run python scripts/evolution_loop_probe.py --manifest | while IFS=$'\t' read -r key branch file; do
  git show "origin/${branch}:${file}" > "${tmpdir}/${key}.md" 2>/dev/null || true
done
```

The first slice must also support tests that use checked-in fixtures instead of live sidecars.

## 2. Run a Read-Only Scan

```bash
uv run python scripts/evolution_loop_probe.py \
  --evidence-dir "${tmpdir}" \
  --json > /tmp/evolution_summary.json
```

Expected properties:

- The command exits `0`.
- The output includes top breakthrough candidates, stale evidence, safe high-leverage work, evidence-dependency items, and operator-review items.
- No broker secrets are required.
- No trading configuration files are modified.

## 3. Verify Safety Classification

Run tests that inject candidates requiring:

- broker orders
- capital increase
- whitelist expansion
- cap relaxation
- live strategy swap
- secret handling change
- paid external service use

Expected result: all are classified as safety-boundary or operator-review items, not automatic actions.

## 4. Publish Sidecar in Workflow

After core tests pass, run the planned workflow manually:

```bash
gh workflow run autonomous-evolution-loop.yml
```

Expected result:

- `automation/autonomous-evolution-last-run` is force-pushed with `LAST_RUN.md`, `evolution_summary.json`, `learning_ledger.json`, and `candidate_backlog.json`.
- `LAST_RUN.md` states that orders, capital, whitelist, caps, and live strategy were unchanged.

## 5. Liveness Integration

Run:

```bash
uv run python scripts/pipeline_liveness_probe.py --manifest
uv run python scripts/pipeline_liveness_probe.py --sidecar-dir <fixtures> --json
```

Expected result: the autonomous evolution sidecar appears in the liveness registry as a non-money-path reporting loop. Its failure should degrade visibility, not move money.
