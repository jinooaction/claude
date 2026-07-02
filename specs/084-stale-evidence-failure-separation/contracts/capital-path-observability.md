# Contract: Capital Path Observability Issues

## JSON Output

`capital_path_readiness.json` MUST include:

```json
{
  "observability_issues": [
    {
      "issue_id": "released-candidate-echo:candidate-6ee3370e933d",
      "issue_type": "released_candidate_echo",
      "severity": "info",
      "source_key": "released-work",
      "status": "RELEASED",
      "summary_ko": "이미 출시된 후보가 upstream 후보 목록에 남아 있습니다.",
      "next_action_ko": "released-work와 evolution backlog 생산 순서를 확인합니다.",
      "affected_candidate_id": "candidate-6ee3370e933d"
    }
  ]
}
```

## Markdown Output

The report MUST contain a `## 관측 이슈` section between candidate sections and input evidence.

## Manifest Inputs

`scripts/capital_path_readiness_probe.py --manifest` MUST include:

```text
released-work	automation/released-work-last-run	released_work.json
pipeline-liveness	automation/pipeline-liveness-last-run	LAST_RUN.md
```

## Completed Candidate

This feature completes autonomous work candidate `candidate-6ee3370e933d` once merged and handed off.

completed_candidate_id: candidate-6ee3370e933d
