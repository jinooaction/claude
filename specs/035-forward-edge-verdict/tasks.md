# 스펙 035 — 작업 (tasks)

전부 완료. Kernel 터치 0건, 돈 0 이동.

- [x] **T01** 순수 판정 모듈 `portfolio/edge_verdict.py` — `daily_returns_from_curve`,
  `equal_weight_buy_hold_curve`(스펙 032 잣대), `forward_edge_verdict`(스펙 027 재사용),
  `EdgeVerdict` dataclass + `render_text`. (FR-V02, FR-V03, FR-V04)
- [x] **T02** `portfolio/__init__.py` 에 신규 공개 심볼 export.
- [x] **T03** 단위 테스트 `tests/unit/test_edge_verdict.py` — 수익률·벤치마크 빌더·세 판정·
  DSR 처벌·결정론·JSON (14건). (SC-V02~SC-V06)
- [x] **T04** 생산자 CLI `nav-snapshot` — fills 재구성 → 시세 mark → `compute_nav` →
  `--snapshot` 이면 `PORTFOLIO_NAV_SNAPSHOT` append. (FR-V01)
- [x] **T05** 소비자 CLI `forward-verdict` — NAV 시계열 + price_bars 벤치마크 → 판정 출력. (FR-V02~V04)
- [x] **T06** 통합 테스트 `tests/integration/test_forward_verdict_cli.py` — 생산자 행 기록,
  데이터 부족, 벤치마크 포함 EDGE_CONFIRMED 엔드투엔드, text, 누락 DB 오류 (5건). (SC-V01~V03)
- [x] **T07** 워크플로 `rebalance-paper-forward.yml` 배선 — `nav-snapshot --snapshot` 단계 +
  `forward-verdict` 단계 + 사이드카 `LAST_RUN.md` 판정·NAV 섹션. (FR-V05)
- [x] **T08** 전체 테스트(1453 통과·4 스킵)·린트(ruff All checks passed)·YAML 유효 확인.

## 검증 메모

- 전체 `uv run pytest`: 1453 passed, 4 skipped(라이브 KIS 게이트).
- 린트 `uv run ruff check src tests`: All checks passed.
- 엔드투엔드 시연(합성 NAV 25점 + 평벤치): 전략 샤프 > 벤치, 초과수익 >0, PSR 합격 →
  `EDGE_CONFIRMED`. 직선(노이즈 0) 입력은 보수적으로 `NO_EDGE`(설계 의도 — 불확실하면 미선언).
