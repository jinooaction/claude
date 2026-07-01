# Contract: Strategy Failure Learning

## Evidence Manifest

`scripts/evolution_loop_probe.py --manifest` must include:

```text
promotion-summary	automation/autonomous-promotion-last-run	promotion_summary.json
```

The workflow stores this file under the evidence directory using the key name. The probe treats missing or malformed content as no external promotion failures.

## Promotion Summary Input

Minimal supported shape:

```json
{
  "schema_version": "1.0",
  "run_id": "28504209238",
  "assessments": [
    {
      "candidate_id": "candidate-1ed634d8bf6d",
      "stage": "DISCARD",
      "allowed_next_action": "검증 실패 후보를 승격하지 않고 재설계 또는 학습 장부 후보로 보낸다.",
      "blocked_reason_ko": "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.",
      "candidate": {
        "candidate_id": "candidate-1ed634d8bf6d",
        "title_ko": "micro GTAA 의도 손익 재검토와 대체 전략 연구"
      }
    }
  ]
}
```

## Learning Ledger Output

For each `DISCARD` assessment, `learning_ledger.json` must include:

```json
{
  "candidate_id": "candidate-1ed634d8bf6d",
  "decision": "rejected",
  "reason_ko": "기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.",
  "evidence_package_id": "autonomous-promotion:28504209238",
  "next_recheck_condition": null
}
```

## Safety Contract

This feature must not add any of these strings to `.github/workflows/autonomous-evolution-loop.yml`:

- `KIS_`
- `ssh `
- `ssh -`
- `rebalance-live`
- `--mode live`
- `--confirm-live`
- `whitelist`
- `caps`
