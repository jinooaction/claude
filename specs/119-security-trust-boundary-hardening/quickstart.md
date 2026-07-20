# Quickstart: Security Trust Boundary Hardening

1. Run focused tests:

   ```bash
   uv run pytest tests/unit/test_deploy_guards.py tests/unit/test_deploy_steps.py tests/unit/test_broker_auth.py tests/unit/test_execution_state.py tests/unit/test_fill_sync.py tests/unit/test_risk_gates.py tests/unit/test_security_workflow_hardening.py -q
   ```

2. Run full validation:

   ```bash
   uv run pytest -q
   uv run ruff check src tests
   git diff --check
   uv run python scripts/check_handoff_facts.py
   uv run python scripts/agent_harness_probe.py --strict
   ```

3. Review generated PR body with:

   ```bash
   uv run python scripts/check_pr_quality_gate.py /tmp/pr-body.md
   ```

4. Operator-side follow-up after merge: the GitHub-held root SSH user/private-key secrets have been removed. Remove the old public key from server `authorized_keys`, then provision a non-root forced-command deploy identity and set fresh `VULTR_SSH_USER`/`VULTR_SSH_PRIVATE_KEY` secrets for that identity.
