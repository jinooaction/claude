# KIS smoke 자율 검증 — 최신 실행 진단

이 파일은 `.github/workflows/kis-smoke.yml` 이 매 run 마다 자동 force-push 합니다. 운영자가 GitHub Actions UI 에 들어가지 않고도 외부 (예: claude session) 에서 `git fetch origin automation/kis-smoke-last-run && git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 로 진단 가능합니다.

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | 26712968267 |
| run_url | https://github.com/jinooaction/claude/actions/runs/26712968267 |
| commit | b701a26d3f64962c9afcee951f593552969b9481 |
| trigger | push |
| timestamp_utc | 2026-05-31T12:45:03Z |

## 상태

| 변수 | 값 |
|------|-----|
| secrets_present | true |
| key_valid | true |
| smoke_state | success |
| smoke_exit | 0 |

## SSH/원격 출력 (smoke_output.log)

```
Warning: Permanently added '202.182.125.132' (ED25519) to the list of known hosts.
--- git pull ---
Your branch is behind 'origin/main' by 8 commits, and can be fast-forwarded.
  (use "git pull" to update your local branch)
HEAD is now at b701a26 Merge pull request #128 from jinooaction/claude/gracious-knuth-gwAxV
현재 HEAD: b701a26 (Merge pull request #128 from jinooaction/claude/gracious-knuth-gwAxV)

--- .env 확인 (KIS 키만 ✓ 표시, 값 노출 안 함) ---
  KIS_APP_KEY: ✓ 설정됨
  KIS_APP_SECRET: ✓ 설정됨
  KIS_ACCOUNT_NO: ✓ 설정됨

--- KIS_LIVE_TEST=1 라이브 smoke 실행 ---
No entry for terminal type "unknown";
using dumb terminal settings.
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /opt/auto-invest/.venv/bin/python
hypothesis profile 'default'
rootdir: /opt/auto-invest
configfile: pyproject.toml
plugins: anyio-4.13.0, hypothesis-6.152.7, asyncio-1.3.0, respx-0.23.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 4 items

tests/integration/test_live_broker.py::test_live_kis_token_and_quote 
Live AAPL quote: $312.0600
PASSED
tests/integration/test_live_broker.py::test_live_kis_purchasable_cash 
Live KIS USD purchasable cash: $292.61
PASSED
tests/integration/test_live_broker.py::test_live_kis_positions 
Live KIS positions: 4개 보유
  - BHP: 1주 (평단 $47.9700)
  - MRK: 3주 (평단 $79.0900)
  - ORANY: 28주 (평단 $11.1950)
  - RELX: 6주 (평단 $54.1550)
PASSED
tests/integration/test_live_broker.py::test_live_kis_combined_balance 
Live KIS balance: cash=$292.61, total=$1521.58000000
PASSED

============================== 4 passed in 1.77s ===============================
```

## 다음 단계 추정

- 추가 액션 없음. 매일 03:00 UTC cron 으로 자동 감시 계속.
