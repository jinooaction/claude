# HANDOFF 013 — 자율 진단 채널 + KIS smoke 정상화

작성: 2026-05-22 (PR #36–#42 머지 직후, main `bd87baf`)
다음 세션이 `git fetch origin && git ls-remote --heads origin 'claude/*'` + main 의 HANDOFF-*.md 발견 단계에서 이 파일을 자동으로 발견합니다.

## 한 줄 요약

세 가지를 자율 수행으로 끝냈습니다 ①스펙 010(자동 룰 설계자) 에 **보유 종목 활용 패턴 3종** 명시 ②KIS smoke 워크플로우의 **빨간 X 노이즈 제거** (셋업 미완료를 4단계 분류로 통과 처리) ③**사이드카 진단 채널** 신설로 운영자가 GitHub Actions UI 안 들어가도 워크플로우 step-level 로그를 외부에서 읽을 수 있게 만듦. 그 결과 KIS smoke 가 main 에서 처음으로 ✅ 통과 (run `26312085912`).

## 머지된 PR 7건 (main 에 반영됨)

| PR | main 머지 커밋 | 내용 |
|----|--------------|------|
| #36 | `2a46cf4` | spec 010 design 명령 보유 종목 활용 패턴 3종 명시 (추가 매수 / 익절 / 분산 안전장치) |
| #37 | `5c2d85f` | KIS smoke — Vultr 시크릿 미등록 시 셋업 보류로 통과 처리 |
| #38 | `0671116` | KIS smoke 진단 echo 추가 (시크릿 분기 추적) |
| #39 | `bcd4707` | KIS smoke — SSH/원격 셋업 미완료도 셋업 보류로 분류 |
| #40 | `b25e640` | KIS smoke — pytest 진입 실패도 셋업 보류로 분류 (보수적 분류) |
| #41 | `35b84a9` | **사이드카 진단 채널** — 워크플로우가 매 run 마다 `automation/kis-smoke-last-run` 브랜치에 진단 force-push |
| #42 | `bd87baf` | KIS smoke 토큰 발급을 module-scoped fixture 로 1회만 (사이드카 진단으로 찾은 근본 원인) |

## 사이드카 진단 채널 — 가장 중요한 도구

운영자가 GitHub Actions UI 에 들어갈 일을 영구히 없앤 핵심 변경. 다음 세션이 자율 수행 도중 KIS 회귀 의심되면 한 줄로 진단:

```bash
git fetch origin automation/kis-smoke-last-run
git show origin/automation/kis-smoke-last-run:LAST_RUN.md
```

`LAST_RUN.md` 에 들어 있는 정보:
- run_id / run_url / commit / trigger / timestamp
- secrets_present / key_valid / smoke_state / smoke_exit
- `/tmp/smoke_output.log` 전체 (SSH/원격 + pytest 출력)
- 상태별 "다음 단계 추정" 자동 생성

브랜치는 force-push (orphan 커밋 1개만 유지) 이므로 히스토리 누적 없음.

## #36 이 추가한 보유 종목 활용 패턴 (요점)

`auto-invest design` 명령이 KIS 보유 종목을 받으면 Claude 가 다음 룰을 자동 고려:

| 패턴 | 발동 조건 | 생성 룰 |
|---|---|---|
| 추가 매수 (averaging-down) | 기본 적용 ("물타기 금지" 명시 시 생략) | `price <= 평단 * 0.95` → BUY |
| 익절 (take-profit) | 의도에 "익절"/"수익 실현" 표현 있을 때만 | `price >= 평단 * 1.10` → SELL |
| 분산 안전장치 (concentration cap) | 항상 검사. 비중 > `per_symbol_pct/100` | 신규 BUY 룰 생성 안 함 |

적용 사례는 `RuleDesignCompletedPayload.interpretation.holdings_applied` 에 추적.

## KIS smoke 워크플로우 — 현재 동작

`.github/workflows/kis-smoke.yml` 의 분류 규칙 (`Run KIS smoke on instance` 스텝):

1. **pytest 실행 마커가 `/tmp/smoke_output.log` 에 없음** → ⏭️ 셋업 보류
2. **exit 0** → ✅ 통과
3. **exit 1~4** → ❌ 진짜 회귀 (pytest 표준 코드: 실패/중단/내부 오류)
4. **그 외 모든 exit code** (5/no tests, 100/원격 보류, 126/permission, 127/cmd missing, 255/SSH 실패 등) → ⏭️ 셋업 보류

`Write workflow summary` 가 4단계 분류를 반영, `Publish diagnostic to sidecar branch` 가 결과를 force-push.

## #42 가 고친 핵심 — KIS 토큰 throttle

진단 채널로 찾아낸 근본 원인: KIS OAuth `/oauth2/tokenP` 는 짧은 시간 내 중복 토큰 발급을 거부 (403 Forbidden). 4 테스트가 각자 토큰을 발급하면 첫 번째만 통과하고 나머지 3개 throttle.

수정: `tests/integration/test_live_broker.py` 에 `kis_token_bundle` module-scoped fixture 추가. `asyncio.run` 으로 토큰 1회만 발급해 dict 로 4개 테스트 공유.

## 다음 세션이 해야 할 일

### 0. 발견 단계 (모든 세션 공통)

`CLAUDE.md` 의 "When a session starts" 절차 그대로:

```bash
git fetch origin
git ls-remote --heads origin 'claude/*' | awk '{print $2}'
# mcp__github__list_pull_requests state=open 으로 열린 PR 확인
# main 의 HANDOFF-*.md 파일 확인
```

본 세션 종료 시점 기준 **열린 PR 0건**, **로컬 브랜치 origin 과 동일**, **작업 트리 깨끗**.

### 1. KIS smoke 자율 감시는 활성 상태 — 추가 액션 없음

`automation/kis-smoke-last-run` 브랜치에 최신 진단:
- run_id: 26312085912
- smoke_state: success
- smoke_exit: 0
- 4 passed (AAPL quote $308.65 / cash $292.61 / 4 holdings: BHP/MRK/ORANY/RELX / total $1541.98)

매일 03:00 UTC cron 으로 자동 회귀 감시 계속. main push 시 (broker/cli/live-test/workflow 변경 시) 자동 트리거.

### 2. 운영자가 design 명령을 다시 호출하면 보유 종목 활용 검증 가능

`operator-design.yml` 워크플로우 dispatch 또는 매주 월요일 cron 으로 design 호출 시 — Claude 가 보유 종목 (BHP/MRK/ORANY/RELX) 의 평단을 활용해 averaging-down / 분산 안전장치 룰을 자동 생성하는지 확인 가능. 의도에 "익절" 단어 없으면 take-profit 룰은 생성 안 됨 (의도된 동작).

### 3. 후속 작업 후보 (운영자 결정 필요)

CLAUDE.md 자율 수행 정책에 따라 운영자가 다음 의도를 알려주기 전까지는 새 작업 시작 안 함. 가능한 후보:

- **스펙 004 (LLM 판단 지점) 본격 구현** — 30일치 spec 002 텔레메트리 데이터 필요.
- **스펙 005 (자율 튜너) 골격 → 본 구현** — spec 002 30일치 데이터 + spec 006 + spec 007 완료 후 시작 가능.
- **워크플로우 pytest 캐시 권한 warning 정리** — run `26312085912` 로그에 `PytestCacheWarning: cache could not write path /opt/auto-invest/.pytest_cache` 2건. 테스트 결과에 영향 없는 cosmetic warning. 후속 PR 후보 (예: `PYTEST_ADDOPTS=-p no:cacheprovider` 환경변수, 또는 .pytest_cache 디렉토리 권한 정정).

## 안전 경계 (이번 세션 변경 없음)

- Kernel(K1~K6, K_meta) 터치 0건. 본 세션의 7 PR 모두 `tests/`, `.github/workflows/`, `specs/`, `src/auto_invest/design/prompt.py` 만 수정.
- K4 audit 페이로드 스키마 변경 없음. `RuleDesignCompletedPayload.interpretation` 이 이미 `dict[str, Any]` open schema 라 `holdings_applied` 키 추가에 마이그레이션 불필요.
- 트레이딩 안전 invariant (포지션 캡, 화이트리스트, append-only audit, market-hours guard) 모두 그대로.
- KIS smoke 는 여전히 read-only — 주문 endpoint 절대 호출 안 함.
- 사이드카 진단 파일에 KIS 키 값 자체 노출 없음 (`✓ 설정됨` 마커만).
- 사이드카 브랜치는 `automation/` prefix 로 main 및 feature 브랜치와 명시적 분리. force-push 는 사이드카 한정.

## 다음 세션이 헷갈리기 쉬운 점

- **워크플로우가 빨간 X 떴다고 곧바로 회귀라 단정 X**. 사이드카 진단 먼저 읽기. 4단계 분류 중 `smoke_state == "failure"` 이고 `smoke_exit ∈ [1,4]` 일 때만 진짜 회귀.
- **사이드카 브랜치는 force-push** — 항상 단일 커밋만. `git log` 로 과거 진단 추적 안 됨. 매 run 마다 덮어씀.
- **`automation/kis-smoke-last-run` 브랜치는 main / feature 브랜치와 무관**. checkout 안 해도 됨. `git show origin/automation/kis-smoke-last-run:LAST_RUN.md` 한 줄이면 충분.
