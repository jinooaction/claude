# Quickstart: Paired Forward Edge Gate

1. Run focused tests:

   `uv run pytest tests/unit/test_edge_verdict.py tests/unit/test_forward_gate_calibration.py tests/integration/test_forward_gate_calibration_probe.py`

2. Generate calibration evidence:

   `uv run python scripts/forward_gate_calibration_probe.py --repetitions 5000 --json-out /tmp/forward_gate_calibration.json`

3. Confirm `verdict=CALIBRATED`, paired null PSR 0.95 acceptance at most 0.06, paired null PSR 0.80 acceptance in `[0.17, 0.23]`, and paired planted detection above legacy.

4. Run the full repository gates, merge, and wait for the deployed commit.

5. Dispatch `rebalance-paper-forward.yml`; verify every benchmark-backed verdict reports schema 1.2 and `paired_active_return_psr_v1`.

6. Refresh profit evidence, capital path, KIS no-order smoke, and money path. A corrected pass is only evidence for the existing ladder; it is not an order command.
