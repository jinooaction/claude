# Quickstart: Independent Options Variance Risk Premium

## Frozen Local Replay

1. Download the four preregistered public source files without changing candidate or gate settings.
2. Run the options-premium probe with the current energy factory JSON and prior family decision JSON files.
3. Confirm exact 16/16 current trials, 752/752 global unique fingerprints, chronology, tail metrics, controls, and adoption audit.
4. Record the first result in `production-result.md` before modifying any requirement.

## Focused Verification

```bash
uv run pytest -q tests/unit/test_options_variance_risk_premium_factory.py tests/integration/test_options_variance_risk_premium_factory_probe.py
uv run ruff check src tests
```

## Full Release Verification

```bash
uv run pytest -q
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

Parse the workflow YAML, run `git diff --check`, validate the PR body, merge only after all
checks pass, and verify the production sidecar and KIS read-only smoke. No step may submit
an option or equity order.

## Expected Safety State

- research-only evidence;
- no KIS secret in the factory workflow;
- no option-chain order construction;
- no PUTW or SPX option whitelist entry;
- no margin, capital, arming, cap, constitution, or kernel change;
- live parity false even if a historical candidate passes.
