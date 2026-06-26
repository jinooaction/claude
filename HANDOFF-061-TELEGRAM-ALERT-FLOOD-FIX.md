# HANDOFF 061 — Telegram 알림 폭주 방지와 KIS 진단 보강 (2026-06-26 KST)

main 베이스라인: `7195c48`(PR #388). 운영자가 "텔레그램 메시지가 9천개가 넘게 쌓였다"고
보고했고, 조사 결과 GitHub Actions 반복 주문이 아니라 서버의
`auto-invest-telegram-alerts.service`가 오래된 audit cursor 또는 반복 `ERROR` row를 계속 따라잡는
경로가 유력했다. 같은 조사에서 최근 KIS 주문 거부가 `KeyError('output')`로만 남아 실제 KIS
`rt_cd/msg_cd/msg1` 진단을 잃는 문제도 확인했다.

## 무엇이 바뀌었나

- `src/auto_invest/notifications/audit_tail.py`: state file이 이미 있지만 오래된 seq를 가리키는
  경우 기본 최신 25개만 catch-up한다.
- 동일한 `ERROR` 이벤트는 기본 3600초 cooldown 안에서 재전송하지 않는다. 억제된 row도 cursor는
  전진해 같은 오류가 무한히 쌓이지 않는다.
- `auto-invest telegram-alerts`에 `--max-catchup-alerts`와 `--error-cooldown-seconds`를 추가했다.
  음수 catch-up 상한은 제한 해제, cooldown 0은 반복 오류 억제 해제다.
- `src/auto_invest/broker/diagnostics.py`: HTTP 오류뿐 아니라 HTTP 200 오류 본문도 같은 마스킹
  진단 구조로 보존하는 `diagnostics_from_response`를 추가했다.
- `src/auto_invest/broker/overseas.py`: KIS 주문 응답이 HTTP 200이어도 `rt_cd` 실패 또는
  `output.ODNO` 누락이면 성공으로 보지 않고 `KisOrderError`와 진단을 남긴다.
- `.github/workflows/manage-telegram-alerts.yml`: 운영자가 로컬 SSH 없이도 GitHub Actions에서
  `auto-invest-telegram-alerts.service`만 `status/disable/restart/enable` 할 수 있게 했다.
- `specs/059-kis-order-diagnostics/`, `specs/060-telegram-order-alerts/`, `deploy/README.md`에
  변경된 요구사항과 운영 경로를 기록했다.

## 현재 운영 상태

- PR #388은 merge 방식으로 main에 머지됐다.
- `Deploy on merge to main` run `28212963179`가 `7195c48`에서 성공했다.
- KIS smoke run `28212963184`가 `7195c48`에서 성공했다. sidecar 기준 `secrets_present=true`,
  `key_valid=true`, `smoke_state=success`, `smoke_exit=0`.
- `Manage Telegram alerts on server` run `28212999028`로
  `auto-invest-telegram-alerts.service action=restart`를 실행했고 성공했다.
- 재시작 약 50초 뒤 `status` run `28213025727`에서 서비스는 `enabled`/`active`였고,
  journal의 최신 50줄에는 재시작 이후 새 Telegram 전송 로그가 보이지 않았다. 재시작 전에는
  5~6초 간격의 Telegram `sendMessage` 성공 로그가 계속 있었다.

## 안전 경계

- 위험 등급: 3(외부 API·운영 알림·브로커 진단 안전 경계)
- 돈 경로 변경: 없음
- 실제 주문 실행: 없음
- 주문 게이트, 자본, whitelist, 포지션 한도, 손실 브레이커, 헌법, 커널 목록 변경: 없음
- 감사 로그 원본은 변경하지 않는다. Telegram cursor state에 동일 오류 억제용 SHA-256
  fingerprint만 저장한다.
- KIS 진단은 기존 마스킹 규칙을 적용해 계좌번호, token, app key, app secret, authorization을
  원문으로 남기지 않는다.

## 검증

PR #388 머지 전:

- `uv run pytest tests/unit/test_telegram_alerts.py tests/integration/test_telegram_alerts_cli.py tests/integration/test_broker_order_diagnostics.py tests/unit/test_manage_telegram_alerts_workflow.py tests/unit/test_configure_telegram_alerts_workflow.py` → 21 passed
- `uv run pytest` → 2257 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- `uv run auto-invest telegram-alerts --help` → `--max-catchup-alerts`, `--error-cooldown-seconds` 노출 확인
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run python scripts/check_handoff_facts.py` → OK
- `scripts/check_pr_quality_gate.py /tmp/telegram-alert-flood-pr-body.md` → pr-quality-gate-ok
- PR #388 상태: ready, `mergeStateStatus=CLEAN`, remote `pr-quality-gate` success

머지와 운영 조치 후:

- `Deploy on merge to main` run `28212963179` → success
- `KIS smoke (autonomous)` run `28212963184` → success
- `Manage Telegram alerts on server` restart run `28212999028` → success
- `Manage Telegram alerts on server` status run `28213025727` → success, service enabled/active

handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패했다. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `7a14315`로 오래된 문제였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2257 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

Telegram 폭주는 서버 알림 서비스를 새 코드로 재시작해 일단 멈춘 상태로 보인다. 다시 폭주하면
`Manage Telegram alerts on server` workflow의 `disable`로 서비스만 끄고, `status` journal에서
재시작 이후 `sendMessage`가 다시 증가하는지 먼저 확인한다.
