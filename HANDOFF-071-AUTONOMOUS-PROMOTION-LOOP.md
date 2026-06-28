# HANDOFF 071 — 자율 승격 루프 자동화 (2026-06-29 KST)

main 베이스라인: `ddecebb`(PR #408). 자율 성장 후보를 실제 돈 경로로 바로 보내지 않고, 다음 검증 단계로 자동 분류하는 read-only 승격 루프를 출시했다.

## 무엇이 바뀌었나

- `specs/068-autonomous-promotion-loop/`: 목표, 비목표, 안전 경계, 데이터 모델, 계약, quickstart, tasks를 남겼다.
- `src/auto_invest/analytics/promotion_loop.py`: 후보 backlog와 sidecar 증거를 읽어 승격 단계를 결정한다.
- `scripts/promotion_loop_probe.py`: workflow와 로컬 재현용 probe를 추가했다.
- `auto-invest promotion-scan`: 같은 판정을 명령줄에서 실행한다.
- `.github/workflows/autonomous-promotion-loop.yml`: 매일 08:45 UTC와 관련 main push 때 `automation/autonomous-promotion-last-run` sidecar를 발행한다.
- `pipeline_liveness`: 새 `autonomous-promotion` sidecar를 non-critical 감시 대상으로 등록했다.
- `safety.command_registry`: `promotion-scan`을 A0 읽기 전용 명령으로 등록했다.

## 운영상 의미

- 이제 자율 성장 루프가 후보를 만들면 승격 루프가 그 후보를 다음 단계로 자동 분류한다.
- 단계는 `BACKTEST_REQUIRED`, `RECENT_OOS_REQUIRED`, `FORWARD_REGISTRATION_READY`, `FORWARD_ACCUMULATING`, `CANARY_CANDIDATE`, `EXISTING_GATE_READY`, `OPERATOR_REVIEW`, `DISCARD`다.
- `CANARY_CANDIDATE`는 “실주문 승인”이 아니라 “기존 돈 게이트에 제출할 후보”라는 뜻이다.
- `EXISTING_GATE_READY`도 직접 주문하지 않는다. 전략 교체는 스펙 055 재지정 게이트, 자본 증액은 스펙 050 자본 사다리로만 간다.

## 백테스트와 소액 실거래의 차이

세계 최고 수준의 백테스트는 반드시 필요하다. 전략 논리, 비용 민감도, 과최적화, 최근 표본외 성능, walk-forward 강건성을 검증한다.

하지만 백테스트가 해결하지 못하는 영역이 있다.

- 브로커 주문 거부
- 부분 체결과 미체결
- 실계좌 현금, 결제, 보유 종목 충돌
- 장중 호가 스프레드와 슬리피지
- API 지연, 장애, 토큰 갱신
- append-only 감사 로그와 일일 정산

그래서 백테스트 통과는 캐너리 후보 자격이지, 실계좌 실행 검증 완료가 아니다. 소액 live canary는 전략을 다시 검증하는 단계가 아니라 실제 실행 경로를 작은 손실 한도 안에서 검증하는 단계다.

## 첫 실행 증거

- `Autonomous promotion loop` run `28332023253`: success
- sidecar: `automation/autonomous-promotion-last-run`
- sidecar commit: `ddecebb24afe85b389ba5c5f2b183f808e21d4d1`
- `overall_status`: `ok`
- 누락 증거: 없음
- 현재 상위 후보: 모두 `BACKTEST_REQUIRED`
- 안전 문구: 주문, 자본, whitelist/caps, live 전략, sentinels 변경 없음

## 배포와 smoke

- `Deploy on merge to main` run `28332023265`: success
- `KIS smoke (autonomous)` run `28332023268`: success
- KIS smoke commit: `ddecebb24afe85b389ba5c5f2b183f808e21d4d1`
- `key_valid=true`, live broker smoke 4건 통과
- 배포는 dry-run worker 코드 반영이다. 실거래 전환이 아니다.

## 안전 경계

- 위험 등급: 2(read-only 운영 자동화)
- 실제 주문 실행: 없음
- broker API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체: 없음
- sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 새 workflow는 GitHub sidecar branch 발행만 한다.

## 검증

PR #408 머지 전:

- `uv run pytest -q` → 2321 passed, 4 skipped
- `uv run ruff check src tests scripts/promotion_loop_probe.py` → All checks passed
- `git diff --check` → clean
- `uv run python scripts/promotion_loop_probe.py --evidence-dir tests/fixtures/promotion_loop/fresh --json --now 2026-06-29T02:00:00Z --commit abc1234 --run-id smoke` → success
- `uv run auto-invest promotion-scan --evidence-dir tests/fixtures/promotion_loop/fresh --format json --now 2026-06-29T02:00:00Z --run-id smoke` → success
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- PR 품질 관문 → success, mergeable `CLEAN`, merge 방식으로 main에 병합

handoff 갱신 전 main 기준:

- `uv run ruff check src tests` → All checks passed
- `uv run pytest -q` → stale `HANDOFF.md` 때문에 하네스 2건만 실패. 이 handoff 갱신은 `마지막 main 커밋` 행과 스펙 068 상태를 바로잡아 그 원인을 제거한다.

## 다음 세션 한 줄

자율 승격 루프는 후보를 돈으로 바로 바꾸는 장치가 아니라, 후보를 백테스트부터 기존 돈 게이트까지 안전한 다음 검증 단계로 계속 자동 분류하는 장치다.
