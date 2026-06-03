# HANDOFF 040 — 스펙 035: forward 엣지 자동 판정 폐회로 (2026-06-03)

main 머지 `9bfa55d`(PR #165). Kernel 터치 0건, 돈 0 이동. 운영자 지시: "세계 최고 수준이
되기 위한 작업 분석·우선순위 판단 뒤 자율 수행 — 결국 실제로 돈을 버는 게 중요하다."

## 한 줄 요약

이 시스템에서 **"실제로 돈을 버는가"를 판정하는 폐회로가 끊겨 있던 것**을 연결했다. 이제 매
forward 페이퍼 실행마다 시가평가 순자산(NAV)을 기록하고, 쌓인 시계열을 **단순 보유 벤치마크와
비교 + 디플레이티드 샤프로 우연·과적합 처벌**해 `EDGE_CONFIRMED / NO_EDGE / INSUFFICIENT_DATA`
한 줄 판정을 자동으로 낸다.

## 왜 이게 최우선이었나 (우선순위 판단 근거)

- 알파 도구(팩터·최적화기·재조정)와 검증 도구(워크포워드·디플레이티드 샤프·거래비용·체결품질)는
  이미 세계 최고 수준급으로 많다(31,000줄·테스트 1,400건+).
- 그런데 **돈 버는지 판정할 토대 3개가 끊겨 있었다**:
  1. 스펙 029 `compute_nav`(시가평가 순자산)·`read_nav_points`(시계열)는 만들어졌고 테스트도
     됐지만 **어떤 CLI·실행 경로에도 안 꽂혀** NAV 시계열이 아무 데서도 기록되지 않았다 →
     "시간상 미래에 돈을 벌었는가"를 잴 입력 자체가 없었다.
  2. 디플레이티드 샤프(스펙 027)는 백테스트(`portfolio-walk-forward`)에만 연결, **forward
     트랙엔 미적용.**
  3. forward 트랙(`rebalance-paper-forward.yml`)은 체결만 쌓고(`fills_count`만 증가) 판정을
     안 했다. "단순 보유를 이기는, 우연 아닌 엣지인가"가 산문 TODO 로 남아 있었다.
- 이건 이 프로젝트의 반복 실패 패턴(도구는 만들고 실제 경로엔 안 꽂힘)의 가장 비싼 사례다.
  **돈을 버는지 자체를 판정할 수 없으면 세계 최고 수준은 불가능하다.** 그리고 검증 데이터가
  컨테이너에 없는데 새 알파를 또 만드는 건 함정(검증 못 한 기계만 늘림) → **가장 레버가 큰 일은
  이 폐회로를 잇는 것.**

## 무엇을 만들었나

- **순수 판정 모듈** `src/auto_invest/portfolio/edge_verdict.py`
  - `daily_returns_from_curve` — 자산곡선 → 기간별 수익률(0/비양수 방어).
  - `equal_weight_buy_hold_curve` — 같은 NAV 일자 격자에서 유니버스 균등가중 단순 보유 곡선
    (스펙 032 `_benchmark_equity_curve` 와 같은 잣대, `price_bars` 기반).
  - `forward_edge_verdict` — 전략 NAV(+옵션 벤치마크) → 연율 샤프·PSR·DSR·MinTRL(스펙 027
    `significance.py` 재사용) + 총수익·낙폭(스펙 008 `metrics.py` 재사용) → `EdgeVerdict`.
  - `EdgeVerdict` dataclass(`to_json_dict`) + `render_text`.
- **생산자 CLI** `auto-invest nav-snapshot`
  - fills 재구성(`reconstruct`) → 장부 보유 → 현재 KIS 시세 mark(`_fetch_marks` 재사용) →
    `compute_nav`(스펙 029) → `--snapshot` 이면 `PORTFOLIO_NAV_SNAPSHOT`(K4 추가-전용) append.
  - 기본은 순수 계산(미기록), read-only. 시세 실패는 평균단가 폴백(거래 무중단).
  - **스펙 029 `compute_nav` 를 처음으로 실행 경로에 배선한 명령**(끊겨 있던 생산자).
- **소비자 CLI** `auto-invest forward-verdict`
  - `read_nav_points`(스펙 029) → 전략 NAV 곡선. `--portfolio` 유니버스 + `price_bars` →
    단순 보유 벤치마크. `forward_edge_verdict` → 판정(text/json).
- **워크플로 배선** `.github/workflows/rebalance-paper-forward.yml`
  - 재조정 뒤 `nav-snapshot --snapshot`(생산자) 단계, bars-status 뒤 `forward-verdict`(소비자)
    단계 추가. 사이드카 `LAST_RUN.md` 에 "🧭 forward 엣지 판정" + "시가평가 NAV 스냅샷" 섹션 +
    요약표 ssh_exit 2행. **매 실행 라이브 판정이 찍힌다.**

## 판정 규칙 (전부 만족해야 EDGE_CONFIRMED)

1. 관측 ≥ `min_obs`(기본 20) — 아니면 INSUFFICIENT_DATA.
2. 초과수익 > 0 **그리고** 전략 샤프 > 벤치 샤프 — 단순 보유를 위험조정으로 이김.
3. PSR(벤치 샤프 기준) ≥ 임계치(기본 0.95) — 우연과 구별됨.
4. 시도 > 1 이면 DSR ≥ 임계치 — 다중검정/과적합 보정 후에도 살아남음.

하나라도 미달이면 `NO_EDGE`. 관측 부족·분산 0·통계 불가면 보수적으로 `INSUFFICIENT_DATA`.
**모르면 EDGE 선언 금지** = 돈을 잃지 않게 막는 헌법 X 의 직접 구현.

## 안전 경계 (지킨 것)

- **Kernel 터치 0건.** `compute_nav`·`read_nav_points`·`significance`·`price_bars` 리더·
  `_fetch_marks` 를 재사용만. `risk/gates.py`·캡·whitelist·워커·감사 스키마 무변경.
- **돈 0 이동.** NAV 스냅샷 = 읽기 전용 측정(주문 0건), 판정 = 순수 분석, 워크플로 = PAPER 전용.
- **라이브 자동 승격 0건.** EDGE_CONFIRMED 는 운영자 라이브 게이트(헌법 X.4 / 스펙 026)에 올릴
  *증거*일 뿐 자동 배포 아님. 자율 튜너는 이 판정으로 라이브 못 켬(헌법 IX.B-2 불변).

## 검증

- 전체 `uv run pytest`: **1453 통과, 4 스킵**(라이브 KIS 게이트). 신규 19건:
  - 단위 `tests/unit/test_edge_verdict.py` 14건(수익률·벤치마크 빌더·세 판정·DSR 처벌·결정론·JSON).
  - 통합 `tests/integration/test_forward_verdict_cli.py` 5건(생산자 행 기록·데이터 부족·벤치마크
    포함 EDGE_CONFIRMED 엔드투엔드·text·누락 DB 오류).
- 린트 `uv run ruff check src tests`: **All checks passed!**. 워크플로 YAML 유효.
- 엔드투엔드 시연(합성 NAV 25점·작은 잡음 vs 평벤치·큰 잡음): 전략 샤프>벤치·초과수익>0·PSR
  합격 → **EDGE_CONFIRMED**. (노이즈 0 직선 입력은 보수적으로 NO_EDGE — 설계 의도.)

## 다음 세션이 이어받을 것

- **인스턴스에서 자동 진행**: `rebalance-paper-forward.yml` 가 매 거래일 돌며 NAV 점을 쌓는다.
  확인: `git show origin/automation/rebalance-paper-forward-last-run:LAST_RUN.md` 의 "forward
  엣지 판정" JSON. 지금은 관측 부족 → INSUFFICIENT_DATA. 충분히 쌓이면 **코드 수정 없이** 진짜
  판정으로 자동 전환된다.
- **EDGE_CONFIRMED 가 나오면** 그게 운영자 라이브 게이트(헌법 X.4 / 스펙 026 승격)에 올릴 첫
  *증거*다 — 자동 배포가 아니라 운영자 결정 입력.
- **후속 정밀화 후보**: ① 시간가중수익(큰 자본 투입/인출 시 NAV 기반 수익률 왜곡 보정). ②
  `forward-verdict --num-trials`/`--trial-sharpe-std` 를 튜너가 시도한 설정 개수로 자동 채우기.
  ③ growth(`compute_growth`)·verdict 를 한 리포트로 합치기. ④ 판정 결과 자체를 감사 이벤트로
  스냅샷(시계열 추적).
