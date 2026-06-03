# HANDOFF 042 — 스펙 037: forward A/B 토너먼트 (추세 ON vs OFF, 2026-06-03)

main 머지 `e1cae73`(PR #170). Kernel 터치 0건, **코드 변경 0**(설정 TOML + 워크플로 + 테스트만),
돈 0 이동. 운영자 지시: "계속해"(앞서 제안한 옵션 2 = forward 전략 토너먼트).

## 한 줄 요약

추세 필터 **ON vs OFF** 두 후보를 **각자 전용 DB 로 격리**해 병렬 페이퍼 트레이딩하고, 스펙
035 forward-verdict 로 각각 판정한다. "추세 필터가 *실제로* 도움이 되는가"를 교란변수 없이
비교하는 격리 실험.

## 왜 (스펙 035/036 의 빈틈)

- 스펙 035 forward-verdict 의 벤치마크는 *유니버스 균등 단순 보유*다 → "추세 ON 전략 vs 단순
  보유"는 답하지만, **"추세 필터 자체의 한계 기여"(같은 전략의 ON vs OFF)**는 격리 못 한다.
- 추세 필터의 효과를 알려면 교란변수(유니버스·가중치·주기 차이) 없는 대조군이 필요하다.

## 무엇을 (코드 변경 없이 격리)

- **대조군 설정** `deploy/canary-portfolio-notrend.toml` — `canary-portfolio.toml`(ON)과
  유니버스·가중치·top_n·rebalance_mode·invested_fraction·주기·lookback·momentum 까지 **전부
  동일**, 오직 `[portfolio.trend_filter]` 절만 없음. `test_canary_portfolio_config.py` 가 이
  동일성(추세 필터만 차이)을 회귀로 못박는다.
- **워크플로 2팔 재구성** `.github/workflows/rebalance-paper-forward.yml`:
  - Arm TREND-ON: `canary-portfolio.toml` + `data/forward_trend.db`.
  - Arm TREND-OFF: `canary-portfolio-notrend.toml` + `data/forward_notrend.db`.
  - 각 팔: `backfill-bars` → `rebalance-once --mode paper --construct-universe-top-n 15` →
    `nav-snapshot --snapshot` → `forward-verdict`. 사이드카 `LAST_RUN.md` 에 두 판정 나란히.
- **왜 코드 변경 0**: 페이퍼 체결(`ORDER_PAPER_FILLED`)·NAV(`PORTFOLIO_NAV_SNAPSHOT`)는 한 DB 의
  audit_log 에 쌓이고 nav-snapshot 은 그 DB 의 *모든* 페이퍼 체결을 재구성한다. **DB 파일을
  분리**하면 두 트랙이 섞이지 않는다 → portfolio_id 태깅·주문 경로 수정 불필요. `backfill-bars`
  가 빈 DB 를 자동 마이그레이션(`allow_apply=True`)하므로 별도 마이그레이션 단계도 없다.

## 안전 경계 (지킨 것)

- **Kernel 터치 0건, 코드 변경 0.** 주문 경로(order_router)·NAV 계산·감사 스키마 무변경.
- **돈 0 이동.** 양 팔 모두 `--mode paper`(가상 체결). 라이브 캐너리(`canary-live-rules.toml`)
  무관·무변경. 라이브 자동 승격 0건.

## 검증

- 전체 `uv run pytest`: **1478 통과, 4 스킵**. 신규 1건(대조군 동일성).
- 린트 `ruff check src tests`: All checks passed. 워크플로 YAML 유효(steps=7).

## 다음 세션이 이어받을 것

- **A/B 누적 관찰**: 두 DB 가 매 거래일 NAV 를 쌓는다. NAV 관측 ≥20(≈20 거래일)이면 두 판정이
  INSUFFICIENT_DATA 를 벗어나 ON vs OFF 비교가 의미를 가진다. 확인:
  `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md` 의 두 "🧭 판정" 섹션.
- **추세 필터의 진짜 가치는 드로다운**이므로 조용한 구간엔 ON≈OFF 가 정상(차이는 하락 구간에서
  벌어짐). 단기 비교로 성급히 결론 내지 말 것.
- **후속 후보**: ① 위험조정 지표를 **Calmar(연수익/최대낙폭)**까지 확장 — 추세추종의 드로다운
  방어를 Sharpe 보다 잘 포착(forward-verdict 보강). ② 판정 결과를 감사 이벤트로 스냅샷(시계열
  추적). ③ 더 많은 후보(룩백 길이·absolute_momentum vs sma)를 같은 토너먼트 틀로 확장.
