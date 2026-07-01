# 계약: money-gate-alignment sidecar

## 입력 manifest

`scripts/money_gate_alignment_probe.py --manifest`는 아래 형식으로 입력 sidecar를 출력한다.

```text
<key>\t<branch>\t<filename>
```

필수 키:

- `money-path`
- `capital-path-readiness`
- `edge-autoarm`
- `reassign`
- `rebalance-paper-forward`
- `pipeline-liveness`
- `autonomous-work-execution`
- `kis-smoke`

## JSON 출력

`money_gate_alignment.json`은 다음 최상위 필드를 가진다.

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-01T09:20:00Z",
  "overall_status": "ALIGNED_WAITING",
  "live_money_status": "PREVIEW_ONLY",
  "readiness_state": "ACCUMULATING_EDGE",
  "capital_ladder_stage": "ACCUMULATING_EDGE",
  "blocking_gate": "전진 관측 부족: 14/20",
  "selected_work_candidate": "candidate-fd04772a23c5",
  "next_action_ko": "전진 관측을 계속 누적한다.",
  "gate_surfaces": [],
  "alignment_issues": [],
  "safety_invariants": []
}
```

## Markdown 출력

`LAST_RUN.md`는 사람이 읽는 요약, 이슈 표, 입력 증거 표, 안전 경계, 결정 JSON을 포함한다.

## 안전 계약

- 출력은 보고 전용이다.
- workflow는 브로커, 주문, 라이브 전환, 원격 서버 명령, 외부 비용 명령을 포함하지 않는다.
- 실패해도 기존 돈 경로 게이트 상태를 변경하지 않는다.
