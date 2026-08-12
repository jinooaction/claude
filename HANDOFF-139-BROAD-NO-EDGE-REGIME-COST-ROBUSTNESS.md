# HANDOFF-139 — Broad No-Edge Regime Cost Robustness Contract

## 상태

#601이 main에 merge되어 `candidate-broad-no-edge-regime-cost-robustness-experiment`가 스펙 132로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 레짐 취약 구간과 비용 민감도를 한 번에 읽는 no-live 운영 계약이다.

핵심 결론은 이렇다. 광역 no-edge frontier에서 자산군 확장, 다중 보유 기간·신호군, 레짐·비용 견고성 세 축은 released 상태가 됐다. 자동 실행 루프의 다음 후보는 `candidate-broad-no-edge-data-gap-audit`이고, 해야 할 일은 공개 데이터 범위·조인·레짐 라벨 결측이 no-edge 판정에 끼친 영향을 읽기 전용 감사 계약으로 분리하는 것이다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

스펙 131은 같은 보유 기간과 같은 신호군을 반복하지 않도록 후보 폭을 넓혔다. 하지만 레짐 전환이나 비용·슬리피지에 약하면 paper 성과가 좋아 보여도 실제 돈 경로로 올라갈 수 없다.

안전한 해결은 엣지 신뢰도 기준을 낮추는 것이 아니다. `regime-stratify`, `execution-quality`, `money-path`, `edge-autoarm`, `rebalance-paper-forward`, `released-work`, `evolution-ledger`, `pipeline-liveness`를 함께 읽어 레짐별 PASS/WAIT/STRESS와 10/25/50bp 비용 민감도 행을 기계 판독 가능한 no-live 계약으로 남기는 것이다.

## 무엇을 고쳤나

- `specs/132-broad-no-edge-regime-cost-robustness/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_regime_cost_robustness.py`가 레짐·비용 견고성 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_regime_cost_robustness_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_regime_cost_robustness.py`와 `tests/integration/test_broad_no_edge_regime_cost_robustness_probe.py`가 계약 상태, 레짐 라벨 판정, 비용 민감도 행, 안전 경계, CLI 출력을 고정한다.
- `tests/unit/test_autonomous_work_execution.py`가 레짐·비용 후보 released 뒤 다음 broad no-edge 후보가 `candidate-broad-no-edge-data-gap-audit`로 전진하는 회귀를 고정한다.
- `completed_candidate_id: candidate-broad-no-edge-regime-cost-robustness-experiment` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 132를 가리킨다.

## 확인한 증거

- PR #601: `https://github.com/jinooaction/claude/pull/601`.
- 기능 커밋: `f0c5cee`.
- merge commit: `15719d8438dea3893dfde83f7850a9f336d35866`.
- GitHub PR quality gate: run `31595802762`, success.
- deploy-on-merge run: `31596002457`, commit `15719d8`, success. 컨테이너에서 Actions run success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- released-work run: `31596002387`, commit `15719d8`, released_count 51, 스펙 132 후보 released 포함.
- autonomous-work run: `31596002386`, commit `15719d8`, selected_work `candidate-broad-no-edge-data-gap-audit`, status `EXECUTION_READY`, risk_grade 2.
- 최신 regime-cost sidecar 재현: `CONTRACT_READY`, regime window 2개, label 6개, stress label 2개, wait label 2개, 비용 stress 행 10/25/50bp, release gate PASS.
- local released-work/autonomous-work 재현: 스펙 132 후보 released, broad no-edge frontier map에서 asset-universe, multi-horizon, regime-cost는 released, data-gap-audit은 open, 다음 selected_work는 `candidate-broad-no-edge-data-gap-audit`.
- 로컬 focused 검증: 14 passed, 46 deselected.
- 로컬 전체 검증: `uv run pytest` 2769 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `candidate-broad-no-edge-data-gap-audit`다.

다음 작업은 `public-data` summary, `regime.json`, `regime_timeline.csv`를 읽어 데이터 결측 원인이 no-edge 판정에 끼친 영향을 분리하는 읽기 전용 감사를 정의하는 것이다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
