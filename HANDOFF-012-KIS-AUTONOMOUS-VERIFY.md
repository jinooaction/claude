# HANDOFF 012 — KIS 회귀 자율 검증 도입

작성: 2026-05-22 (PR #33 + #34 머지 직후)
다음 세션이 `git fetch origin && git ls-remote --heads origin 'claude/*'` 발견 단계에서 이 파일을 자동으로 발견합니다.

## 한 줄 요약

KIS 잔고 0원으로 보이던 버그 + 보유 종목 stub + 의도 자본 100달러 정책을 한 PR (#33)으로 정리했고, 그 회귀가 다시 일어나면 운영자 손 안 거치고 자동으로 잡히는 워크플로우(#34, `KIS smoke (autonomous)`)를 추가했습니다.

## 머지된 PR 두 건 (main에 반영됨)

| PR | main 머지 커밋 | 내용 |
|----|--------------|------|
| #33 | `9096e21` | KIS 잔고 0원 표시 회귀 + 보유 종목 stub + 의도 자본 100달러 정책 제거 |
| #34 | `8cfb7d3` | 라이브 KIS smoke 3건 추가 + `.github/workflows/kis-smoke.yml` 신규 |

## #33이 고친 것 (요점만)

1. **KIS 잔고 0원 버그**: `broker/overseas.py` 의 `get_balance` 가 해외주식 잔고조회(`TTTS3012R`) 응답에서 존재하지 않는 필드(`frcr_dncl_amt_2` — 이건 국내잔고용)를 읽고 있었음. 별도 endpoint `inquire-psamount`(`TTTS3007R`) 호출로 교체. 보유 종목 평가금액은 `inquire-balance` `output1` 에서 합산. `total_value_usd = cash + 평가금액 합`.
2. **보유 포트폴리오 stub**: `cli.py:_fetch_kis_account_state` 가 holdings 를 stub 빈 리스트로 반환하던 부분을 실제 `get_positions` 호출로 교체. design 명령의 Claude 프롬프트와 audit 페이로드 둘 다에 보유 종목 정보가 흘러감.
3. **의도 자본 100달러 정책 제거**: `--capital` 옵션 / `intent_capital_usd > kis_balance_usd` 거부 / "자본 한도" 프롬프트 문구 — 운영자 요청으로 전부 제거. 자본은 항상 KIS 잔고 그대로 사용. 잔고 자체가 $10 미만일 때만 거부.

## #34가 추가한 자율 검증 인프라

- **`tests/integration/test_live_broker.py`** — 라이브 smoke 4건 (`KIS_LIVE_TEST=1` 가드):
  - `test_live_kis_token_and_quote` (기존)
  - `test_live_kis_purchasable_cash` (잔고 0원 회귀 방어)
  - `test_live_kis_positions` (포트폴리오 stub 회귀 방어)
  - `test_live_kis_combined_balance` (design 명령과 동일 경로의 end-to-end)

- **`.github/workflows/kis-smoke.yml`** — main push (broker/cli/reconciliation/live-test 변경 시) + 매일 03:00 UTC cron + `workflow_dispatch` 로 자동 실행. SSH 로 Vultr 인스턴스에 접속해 `KIS_LIVE_TEST=1 uv run pytest tests/integration/test_live_broker.py -v` 를 돌림. KIS 키는 인스턴스 `.env` 사용.

## 다음 세션이 해야 할 일 (우선순위 순)

### 1. kis-smoke workflow 첫 실행 결과 확인

PR #34 가 머지되면서 main commit `8cfb7d3` 의 path filter 조건(`tests/integration/test_live_broker.py` + `.github/workflows/kis-smoke.yml` 둘 다 포함) 이 충족되어 `KIS smoke (autonomous)` 워크플로우가 자동 트리거됐습니다.

- 결과 확인: GitHub Actions 탭의 `KIS smoke (autonomous)` 워크플로우, 또는 `mcp__github__list_commits` → `8cfb7d3` 의 check status.
- **통과**: 추가 작업 없음. 매일 03:00 UTC cron 으로 계속 자동 감시.
- **실패**: 후속 PR 로 자동 픽스. 자주 발생할 수 있는 원인:
  - **a. SSH 키/Secrets 미등록**: `VULTR_SSH_HOST/USER/PRIVATE_KEY/PORT` 가 GitHub Settings → Secrets and variables → Actions 에 등록 안 됨. 이는 운영자 1회 셋업 누락 — `docs/OPERATOR_GITHUB_ACTIONS_DESIGN.md` 가이드로 안내.
  - **b. 인스턴스 `.env` KIS 키 누락**: SSH 단계는 통과하지만 `KIS_*` 환경변수 빈 값이면 smoke 가 skip 됨 (의도된 fallback). 운영자가 인스턴스 콘솔에서 `scripts/set_secrets.sh` 실행 안내.
  - **c. KIS API 응답 필드 변경**: 운영자가 등록한 KIS 계좌 환경에서 `ord_psbl_frcr_amt` 가 다른 키로 응답하는 경우. `broker/overseas.py:get_purchasable_cash_usd` 의 후보 키 목록(`ord_psbl_frcr_amt` → `frcr_ord_psbl_amt1` → `frcr_dncl_amt1`)에 새 키 추가 PR.
  - **d. uv 경로 fallback**: workflow 의 첫 시도(`/usr/local/bin/uv run`)가 실패하면 자동으로 두 번째 시도(`cd ${REPO} && uv run`)로 fallback. 둘 다 실패하면 인스턴스에 uv 가 설치 안 됨 — `provision-vultr.yml` 의 setup 단계 확인.

### 2. 운영자가 design 명령을 다시 호출하면 검증 가능

운영자가 `operator-design.yml` 워크플로우를 dispatch 또는 매주 월요일 cron 으로 design 명령을 실행하면, 그 로그의 "KIS 예수금: $X / 총 평가: $Y" 부분이 0이 아닌 실제 값으로 표시되어야 합니다. 이전에는 0으로 표시되던 부분이 #33 픽스로 해결됨.

### 3. 후속 정리 (선택, 우선순위 낮음)

- 운영자가 헌법 IX.D 와 자율 수행 정책에 따라 "다음 작업" 으로 지정해주거나, 운영자 지시 없으면 다음 세션은 운영자에게 새 의도를 받기 전까지 대기.
- 가능한 후속 작업 후보 (운영자 결정 필요):
  - 스펙 004 (LLM 판단 지점) 본격 구현.
  - 스펙 005 (자율 튜너) 골격 → 본 구현.
  - design 명령에 보유 종목 활용 강화 (예: 평단보다 낮을 때 추가 매수 트리거 자동 생성).

## 안전 경계 (변경 없음)

- Kernel(K1~K6, K_meta) 터치 없음.
- K4 audit 페이로드 스키마 변경 없음.
- read-only smoke — 주문 endpoint 절대 호출 안 함.
- 트레이딩 안전 invariant (포지션 캡, whitelist, append-only audit) 모두 그대로.
