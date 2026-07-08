# Contract: Agent Ops Frontier Map

## Scope

The autonomous-work execution report must expose a deterministic operating-system frontier map and use released-work to advance from `candidate-agent-ops-frontier-map` to the first unreleased map-derived operating-system candidate.

## JSON Contract

`build_autonomous_work_execution(...).to_dict()` MUST include:

```json
{
  "agent_ops_frontier_map": [
    {
      "frontier_key": "handoff_truth_liveness",
      "label_ko": "HANDOFF 사실성 생존성",
      "coverage_status": "open",
      "priority_score": 2150,
      "recommended_candidate_id": "candidate-handoff-truth-liveness-contract",
      "title_ko": "HANDOFF 사실성 생존성 계약",
      "reason_ko": "...",
      "next_action_ko": "...",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "HANDOFF.md",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/workflows/pr-quality-gate.yml"
      ]
    }
  ]
}
```

The map MUST include at least:

- `handoff_truth_liveness` -> `candidate-handoff-truth-liveness-contract`
- `pr_merge_evidence_liveness` -> `candidate-pr-merge-evidence-liveness-contract`
- `worktree_concurrency_liveness` -> `candidate-worktree-concurrency-liveness-contract`

## Selection Contract

- If `candidate-agent-ops-frontier-map` is not in released-work, it remains the selected work packet after execution-quality frontier completion.
- If `candidate-agent-ops-frontier-map` is in released-work, selected work advances to the highest-priority unreleased agent-ops frontier entry.
- Released agent-ops frontier entries MUST be skipped.
- Repair, regular execution, operator approval, blocked, released, and suppressed priority ordering MUST remain unchanged.

## Markdown Contract

Markdown output MUST include:

```markdown
## 운영 체계 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
```

## Safety Contract

The feature is read-only and must not:

- call broker APIs
- submit or retry orders
- allocate capital
- change live strategy
- widen whitelist/caps
- read or write secrets
- modify constitution or kernel files
- run fresh external collection
- invoke paid external services

## Released-Work Marker

The feature spec MUST include:

```text
completed_candidate_id: candidate-agent-ops-frontier-map
next_candidate_id: candidate-handoff-truth-liveness-contract
```
