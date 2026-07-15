# Contract: Operator Report Liveness

## Probe Contract

```bash
uv run python scripts/operator_report_liveness_probe.py \
  --repo-root . \
  --final-report /tmp/final-report.md \
  --released-work /tmp/released_work.json \
  --json-out /tmp/operator_report_liveness.json \
  --summary-out /tmp/operator_report_liveness.md
```

## Required Outputs

- JSON output contains `overall_status`, `completed_candidate_id`, `next_candidate_id`, `evidence_surfaces`, `rule_surface_summary`, `final_report_summary`, `quality_gates`, `released_work_summary`, and `safety_invariants`.
- Markdown output contains:
  - `## 종합 판정`
  - `## 검증 게이트`
  - `## 최종 보고 관찰`
  - `## 규칙 표면`
  - `## 입력 증거`
  - `## 안전 경계`
  - fenced 결정 JSON

## PASS Contract

The final report observation passes only when it includes all required meaning categories:

1. One-sentence operator-state conclusion before evidence-only details.
2. What was created or fixed.
3. Meaning for money path, automation, safety boundary, or next-session behavior.
4. Verification evidence and what it proves.
5. Remaining risk or next observation point.
6. Evidence identifiers such as PR number, commit hash, tests, sidecar runs, or deploy runs are not the only conclusion.

## WAIT Contract

- Missing final-report text is `WAIT`.
- Released-work that has not yet consumed `candidate-operator-report-liveness-contract` is `WAIT`.

## FAIL Contract

- Missing required rule surfaces is `FAIL`.
- Malformed released-work JSON is `FAIL`.
- A final report that lists only PR/hash/test evidence without operational meaning is `FAIL`.

## Forbidden Effects

- No network or GitHub API call.
- No broker API call.
- No order or cancellation.
- No capital allocation.
- No live strategy or sentinel change.
- No whitelist/caps change.
- No secret read/write.
- No constitution or kernel manifest modification.
- No repository mutation from the report module.
