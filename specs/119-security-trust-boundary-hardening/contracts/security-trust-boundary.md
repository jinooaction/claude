# Contract: Security Trust Boundary Hardening

## Workflow Contract

- Every third-party Action reference must be a full commit SHA.
- Every SSH command must use strict host-key checking and a configured known-host file.
- Every workflow using `VULTR_SSH_USER` must fail if the value is `root`.
- Remote numeric workflow inputs must be validated before interpolation.

## Deployment Contract

- Candidate deployment requires exact local and remote revision agreement where the workflow provides an expected SHA.
- Canary promotion requires a recent `CANARY_PASSED` row whose candidate and ruleset hashes both match.
- Deploy lock acquisition must be atomic and process-bound.
- Server SSH repair must provision a non-root deploy user with an
  `authorized_keys` forced command, root-owned gateway commands, and
  `visudo`-validated sudoers limited to deploy sync/start/journal actions.
- Deploy and operator setup verification workflows must call fixed gateway
  commands instead of sending arbitrary remote shell scripts.

## Trading Safety Contract

- Stale BUY intent/submitting states block new BUY exposure.
- Unknown broker recovery must prefer exact evidence and mark weak or ambiguous matches unresolved.
- Verified reduce-only sells may pass normal halt/per-trade-cap gates; oversells must fail.
- Missing marks for held positions block new BUY exposure.

## Evidence Contract

- Public sidecar commits keep enough evidence to prove the workflow ran but redact account-scale, token, order, and server-sensitive data.
