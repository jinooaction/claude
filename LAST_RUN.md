# KIS smoke 자율 검증 — 최신 실행 진단

이 파일은 `.github/workflows/kis-smoke.yml` 이 매 run 마다 자동 force-push 합니다. 운영자가 GitHub Actions UI 에 들어가지 않고도 외부 (예: claude session) 에서 `git fetch origin automation/kis-smoke-last-run && git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 로 진단 가능합니다.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T04:10:45Z |

## 상태

| 변수 | 값 |
|------|-----|
| secrets_present | true |
| key_valid | true |
| smoke_state | success |
| smoke_exit | 0 |

## SSH/원격 출력 (smoke_output.log)

```
--- smoke 전용 checkout 준비 ---
운영 repo: /opt/auto-invest (읽기 전용: .env/remote URL 확인만)
대상 commit: 758dda2534af38f444ac75361295fb49b489e234
smoke HEAD: 758dda2 (Merge pull request #577 from jinooaction/codex/handoff-after-forward-anchored-observe-gateway)

--- .env 확인 (KIS 키만 ✓ 표시, 값 노출 안 함) ---
  KIS_APP_KEY=[REDACTED] 설정됨
  KIS_APP_SECRET=[REDACTED] 설정됨
  KIS_ACCOUNT_NO=[REDACTED] 설정됨

--- KIS_LIVE_TEST=1 라이브 smoke 실행 ---
Using CPython 3.11.15
Creating virtual environment at: .venv
   Building auto-invest @ file:///tmp/auto-invest-kis-smoke/repo.DYQHHe
      Built auto-invest @ file:///tmp/auto-invest-kis-smoke/repo.DYQHHe
Installed 49 packages in 295ms
No entry for terminal type "unknown";
using dumb terminal settings.
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /tmp/auto-invest-kis-smoke/repo.DYQHHe/.venv/bin/python
hypothesis profile 'default'
rootdir: /tmp/auto-invest-kis-smoke/repo.DYQHHe
configfile: pyproject.toml
plugins: anyio-4.13.0, hypothesis-6.152.7, asyncio-1.3.0, respx-0.23.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 5 items

tests/integration/test_live_broker.py::test_live_kis_token_and_quote 
Live AAPL quote: $313.3300
PASSED
tests/integration/test_live_broker.py::test_live_kis_purchasable_cash 
Live KIS USD purchasable cash: $934.27
PASSED
tests/integration/test_live_broker.py::test_live_kis_positions 
Live KIS positions: 1개 보유
  - ORANY: 28주 (평단 $11.1950)
PASSED
tests/integration/test_live_broker.py::test_live_kis_combined_balance 
Live KIS balance: cash=$934.27, total=$1466.14680000
PASSED
tests/integration/test_live_broker.py::test_live_kis_recent_orders_have_no_open_unfilled 
Live KIS recent order/execution rows: 0개, open_unfilled=0개
PASSED

============================== 5 passed in 5.04s ===============================
```

## 다음 단계 추정

- 추가 액션 없음. 매일 03:00 UTC cron 으로 자동 감시 계속.
