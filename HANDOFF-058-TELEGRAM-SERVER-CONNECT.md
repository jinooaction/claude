# HANDOFF 058 — 스펙 061 Telegram 서버 연결 자동화 (2026-06-22)

main 베이스라인: `845c5b1`(PR #382). 운영자가 Telegram chat id를 제공한 뒤, 남은 서버 연결
작업을 직접 SSH나 수동 `.env` 편집 없이 끝내기 위해 GitHub Actions workflow를 추가하고 실제로
실행했다. 이 작업은 일반 주문 알림 observer를 켜는 운영 경로이며, 주문 실행 경로가 아니다.

## 무엇이 바뀌었나

- `.github/workflows/configure-telegram-alerts.yml`: `workflow_dispatch` 수동 실행 workflow를
  추가했다.
- workflow는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `VULTR_SSH_*` GitHub secrets 존재를
  확인하고, token/chat id 원문과 base64 표현을 모두 mask한다.
- workflow는 서버 `/opt/auto-invest/.env`에 다음 값을 멱등 반영한다:
  `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `TELEGRAM_SOURCE_LABEL=auto-invest`.
- workflow는 서버에서 `auto-invest telegram-alerts --test-message`를 먼저 실행하고,
  성공한 뒤 `auto-invest-telegram-alerts.service`만 enable/start한다.
- `tests/unit/test_configure_telegram_alerts_workflow.py`: secrets, masking, observer-only enable,
  hardcoded secret 부재를 정적으로 검증한다.
- `deploy/README.md`: 운영자가 GitHub Actions에서 `Configure Telegram alerts on server`를
  실행하면 서버 연결이 끝나는 쉬운 경로를 앞에 추가했다.
- `specs/061-telegram-server-connect/`: 문제 정의, 계획, 작업 목록을 추가했다.

## 현재 운영 상태

- GitHub secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`는 설정됐다. token은 숨김 입력으로 받아
  화면과 로그에 출력하지 않았다.
- 로컬 Telegram test message 전송이 성공했다.
- `Configure Telegram alerts on server` run `27944499731`이 성공했다.
- 서버 `.env` 반영, 서버 test message, `auto-invest-telegram-alerts.service` enable/start까지
  완료됐다.
- 일반 주문 알림은 이제 서버 `audit_log`의 새 주문·거부·체결·halt·error 이벤트를 Telegram으로
  보낼 준비가 되어 있다. 과거 로그는 명시적 `--replay-existing` 없이는 전송하지 않는다.

## 안전 경계

- 위험 등급: 3(외부 API와 런타임 비밀값의 서버 연결 경로 추가)
- 돈 경로 변경: 없음
- 실제 주문 재시도: 없음
- 주문 라우터·브로커 제출·체결 동기화·위험 게이트 변경: 없음
- 자본·화이트리스트·손실 브레이커·캡 변경: 없음
- 헌법 변경: 없음
- 커널 목록 변경: 없음
- 서버에서 enable/start한 것은 `auto-invest-telegram-alerts.service`뿐이다. trading worker,
  deploy service, live mode, order routing은 건드리지 않았다.
- 이전에 브라우저 주소창에 노출된 Telegram token은 폐기·재생성된 token을 사용해야 한다.
  저장소에는 token/chat id 원문을 남기지 않는다.

## 배포와 외부 확인

- PR #382 main merge commit: `845c5b1`
- `Deploy on merge to main` run `27944489222` → success
- `Configure Telegram alerts on server` run `27944499731` → success
- `KIS smoke (autonomous)`는 이번 workflow/doc/spec/test 변경에는 path filter 때문에 트리거되지
  않았다. 최신 KIS sidecar 성공은 #380 `6384584` 기준 run `27942372526`이다.
- 서버 Actions Summary와 서버 `audit_log`의 `DEPLOY_*` 행은 이 컨테이너에서 직접 확인하지 않았다.

## 검증

PR #382 머지 전:

- `uv run pytest tests/unit/test_configure_telegram_alerts_workflow.py` → 3 passed
- workflow YAML parse check → OK
- `git diff --check` → OK
- `uv run ruff check src tests` → All checks passed
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2242 passed, 4 skipped
- PR 품질 관문 통과

handoff 갱신 직전:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건 실패. 코드 실패가 아니라
  `HANDOFF.md` 마지막 main 커밋 행이 `845c5b1`로 갱신되지 않은 문제였다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → `OK (14/14)`
- `uv run pytest -q` → 2242 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

Telegram 일반 주문 실시간 알림은 서버까지 연결됐고 service도 켜졌다. 알림 장애가 생기면 주문
경로 문제가 아니라 Telegram secrets, 서버 `.env`, `auto-invest-telegram-alerts.service` journal,
state file을 먼저 확인한다.
