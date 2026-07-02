# 계약: operator-status sidecar

## Manifest

`scripts/operator_status_probe.py --manifest`는 다음 형식으로 입력 sidecar를 출력한다.

```text
<key>\t<branch>\t<filename>
```

필수 입력 키:

- `pipeline-liveness`
- `money-path`
- `capital-path-readiness`
- `money-gate-alignment`
- `autonomous-work-execution`
- `released-work`

## JSON 출력

`operator_status.json`은 다음 최상위 필드를 가진다.

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-02T09:25:00Z",
  "overall_status": "ACTION_REQUIRED",
  "headline_ko": "돈 경로 정렬 루프가 개입 필요 상태입니다.",
  "next_action_ko": "money-gate-alignment sidecar의 이슈 표를 확인한다.",
  "dashboard_url": "https://jinooaction.github.io/claude/status.html",
  "alert_decision": {
    "alert_level": "ACTION_REQUIRED",
    "should_send": true,
    "reason_ko": "개입 필요 표면 1개가 있습니다.",
    "send_status": "NOT_ATTEMPTED",
    "message_ko": "auto-invest 개입 필요..."
  },
  "surfaces": [],
  "dashboard_sections": [],
  "safety_invariants": []
}
```

## Markdown 출력

`LAST_RUN.md`는 다음을 포함한다.

- 종합 판정 표
- 모바일 알림 판정과 전송 결과
- 표면별 상태 표
- 안전 경계
- 결정 JSON

## Workflow 안전 계약

새 workflow는 다음 문자열이나 행동을 포함하면 안 된다.

- `KIS_`
- `ssh `
- `rebalance-live --mode live`
- `--confirm-live`
- `place-order`
- `submit-order`
- `gh pr create`
- `git push origin main`
- `auto-invest deploy`

허용되는 외부 호출은 Telegram Bot API text send 하나뿐이며, `ACTION_REQUIRED` 이상이고 비밀값이 있을 때만 best-effort로 실행한다.
