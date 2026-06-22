# HANDOFF 057 — 스펙 060 Telegram 모바일 주문 알림 (2026-06-22)

main 베이스라인: `6384584`(PR #380). 운영자가 모바일에서 micro GTAA 검증과 일반 주문 실행,
매수, 매도, 거부, 체결 결과를 실시간으로 알고 싶다고 요청했고, Telegram Bot API 기반 알림을
추가했다. Telegram 알림은 관찰 경로이며 주문 경로가 아니다.

## 무엇이 바뀌었나

- `specs/060-telegram-order-alerts/`: 문제 정의, 설계, 계약, 빠른 시작, 작업 목록을 추가했다.
- `.github/workflows/rebalance-micro-gtaa-canary.yml`: workflow 마지막에 Telegram best-effort 요약
  전송 단계를 추가했다. secrets가 없으면 성공으로 skip하고, 전송 실패도 workflow 결과를 실패로
  바꾸지 않는다.
- `src/auto_invest/notifications/telegram.py`: Telegram 설정 로딩, token/chat id 비밀값 등록,
  메시지 마스킹, 길이 제한, bounded retry 전송 helper를 추가했다.
- `src/auto_invest/notifications/audit_tail.py`: `audit_log`의 새 주문·거부·체결·halt·error 이벤트를
  읽어 모바일 알림 메시지로 포맷하는 cursor tailer를 추가했다.
- `src/auto_invest/cli.py`: `auto-invest telegram-alerts` observer 명령을 추가했다. dry-run,
  test-message, replay-existing, follow 모드를 지원한다.
- `deploy/auto-invest-telegram-alerts.service`: 선택형 systemd service를 추가했다.
- `deploy/sync-units.sh`: 새 service 파일은 설치하지만 자동 enable하지 않는다.
- `deploy/README.md`: BotFather bot 생성, `chat.id` 확인, GitHub secrets, 서버 `.env`,
  test-message, enable/disable 절차를 문서화했다.
- `src/auto_invest/safety/command_registry.py`: `telegram-alerts`를 `A2` 제안 등급으로 등록했다.
  주문 가능, 브로커 사용, DB 쓰기는 모두 false다.

## 현재 운영 상태

- 코드와 systemd unit은 main에 있다.
- GitHub Actions micro GTAA 알림은 repository secrets `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`가 있어야 전송된다. secrets가 없으면 skip된다.
- 서버 일반 주문 알림은 아직 자동으로 켜지지 않는다. 운영자가 `/opt/auto-invest/.env`에
  `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 넣고 아래 순서로 켜야 한다.

```bash
cd /opt/auto-invest
/usr/local/bin/uv run auto-invest telegram-alerts \
  --env-file .env --db data/auto_invest.db \
  --state-file data/telegram_alerts_state.json --test-message
sudo systemctl enable --now auto-invest-telegram-alerts.service
```

- 첫 일반 주문 알림 실행은 state file이 없으면 현재 `audit_log` 마지막 `seq`부터 시작한다.
  과거 로그 전체를 보내려면 명시적으로 `--replay-existing`를 사용해야 한다.
- 실제 Telegram API delivery는 운영자 token/chat id가 있어야 검증 가능하다. 이번 PR에서는 mock,
  dry-run, workflow static 검증까지 수행했다.

## 안전 경계

- 위험 등급: 3(외부 API와 런타임 비밀값 경로 추가)
- 돈 경로 변경: 없음
- 주문 라우터·브로커 제출·위험 게이트 변경: 없음
- 헌법 변경: 없음
- 커널 목록 변경: 없음
- K1 캡·화이트리스트·낙폭 예산·손실 브레이커 변경: 없음
- `audit_log` 변경: 읽기 전용 observer만 추가. audit schema는 변경하지 않았다.
- 비밀값: token, app key, app secret, authorization, 계좌번호, chat id는 저장소에 커밋하지 않는다.
  메시지와 오류 출력에서 민감값은 마스킹하거나 출력하지 않는다.
- 외부 API 실패: bounded timeout/retry 후 실패한다. 알림 실패는 주문 제출, 체결 동기화,
  halt 설정, 손실 브레이커 판단을 바꾸지 않는다.

## 배포와 외부 확인

- PR #380 main merge commit: `6384584`
- `Deploy on merge to main` run `27942372448` → success
- `KIS smoke (autonomous)` run `27942372526` → success
- KIS smoke sidecar: commit `6384584`, `key_valid=true`, `smoke_state=success`, live KIS 테스트 4건 통과
- 이 배포는 코드와 unit 파일 반영 확인이다. Telegram service enable 또는 실거래 전환을 뜻하지 않는다.
- 서버 Actions Summary와 서버 `audit_log`의 `DEPLOY_*` 행은 이 컨테이너에서 직접 확인하지 않았다.

## 검증

PR #380 머지 전:

- `uv run pytest tests/unit/test_safety_command_registry.py tests/unit/test_telegram_alerts.py tests/integration/test_telegram_alerts_cli.py tests/unit/test_micro_gtaa_telegram_alerts.py`
  → 14 passed
- `uv run pytest -q` → 2239 passed, 4 skipped
- `uv run pytest` → 2239 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- YAML parse check for `.github/workflows/rebalance-micro-gtaa-canary.yml` and
  `.github/workflows/mobile-status-pages.yml` → OK
- `git diff --check` → OK
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run python scripts/check_handoff_facts.py` → OK

handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건 실패. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `6384584`로 갱신되지 않은 문제였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2239 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

Telegram 모바일 알림 코드는 배포됐지만 일반 주문 실시간 알림은 아직 운영자가 `TELEGRAM_*`
비밀값을 넣고 service를 enable해야 켜진다. 알림은 observer 전용이므로, 실패하더라도 주문 경로
문제로 해석하지 말고 token/chat id, service journal, state file을 먼저 확인한다.
