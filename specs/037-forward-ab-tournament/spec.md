# 스펙 037 — forward A/B 토너먼트 (추세 필터 ON vs OFF, 격리 트랙)

## 문제

스펙 035 가 "단순 보유를 이기는가"를 자동 판정하는 폐회로를 깔았고, 스펙 036 이 추세 필터
(드로다운 방어)를 추가해 forward 페이퍼 트랙에 켰다(스펙 036 후속). 그런데 forward-verdict
의 벤치마크는 *유니버스 균등 단순 보유*다 — 즉 "추세 ON 전략 vs 단순 보유"는 답하지만,
**"추세 필터 자체가 도움이 되는가"(ON vs 같은 전략의 OFF)**는 격리해 답하지 못한다. 추세
필터의 *한계 기여*를 알려면 교란변수 없는 대조군(같은 전략, 필터만 제거)이 필요하다.

## 목표

추세 필터 ON/OFF 두 후보를 **각자 전용 DB 로 격리**해 병렬 페이퍼 트레이딩하고, 스펙 035
forward-verdict 로 각각 판정해 나란히 비교한다. DB 파일이 격리 경계이므로 두 트랙의 체결·NAV
가 섞이지 않는다 — **코드 변경 0**(portfolio_id 태깅 불필요, 주문 경로 무변경).

## 설계 (왜 전용 DB 인가)

- 페이퍼 체결은 `ORDER_PAPER_FILLED`, NAV 는 `PORTFOLIO_NAV_SNAPSHOT` 으로 한 DB 의 audit_log
  에 쌓인다. nav-snapshot 은 그 DB 의 *모든* 페이퍼 체결을 재구성해 NAV 를 낸다 → 한 DB 에
  두 전략을 돌리면 체결이 섞여 분리 불가.
- 가장 깨끗하고 *코드 변경 없는* 격리는 **DB 파일 분리**다: `data/forward_trend.db`(ON) /
  `data/forward_notrend.db`(OFF). 각 DB 는 자기 전략의 체결·NAV·price_bars 만 담는다.
- `backfill-bars`(각 팔의 첫 명령)가 빈 DB 를 자동 마이그레이션(`allow_apply=True`)하므로 별도
  마이그레이션 단계도 필요 없다.

## 기능 요구 (FR)

- **FR-A01** 대조군 설정 `deploy/canary-portfolio-notrend.toml` — `canary-portfolio.toml`(ON)과
  유니버스·가중치·top_n·재조정 주기까지 **전부 동일**, 오직 `[portfolio.trend_filter]` 절만
  없음(교란변수 0).
- **FR-A02** 워크플로 `rebalance-paper-forward.yml` 를 두 팔로 재구성 — 각 팔은 전용 DB 에서
  backfill → rebalance(`--construct-universe-top-n 15`) → nav-snapshot → forward-verdict.
  PAPER 전용(`--mode paper`), 실주문 0건.
- **FR-A03** 사이드카 `LAST_RUN.md` 에 두 판정(ON/OFF)을 나란히 발행 + 각 팔 준비 로그.
- **FR-A04** 회귀 테스트 — 대조군이 ON 과 trend_filter 외 모든 운용 파라미터가 동일함을 못박음
  (A/B 가 추세 필터 효과를 격리하도록).

## 안전 경계 (비협상)

- **Kernel 터치 0건, 코드 변경 0.** 신규 산출물은 설정 TOML 1개 + 워크플로 재구성 + 테스트뿐.
  주문 경로(order_router)·NAV 계산·감사 스키마 무변경(DB 파일이 격리).
- **돈 0 이동.** 양 팔 모두 `--mode paper`(가상 체결만). 라이브 캐너리(`canary-live-rules.toml`)
  무관·무변경. 라이브 자동 승격 0건(EDGE_CONFIRMED 는 운영자 게이트 증거이지 자동 배포 아님).

## 합격 기준 (SC)

- **SC-A01** 대조군이 ON 과 trend_filter 외 전 파라미터 동일(회귀 테스트).
- **SC-A02** 워크플로 YAML 유효, 두 팔 각자 전용 DB, PAPER 전용.
- **SC-A03** 전체 테스트·린트 통과.

## 한계 / 다음

- 판정은 NAV 관측 ≥20(≈20 거래일)이 쌓여야 INSUFFICIENT_DATA 를 벗어난다 — A/B 차이도 그 뒤
  의미를 가진다. 사이드카에서 두 판정을 추적.
- 추세 필터의 진짜 가치는 *드로다운*이므로, 조용한 구간에선 ON≈OFF 가 정상(필터가 거의 안
  걸림). 차이는 하락 구간에서 벌어진다. 후속: 위험조정 지표를 Calmar(수익/낙폭)까지 확장해
  드로다운 방어를 더 잘 포착(별도 슬라이스).
