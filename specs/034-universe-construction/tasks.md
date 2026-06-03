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
