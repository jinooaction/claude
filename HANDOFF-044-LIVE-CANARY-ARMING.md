# HANDOFF 044 — 고도화를 소액 실거래로: 가드형 라이브 캐너리 무장 채널 (2026-06-04)

main 머지 `7a56370`(PR #174 스펙 039 보수본 → #175 $500 무장본+블로커 → #176 스펙 040 가드형
채널). 운영자 지시: "앞으로 항상 실거래 기반으로 고도화. 돈 못 벌면 의미 없다. 지금 소액
라이브 캐너리 무장 $500. 이어서 진행해."

## 한 줄 요약

고도화(추세 방어 포트폴리오)를 **소액 실거래**로 올리는 가드형 채널을 만들었다. 단, 실주문은
**기본 드라이런 미리보기**로 두고, 운영자가 명시 무장(`armed:true`)할 때만 나간다. 구현 중
**계좌 충돌**(룰 워커와 같은 실계좌) 블로커를 발견해, 룰 워커 비활성을 무장 전 필수로 못박았다.

## 현 상태 (정직)

- **실거래 격차**: 고도화(스펙 032~038: 포트폴리오·다요인·추세·forward 판정·칼마)는 전부
  페이퍼였다. 실거래는 `canary-live-rules.toml` = 단순 3룰 qty=1.
- **무장 진척**: 가드형 채널 + $500 무장본 + 측정(`--mode live`)까지 **구축 완료, 무장 직전**.
  PR #176 머지로 **드라이런 미리보기 1회 발화**(실주문 0건). 사이드카에서 "무장 시 실거래가
  무엇을 살지" 확인 가능.

## 구현 중 발견한 2가지 (왜 즉시 실주문 안 했나)

1. **$500 주가 현실**: SPY ~$540 / MSFT ~$430 / AAPL ~$316. 정수 주만 → $500 는 **1종목 1주**
   (top-2 는 ~$10k+). 무장본을 `top_n=1`(추세 통과 단일 우량주 1주)로 조정. 캡은 자본 대비 %라
   $500 에서 1주 사려면 커야 해 95% — 절대 위험은 자본 $500 이 천장(워크플로가 capital>$1,000
   무장 거부로 footgun 차단).
2. **🚨 실거래 계좌 충돌(치명적)**: 같은 실계좌에 룰 워커가 돌면, 포트폴리오 재조정이 DB 의
   현재 보유를 읽고 목표 자본 기준으로 초과분을 **청산** → 워커 포지션을 의도치 않게 매도(돈
   잃음). **한 실계좌엔 전략 하나** → 무장 전 룰 워커를 비활성으로 전환해야 한다.

## 만든 것

- `deploy/canary-live-portfolio.toml` — $500 무장본(top_n=1, 추세 방어, SPY·MSFT·AAPL 무확대).
- `.github/workflows/rebalance-live-canary.yml` — 가드형 채널:
  - 트리거: `workflow_dispatch` + `automation/rebalance-live.request` 센티넬 push.
  - **기본 드라이런 미리보기**(`rebalance-once --dry-run`, 주문 0건). 실주문은 `armed:true`일 때만
    (`--mode live --confirm-live`).
  - 안전장치: 자본 상한 $1,000, --confirm-live 인터록, K1 캡, 스펙 014 서킷 브레이커(halt_gate),
    추세 필터, 거래 집합 무확대.
  - 라이브 트랙 측정(NAV 스냅샷 + `forward-verdict --mode live` + 칼마).
  - 사이드카 `automation/rebalance-live-canary-last-run`.
- `automation/rebalance-live.request` — 센티넬, 기본 `armed:false`. 안전 회귀 테스트 2건.

## 무장(실주문)까지 남은 단계 — 운영자/다음 세션

1. **드라이런 미리보기 확인**: `git show origin/automation/rebalance-live-canary-last-run:LAST_RUN.md`
   — 무장 시 실거래가 무엇을 사고팔지 납득되는가?
2. **룰 워커 충돌 해소**: 같은 실계좌의 `canary-live-rules.toml` 워커를 비활성(disabled 룰셋)으로
   전환(go-live 채널 `automation/go-live-canary.request` 의 rules_path 변경). 한 계좌 전략 하나.
3. **무장**: `automation/rebalance-live.request` 의 `armed:false` → `armed:true` 로 머지 →
   `rebalance-once --mode live --confirm-live` 가 실주문(소액 1주). 추세 방어 포트폴리오가 실거래로.
4. **판정**: forward-verdict + 칼마(`--mode live`)가 실거래 트랙을 디플레이티드 샤프로 판정.

## 안전 경계 (지킨 것)

- **현재까지 돈 0 이동.** 무장 안 함(armed:false). 머지는 드라이런 미리보기만 발화. Kernel 터치
  0건. 기존 라이브 워커·페이퍼 트랙 무변경.
- **계좌 충돌로 운영자 $12k 포지션을 청산할 뻔한 위험을 발견해 멈췄다** — 무장 전 룰 워커
  비활성 필수로 못박음. 돈을 잃지 않게 막는 게 최우선(헌법 X).
- 헌법 X.4: 라이브 전환은 운영자 결정. 이 채널은 소액 캐너리 무장 전용, 풀라이브 아님.
