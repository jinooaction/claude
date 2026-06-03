# 스펙 034 — 작업 목록

- [x] **T001** `strategy/universe.py` — `median_dollar_volume` / `liquidity_rank` /
  `select_universe` (결정론 Decimal, 비커널). (FR-U01·U02·U03)
- [x] **T002** 단위 테스트 13건 — 중앙값(홀/짝/이상치 무시/룩백/빈 바), 순위(내림차순/
  데이터부족 맨끝/동점 사전순), 구성(상위N/최소이력/최소유동성/결정론/빈집합). (SC-U01·U02·U03)
- [x] **T003** CLI `auto-invest build-universe` — 적재 데이터셋에서 유동성 상위 유니버스
  구성(text/JSON/TOML). 읽기 전용. (FR-U03)
- [x] **T004** `scripts/fetch_sp500_subset.py --all` — 전체 횡단면(약 505종목) 추출. (FR-U04)
- [x] **T005** 넓은 유니버스 설정 `sp500-broad-portfolio.toml` (유동성 상위 119, 합성 팩터). 
- [x] **T006** `portfolio-walk-forward` 표본 외 + DSR 검증 실행, 결과 `FINDINGS.md` 기록. (FR-U05·SC-U04)
- [x] **T007** 전체 테스트 + 린트 통과 확인 후 커밋·푸시·PR·자동 머지.

## 재발 차단 후속 (운영자 "둘 다 순서대로", 2026-06-03)

- [x] **T008** (1/2) 최근성 가드 코드 강제 — `recency.stale_guard` + `portfolio-walk-forward`·
  `backtest-portfolio` 가 stale 데이터를 `--allow-stale` 없이는 종료코드 70 으로 거부. 단위
  테스트 4건. (옛 데이터 백테스트로 전략 결론 내리는 재발을 도구가 차단)
- [x] **T009** (2/2) `build-universe` 를 현재 데이터 forward 페이퍼 경로에 배선 —
  `rebalance-once --construct-universe-top-n N`(현재 저장 바 기준 유동성 상위 N 으로 유니버스
  구성, 구성 결과 ⊆ 설정 유니버스 ⊆ 화이트리스트). `canary-portfolio.toml` 후보 28종목 확대 +
  `rebalance-paper-forward.yml` 에 `--construct-universe-top-n 15` 배선. CLI 통합 테스트 3건.
  **인스턴스 검증 남음**(현재 데이터·서버 접근 필요): 워크플로 실행 시 사이드카
  `automation/rebalance-paper-forward-last-run` 의 construct-universe 줄 확인.
