# Contract: Capital Path Readiness Loop

## Manifest Contract

`scripts/capital_path_readiness_probe.py --manifest` must emit:

```text
money-path	automation/money-path-last-run	LAST_RUN.md
edge-autoarm	automation/edge-autoarm-last-run	LAST_RUN.md
reassign	automation/reassign-last-run	LAST_RUN.md
rebalance-paper-forward	automation/rebalance-paper-forward-last-run	LAST_RUN.md
kis-smoke	automation/kis-smoke-last-run	LAST_RUN.md
autonomous-promotion	automation/autonomous-promotion-last-run	promotion_summary.json
evolution-backlog	automation/autonomous-evolution-last-run	candidate_backlog.json
evolution-ledger	automation/autonomous-evolution-last-run	learning_ledger.json
```

## JSON Output Contract

`capital_path_readiness.json` must include:

```json
{
  "schema_version": "1.0",
  "readiness_state": "ACCUMULATING_EDGE",
  "live_money_status": "PREVIEW_ONLY",
  "capital_ladder_stage": "ACCUMULATING_EDGE",
  "blocking_gate": "전진 관측 부족: 13/20",
  "next_action_ko": "기존 전진 관측과 자본 사다리 게이트를 계속 사용한다.",
  "required_existing_gates": ["money-path", "edge-autoarm", "reassign"],
  "priority_candidates": [],
  "suppressed_candidates": []
}
```

## Safety Contract

The workflow and probe must not contain or invoke:

- `KIS_`
- `ssh `
- `ssh -`
- `rebalance-live --mode live`
- `--confirm-live`
- `place-order`
- `submit-order`
- whitelist mutation commands
- caps mutation commands
- live strategy mutation commands

The workflow may fetch automation sidecar branches and publish its own sidecar branch.
