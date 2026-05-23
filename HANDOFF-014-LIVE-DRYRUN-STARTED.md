# HANDOFF 014 — 라이브 worker(dry-run) 시작 성공

작성: 2026-05-23 (PR #47 + #48 머지 직후, main `3010648`)
다음 세션이 `git fetch origin` + main 의 HANDOFF-*.md 발견 단계에서 이 파일을 자동 발견합니다.

## 한 줄 요약

운영자(mason)의 자율 수행 지시로 `auto-invest design` 을 재호출해 **라이브 worker 가 dry-run 모드로 정상 시작**됐습니다 (run `26330498160`, 2026-05-23 10:36 UTC). 잔고 $292.61, 적립 룰 + 보유 종목 활용 룰 생성 완료. 실주문은 아직 안 나갑니다(헌법 VI 1주일 안전 관찰).

## ⚠ 이전 HANDOFF 의 오해 정정 (다음 세션 필독)

- **HANDOFF-010 은 historical** — "ANTHROPIC 키 추가 + design 실행이 다음 단계" 라고 적혀 있으나, 그 단계는 이미 끝났음. ANTHROPIC 키는 인스턴스 `.env` 에 입력 완료 상태였고, 이번 세션에서 design 라이브 시작까지 완료.
- **"현금 $0" 은 버그였다** — HANDOFF-011 의 "현금 $0 으로 거부" 는 외화예수금 조회 버그(PR #33 `9096e21` 로 해결). 실제 KIS 해외계좌 현금은 **$292.61**, 총 평가 $1,536.38. 운영자가 "현금 0 아니다, 잔고 있다" 고 정확히 지적했고 그게 맞았음. 다음 세션은 잔고/키를 다시 의심하지 말 것.

## 이번 세션이 잡은 진짜 블로커 2개

design 재호출이 실패하던 원인은 잔고도 키도 아니었음. 두 가지 코드/CI 버그:

| PR | main 머지 | 내용 |
|----|----------|------|
| #47 | `8512fc2` | **프롬프트 누락**: `design/prompt.py` 가 적립용 `time` 트리거(`at_time`+`weekdays`) 사용법을 안 알려줘서, Claude 가 "매주 월요일 적립" 을 `kind="schedule"`(없는 종류) / `at_time="MON_09:35"`(형식 위반)로 만들어 검증 3회 실패 (run `26330304139`). 스키마(`config/rules.py` `TimeTrigger.weekdays`)는 이미 요일 스케줄 지원 → 프롬프트만 보강 + 회귀 테스트 추가. |
| #48 | `3010648` | **AUTO_OK 전달 버그**: `trigger-design.yml` 의 `AUTO_OK=1 sudo bash` 가 sudo env_reset 으로 변수를 비워, 검증 통과 후 OK prompt 가 interactive 로 빠져 `Aborted` (run `26330437897`). `sudo env AUTO_OK=1 bash` 로 우회. |

## 라이브 시작 결과 (run `26330498160`)

```
잔고: $292.61 USD, 총 평가: $1536.38
검증 통과 → OK 자동 입력 → WORKER_STARTED seq=231
라이브 시작 시각: 2026-05-23T10:36:17.979Z
생성 룰 저장: config/rules_auto_20260523T103616.toml
```

- design session: seq=226, 라이브 worker: seq=231 (실행 중)
- 시그널/체결/차단/오류 통계 전부 0 (방금 시작)

생성된 룰 (Claude 해석):
- `rule_dca_voo_monday` — VOO 매주 월요일 09:35 적립 (`kind="time"`, `at_time="09:35"`, `weekdays=[0]`, `cooldown_seconds=604800`)
- universe: VOO/QQQ/SPY + 보유 종목 BHP/MRK/ORANY/RELX
- holdings_applied: averaging_down(BHP/MRK/RELX), concentration_cap_skipped(ORANY)

## 현재 모드: dry-run (실주문 안 나감)

worker 는 `.env` 의 `AUTO_INVEST_MODE` 기준으로 동작. 현재 dry-run. 헌법 VI 단계적 확장(Backtest→Canary→Full)의 1주일 안전 관찰 단계.

## 다음 세션이 할 수 있는 일

### 1. 운영자가 "실거래로 전환" 이라고 하면

`AUTO_INVEST_MODE=live` 토글 — 돈이 실제로 움직이는 irreversible 행동이므로 **운영자 명시 지시 필요**. 인스턴스 `.env` 한 줄 변경 + worker 재시작:

```bash
# GitHub Actions workflow 로 (live-mode-toggle.yml 작성 권장)
ssh ... "sudo sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \
  && sudo systemctl restart auto-invest.service"
```

`live-mode-toggle.yml` 워크플로우를 작성하면 운영자가 콘솔 안 들어가고 GitHub Actions 로 전환 가능 (HANDOFF-011 라인 63-72 에서 이미 권장).

### 2. design 재호출 (의도 변경 / 룰 갱신)

`claude/verify-operator-setup` 브랜치의 `.trigger/design-now.txt` 에 새 줄 추가 + push → `trigger-design.yml` 자동 발동 → SSH 로 `sudo env AUTO_OK=1 bash operator_design.sh` 실행 → 결과 `.verify/last_design.md` 에 commit. **AUTO_OK 이제 정상 동작**. 의도를 바꾸려면 `trigger-design.yml` 의 `INTENT` default 를 수정하거나 workflow_dispatch 로 다른 의도 입력.

### 3. dry-run 관찰 (1주일)

- `git fetch origin automation/kis-smoke-last-run && git show origin/automation/kis-smoke-last-run:LAST_RUN.md` — KIS 연결 매일 자동 감시.
- worker 상태: design `--check` (verify-operator-setup 트리거로 SSH 실행) 또는 status-check.yml 워크플로우 작성.

### 4. 후속 spec 후보 (운영자 결정 필요)

- 스펙 008(백테스트) 완성 시 design 검증의 백테스트 단계 자동 활성화 (현재는 import 가드로 통과 처리).
- 스펙 007(hardened canary) — 자율 deploy 게이트.
- 스펙 005(autonomous tuner) — 시장 변화 따라 룰 자동 진화.

## 안전 경계 (이번 세션 변경 없음)

- Kernel(K1~K6, K-meta) 터치 0건. PR #47 은 시스템 프롬프트 문자열 + 테스트, PR #48 은 운영 트리거 워크플로우.
- 트레이딩 안전 invariant (포지션 캡, 화이트리스트, append-only audit, market-hours guard) 모두 그대로.
- 라이브 worker 는 dry-run — 실주문 endpoint 호출 안 함. 실거래는 `AUTO_INVEST_MODE=live` 명시 토글 필요.
- 테스트: 743 passed, 4 skipped (라이브 KIS 가드). 린트 clean.

## 운영자 환경 정보 (재확인 안 함 — 이미 다 셋업됨)

- IP `202.182.125.132` (Vultr Tokyo), SSH user `root`, port `22`
- KIS 키 3개 + ANTHROPIC 키 모두 `.env` 입력 완료
- GitHub Secrets 4개 (VULTR_SSH_HOST/USER/PRIVATE_KEY/PORT) 등록됨, 오늘도 정상 (사이드카 진단 run `26325493405`)
- 운영자는 인스턴스 콘솔에 직접 안 들어감 — 모든 작업은 GitHub Actions SSH 자율 수행
