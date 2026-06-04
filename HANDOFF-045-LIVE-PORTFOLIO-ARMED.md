# HANDOFF 045 — (A) 룰 워커 끄고 추세 방어 포트폴리오로 라이브 캐너리 무장 (2026-06-04)

main 머지 `96ff217`(PR #178 발행버그 수정 → #179 (A) 무장). 운영자: "(A) 룰 워커를 끄고
포트폴리오 전략으로 교체. 그런데 지금 돈 단위 계산이 틀리거나 그런 문제는 없는거지?"

## 한 줄 요약

고도화(추세 필터로 방어되는 포트폴리오)가 **드디어 실제 돈에 적용됐다** — 라이브 캐너리의
전략을 단순 3룰에서 추세 방어 포트폴리오로 교체(룰 워커 비활성 + 포트폴리오 무장, $500).
실주문은 시장시간 스케줄에서만. 무장 전 운영자의 돈 단위 질문에 코드+실데이터로 답했다.

## 돈 단위 검증 (운영자 질문 답 — 틀린 거 없음)

- **코드 감사(전부 USD·정수주)**: `rebalance_plan` investable=자본×invested_fraction,
  qty=floor(목표금액/가격). `_per_trade_cap_qty` cap=자본×per_trade%/100 → floor(cap/가격).
  **캡 기준 = 재조정 자본($500), 워커 $12k 아님.** `_marketable_limit` USD(ask/bid)·센트 양자화.
  브로커 `place_order`: `ORD_QTY`=정수주, `OVRS_ORD_UNPR`=USD 지정가, **FX 변환 없음**.
- **실데이터 드라이런(사이드카)**: `{"target_weights":{"AAPL":"1.0"},"results":[{"symbol":"AAPL",
  "side":"BUY","requested_qty":1,"routed_qty":1,"limit_price_usd":"312.48","state":"DRY_RUN"}]}`
  → $500 자본에 **AAPL 1주 @ $312.48**(≈$312), 매도 0건. 100배/FX/센트 오류 없음.
- 현재 라이브 포지션 0(NAV 스냅샷 holdings=[]) → 무장해도 **청산 없이 1주 매수만**.

## 발견·수정한 버그 (돈 계산과 무관)

라이브 워크플로 발행 스텝이 `set -u` 아래 큰따옴표 `$1,000` 을 `$1`(미설정 위치인자)로 해석해
실패 → 사이드카 미발행(`line 15: $1: unbound variable`). 문구를 "1000불 초과"로 교체 + 발행
스텝 `-u` 제외(주문 기록 보호). PR #178. **셸 인용 버그일 뿐, 돈 경로 계산 정상.**

## (A) 실행 — 룰 워커 → 포트폴리오 교체

1. **룰 워커 비활성**: `deploy/canary-live-rules-disabled.toml`(3룰 전부 `enabled=false`,
   caps·whitelist 동일) + `automation/go-live-canary.request` rules_path 교체(run_seq 6).
   → 워커는 돌되(백필·체결동기화·헬스) **룰 주문 0건**. 한 실계좌 전략 하나(충돌 해소).
2. **포트폴리오 무장**: `automation/rebalance-live.request` `armed: true`(run_seq 3, $500).
3. **시장시간 게이트**: 워크플로에 `schedule: cron "0 15 * * 1-5"`(15:00 UTC 평일) 추가 +
   LIVE 스텝 `if ... && github.event_name != 'push'` → **무장 머지(push)는 미리보기만,
   실주문은 시장시간 스케줄(또는 수동 dispatch)에서만**. 장 마감 시간대 무장 머지가 실주문을
   내는 일을 막는다.

## 현 상태 & 다음

- **무장 완료.** 머지 자체 = 미리보기만(돈 0 이동). go-live #6(룰 워커 비활성)은 머지 직후
  실행(같은 go-live 채널 직전 실행 성공 — 메커니즘 검증됨). **첫 실주문 = 다음 15:00 UTC
  평일 스케줄** → 추세 방어 포트폴리오가 AAPL 1주(~$312) 실거래.
- **확인 경로**: `git show origin/automation/rebalance-live-canary-last-run:LAST_RUN.md` —
  무장+push 실행은 "🟡 무장됨이나 이번 실행은 미리보기만"으로 표기(메시지 수정 반영). 스케줄
  실행 후엔 "⚠ 무장+실주문 실행"으로 바뀌고 라이브 재조정 결과가 찍힌다.
- **판정**: 실거래 체결이 쌓이면 forward-verdict `--mode live` + 칼마(스펙 035/038)가 실거래
  트랙을 디플레이티드 샤프로 판정 — "실거래 기반 고도화"의 측정 폐회로 완성.
- **자본 상향**: 운영자 결정. `rebalance-live.request` capital_usd 를 올리면 워크플로가
  $1,000 초과 시 거부(이 소액 설정의 캡은 95%라 큰 자본에 위험) — 자본 키우려면 캡 먼저 낮출 것.

## 안전 경계 (지킨 것)

- 자본 $500 = 최대 손실 한도(AAPL ~1주). 거래 집합 무확대(SPY·MSFT·AAPL, 헌법 II). 추세 필터
  방어(추세 아래 현금). 스펙 014 손실 서킷 브레이커 = 킬스위치(halt_gate 가 한도 초과 시 주문
  거부). K1 캡 천장. 자본 상한 $1,000 워크플로 가드. `--confirm-live` 인터록.
- 헌법 X.4: 운영자 지시 소액 라이브 캐너리. **풀라이브 아님**(VI 3단계는 별도 운영자 결정).
- Kernel 터치 0건(설정·워크플로·문서만). 페이퍼 트랙·기존 forward 도구 무변경.
