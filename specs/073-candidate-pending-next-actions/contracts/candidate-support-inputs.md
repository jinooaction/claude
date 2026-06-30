# Contract: Candidate Support Inputs

## Pipeline liveness sidecars

Producer: existing automation sidecar branches listed by:

```bash
uv run python scripts/pipeline_liveness_probe.py --manifest
```

Consumer path:

```text
/tmp/candidate_result_sidecars/{manifest_key}.md
```

Required command shape:

```bash
uv run python scripts/pipeline_liveness_probe.py --sidecar-dir /tmp/candidate_result_sidecars --strict --json
```

## Public data snapshot

Producer: `origin/automation/public-data`

Consumer path:

```text
/tmp/candidate_result_public_data
```

Required command shape:

```bash
uv run auto-invest macro-regime --data-dir /tmp/candidate_result_public_data --json
```

## Safety contract

Support input staging may read Git sidecar branches and write temporary files under `/tmp`. It must not call broker APIs, place orders, alter capital allocation, edit whitelist/caps, write sentinels, change live strategy configuration, or write secrets.
