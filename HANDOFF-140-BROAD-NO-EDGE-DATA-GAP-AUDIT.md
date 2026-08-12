# HANDOFF-140 — Broad No-Edge Data Gap Audit Contract

## 상태

#603이 main에 merge되어 `candidate-broad-no-edge-data-gap-audit`가 스펙 133으로 완료됐다. 이 작업은 돈을 움직이는 패치가 아니라, `NO_EDGE_YET` 상태에서 공개 데이터 결측과 전략 성과 판정을 분리하는 no-live 운영 계약이다.

핵심 결론은 이렇다. 광역 no-edge frontier에서 자산군 확장, 다중 보유 기간·신호군, 레짐·비용 견고성, 데이터 결측 원인 감사 네 축은 모두 released 상태가 됐다. 자동 실행 루프의 현재 선택은 `wait-for-fresh-evidence`이고, 실행 가능한 안전 후보는 없다. 실주문, live 재무장, 자본 배분은 여전히 금지다.

## 왜 했나

레짐·비용 견고성 후보까지 닫힌 뒤 남은 질문은 "NO_EDGE가 정말 전략 실패인가, 아니면 데이터 결측 때문에 판정이 흐려진 것인가"였다. 안전한 해결은 엣지 기준을 낮추는 것이 아니다.

`public-data` summary, `regime.json`, `regime_timeline.csv`, `regime-stratify`, `rebalance-paper-forward`, `money-path`, `edge-autoarm`, `released-work`, `pipeline-liveness`를 함께 읽어 결측 원인과 NO_EDGE 영향을 기계 판독 가능한 보고서로 남기는 것이다.

## 무엇을 고쳤나

- `specs/133-broad-no-edge-data-gap-audit/` SDD 산출물을 추가했다.
- `src/auto_invest/analytics/broad_no_edge_data_gap_audit.py`가 데이터 결측 감사 no-live 계약을 JSON/Markdown으로 만든다.
- `scripts/broad_no_edge_data_gap_audit_probe.py`가 sidecar 입력을 받아 계약을 발행한다.
- `tests/unit/test_broad_no_edge_data_gap_audit.py`와 `tests/integration/test_broad_no_edge_data_gap_audit_probe.py`가 CPI 결측, 레짐 지표 결측, timeline 품질, money gate 정렬, CLI 출력을 고정한다.
- `tests/unit/test_autonomous_work_execution.py`가 데이터 결측 감사 후보 released 뒤 broad no-edge frontier가 모두 released가 되고 `wait-for-fresh-evidence`로 넘어가는 회귀를 고정한다.
- `completed_candidate_id: candidate-broad-no-edge-data-gap-audit` 완료 마커와 완료된 `tasks.md` 덕분에 released-work가 이번 후보를 소비한다.
- `.specify/feature.json`과 `CLAUDE.md`는 최신 완료 스펙 133을 가리킨다.

## 확인한 증거

- PR #603: `https://github.com/jinooaction/claude/pull/603`.
- 기능 커밋: `28ca5fa`.
- merge commit: `4d39fe8d6b12f6176b22153ef4ec06aa248f7c36`.
- GitHub PR quality gate: run `31605904257`, success.
- deploy-on-merge run: `31605944286`, commit `4d39fe8`, success. 컨테이너에서 Actions run success는 확인했지만 서버 audit_log는 운영자 또는 서버 접근 표면에서만 확인할 수 있다.
- released-work run: `31605944297`, commit `4d39fe8`, released_count 52, 스펙 133 후보 released 포함.
- autonomous-work run: `31605944292`, commit `4d39fe8`, selected_work `wait-for-fresh-evidence`, status `OBSERVATION_WAIT`.
- 최신 data-gap sidecar 재현: `CONTRACT_READY`, completed candidate `candidate-broad-no-edge-data-gap-audit`, next candidate `wait-for-fresh-evidence`, release gate PASS.
- 결측 증거: CPI `CUUR0000SA0`은 `GAP_DETECTED`/`MEDIUM`, inflation 지표는 `UNAVAILABLE`/`MEDIUM`, timeline 2399행, canonical label 누락 없음, `inflation_yoy` 100% 결측.
- NO_EDGE 문맥: stratified sparse label 2개(`GLOBAL-TREND:RISK_OFF`, `GLOBAL-TREND-WIDE:RISK_OFF`), forward paper NO_EDGE 행 7개.
- 로컬 focused 검증: 11 passed, 48 deselected.
- 로컬 전체 검증: `uv run pytest` 2777 passed, 5 skipped.
- 로컬 린트: `uv run ruff check src tests` 통과.
- 기타 검증: `git diff --cached --check` 통과, `uv run python scripts/check_handoff_facts.py` OK, `uv run python scripts/agent_harness_probe.py --strict` OK(14/14), PR quality gate 통과.

## 안전 경계

이번 변경은 등급 2 운영 보정이다.

브로커 API 호출, 실제 주문, 실거래 전환, live 재무장, 자본 배분, 라이브 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

`money-path`는 여전히 `PREVIEW_ONLY` / `NO_EDGE_YET`이고, edge-autoarm은 `WAIT_EDGE` / `NO_EDGE`다. 실거래는 기존 엣지 확정과 운영자 승인 경계 없이는 열리지 않는다.

## 다음 세션 판단

현재 최신 autonomous-work selected_work는 `wait-for-fresh-evidence`다. 실행 가능한 안전 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없다.

다음 세션은 새 코드 후보를 만들기 전에 scheduled sidecar가 새로 쌓였는지 확인한다. 새 증거가 생기면 released-work와 autonomous-work를 다시 읽어 `EXECUTION_READY` 후보가 생겼는지 판단한다.

주문 제출, live 재무장, 자본 배분은 하지 않는다. 현재 돈 경로는 여전히 `PREVIEW_ONLY`/`NO_EDGE_YET`이다.
