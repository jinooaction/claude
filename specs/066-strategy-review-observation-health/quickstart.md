# Quickstart: Strategy Review Observation Health

## 1. Run Focused Unit Tests

```bash
uv run pytest tests/unit/test_forward_tournament.py
```

Expected: all observation-health cases pass, including all-premature lag, mixed comparable/premature degradation, and all-comparable lag.

## 2. Run Probe Integration Tests

```bash
uv run pytest tests/integration/test_forward_tournament_probe.py
```

Expected: a current sidecar-shaped seven-track board with `globalfixed` behind but all tracks premature reports `observation_health=OK`.

## 3. Check Lint

```bash
uv run ruff check src tests scripts/forward_tournament_probe.py
```

Expected: no lint failures.

## 4. Interpret the Current Operational State

After deployment and the next scheduled forward tournament run, the reassignment sidecar should no longer say candidate observation quality is degraded merely because `globalfixed` has fewer observations while every track is below 20 observations. It should still hold reassignment because no comparable challenger exists yet.
