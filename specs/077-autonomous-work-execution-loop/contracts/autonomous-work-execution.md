# 계약: 자율 작업 실행 루프

## Manifest

`scripts/autonomous_work_execution_probe.py --manifest`는 다음 형식으로 입력 sidecar를 출력한다.

```text
<key>\t<branch>\t<filename>
```

## JSON 출력

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-01T09:10:00Z",
  "overall_status": "EXECUTION_READY",
  "selected_work": {
    "packet_id": "work-...",
    "candidate_id": "candidate-...",
    "domain_key": "live_readiness",
    "title_ko": "자본 경로 gate alignment",
    "work_type": "gate_alignment",
    "risk_grade": 2,
    "priority_score": 3597,
    "status": "EXECUTION_READY",
    "reason_ko": "...",
    "next_action_ko": "...",
    "required_inputs": ["automation/capital-path-readiness-last-run:LAST_RUN.md"],
    "safety_boundary": ["no orders", "no capital change"],
    "source_refs": ["automation/capital-path-readiness-last-run:capital_path_readiness.json"]
  },
  "ranked_work": [],
  "suppressed_work": [],
  "evidence_surfaces": [],
  "safety_invariants": []
}
```

## Workflow 안전 계약

워크플로는 다음을 포함하면 안 된다.

- `KIS_`
- `ssh `
- `rebalance-live --mode live`
- `--confirm-live`
- `place-order`
- `submit-order`
- `gh pr create`
- `git push origin main`
