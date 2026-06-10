# forward 엣지 자동 무장 게이트 (스펙 049) — 운영 안내

운영자 지시 **"forward 검증 후 자동 무장"**(2026-06-10)의 자동화. 검증된 글로벌 분산
추세 앙상블(ARM E, `deploy/global-trend-portfolio.toml` / `data/forward_global.db`)의
forward 판정이 **EDGE_CONFIRMED** 가 되면, 라이브 캐너리 무장 센티넬
(`automation/rebalance-live.request`)을 `armed: true` 로 뒤집는 PR 을 자동으로 연다.

- 게이트 워크플로: `.github/workflows/forward-edge-autoarm.yml` (매 평일 23:50 UTC).
- 결정 로직(테스트됨): `src/auto_invest/portfolio/autoarm.py` + CLI `auto-invest autoarm-decide`.
- 최신 결정 확인(컨테이너에서):
  ```bash
  git fetch origin automation/edge-autoarm-last-run
  git show origin/automation/edge-autoarm-last-run:LAST_RUN.md
  ```

## 무장 조건 (전부 만족해야 ARM)

1. **EDGE_CONFIRMED** — 검증된 앙상블의 forward 판정(스펙 035). 아니면 WAIT(정상, 더 쌓여야 함).
2. **검증=무장 정합성** — 라이브 캐너리 설정(`canary-live-portfolio.toml`)의 전략 지문이
   검증한 앙상블과 일치. 불일치면 BLOCKED(검증 안 한 전략은 무장 안 함).
3. **미무장** — 이미 `armed: true` 면 ALREADY_ARMED(멱등 no-op).
4. **킬스위치 없음** — 아래.

## ⚠ 즉시 정지 (킬스위치)

이 디렉터리에 **`AUTOARM_DISABLED`** 라는 빈 파일을 만들어 main 에 머지하면 게이트가 멈춘다
(결정 DISABLED, no-op). 자동 무장을 막고 싶을 때:

```bash
touch automation/AUTOARM_DISABLED
git add automation/AUTOARM_DISABLED && git commit -m "ops: 자동 무장 게이트 정지(킬스위치)"
# main 에 머지
```

되살리려면 그 파일을 지우면 된다.

## 안전 경계 (정직)

- 무장 머지 자체는 **미리보기만** — 첫 실주문은 다음 미국 정규장 스케줄
  (`rebalance-live-canary.yml` 은 push 가 아니라 schedule 에서만 실주문). 운영자가 사이드카
  `automation/rebalance-live-canary-last-run` 로 무엇을 살지 검토하고 첫 실주문 전에 disarm 할
  시간이 있다.
- 자본은 소액(센티넬 `capital_usd`, 캡 $1,000 이하로 클램프). 자동 게이트가 노출을 못 키운다.
- 라이브 거래 집합 SPY·IEF·GLD(헌법 II). 풀라이브 아님(헌법 X.4 — VI 3단계는 별도 운영자 결정).
- 헌법 X.4(v4.0.0): 라이브 전환은 운영자 결정. 이 게이트는 운영자 명시 지시 하 *라이브 캐너리*
  무장 준비 전용.
