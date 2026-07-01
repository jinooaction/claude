# HANDOFF 078 — 후보 가격 이력 지원과 승격 실패 반영 (2026-07-01 KST)

main 베이스라인: `fcc6e5f`(PR #425). 스펙 074는 남은 전략/포트폴리오 후보 2개의
`data_history_missing` 대기를 없애기 위해, 후보 결과 실행기가 가격 이력을 준비하고
`portfolio-walk-forward`에 `--history-root`를 넘기게 했다.

## 무엇이 바뀌었나

- `src/auto_invest/analytics/candidate_history_support.py`
  - 후보 검증용 가격 이력 dataset manifest를 단일 출처로 추가했다.
  - micro GTAA, global trend wide, multi-asset trend의 portfolio/db/history-root를 명시한다.
- `scripts/candidate_history_support_probe.py`
  - workflow가 읽는 TSV manifest와 로컬 확인용 JSON 출력을 제공한다.
- `src/auto_invest/analytics/candidate_factory.py`
  - 전략/포트폴리오 후보 명령에 `--history-root /tmp/candidate_result_history/.../hist`를 붙인다.
- `.github/workflows/candidate-result-executor.yml`
  - SSH key가 있을 때 서버 `/opt/auto-invest`에서 read-only `bars-export`와 `ingest-history`를 실행한다.
  - 생성된 `/tmp/candidate_result_history`를 runner로 가져와 후보 검증 패키지에 제공한다.
  - SSH key가 없으면 통과로 위조하지 않고 기존처럼 후보를 pending/degraded로 남긴다.
- follow-up 브랜치 `Codex/075-promotion-factory-result-state`
  - `promotion_loop.py`가 전략/포트폴리오 공장 결과 `blocked/fail`을 다시 `BACKTEST_REQUIRED`로
    반복하지 않고 `DISCARD`로 분류하게 보정한다.

## 운영상 의미

- 스펙 073 뒤 남은 pending 2개의 공통 원인인 `data_history_missing`은 제거됐다.
- 두 후보는 이제 "데이터가 없어서 판단 못 함"이 아니라 "가격 이력을 넣어 검증했지만 no-edge/fail"이다.
- 자동 루프는 이 실패를 pass로 위조하지 않는다.
- 전략/포트폴리오 후보는 `historical_backtest`, `recent_oos`, `walk_forward`가 모두 pass일 때만
  forward 등록 후보가 된다.

## 배포 후 실제 실행 증거

- `Deploy on merge to main` run `28503224288`: success, commit
  `fcc6e5f5e9aef7a659016c5ecce5546a0294e00c`
- main push 직후 result executor run `28503224265`: success였지만, factory sidecar 경합 때문에
  이전 패키지를 읽어 `pending=2`를 유지했다.
- 최신 패키지 기준으로 재실행한 `Candidate result executor` run `28503338531`: success
- 최신 result executor summary:
  - `overall_status=degraded`
  - `pass=7`, `fail=2`, `pending=0`, `blocked=0`
  - `diagnostic_counts={}`
  - `candidate-1ed634d8bf6d`: fail, `--history-root` 포함
  - `candidate-cc96b35062da`: fail, `--history-root` 포함
- result sidecar 뒤 재실행한 `Candidate implementation factory` run `28503561736`: success
- 최신 factory summary:
  - `evidence_passed=7`, `blocked=2`, `pending=0`, `ready=0`

## 후보별 현재 상태

- `candidate-1ed634d8bf6d` strategy_backtest
  - 이전 상태: `data_history_missing`, `insufficient_pass_evidence`
  - 현재 상태: factory `blocked`
  - 의미: 가격 이력은 준비됐지만 기계 판독 백테스트 결과가 실패라 승격 증거로 병합하지 않는다.
- `candidate-cc96b35062da` portfolio_backtest
  - 이전 상태: `data_history_missing`
  - 현재 상태: factory `blocked`
  - 의미: 가격 이력은 준비됐지만 포트폴리오 검증 결과가 실패라 승격 증거로 병합하지 않는다.
- 비전략 후보 7개
  - 현재 상태: `evidence_passed`
  - 의미: no-live 운영/데이터/분석 검증은 통과했지만 전략/포트폴리오 후보가 아니므로 forward paper 등록 대상은 아니다.

## 후속 루프 검증

- `Candidate result executor` run `28503338531`: success, commit `fcc6e5f`
- `Candidate implementation factory` run `28503561736`: success, commit `fcc6e5f`
- `Autonomous promotion loop` run `28503609658`: success, commit `fcc6e5f`
- main 기준 promotion loop는 아직 factory `blocked`를 `BACKTEST_REQUIRED`로 보여준다.
  follow-up 패치는 최신 sidecar smoke에서 두 후보를 `DISCARD`로 분류하는 것을 확인했다.

## 안전 경계

- 위험 등급: 2(운영 자동화 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 비밀값, 감사 로그 변경: 없음
- 서버 `bars-export`와 `ingest-history`는 가격 이력 준비용 read-only 실행이다.
- `Backtest -> Canary -> Full` 순서는 유지된다.
- 최신 KIS smoke sidecar는 run `28500268994`, commit `f9f8908`, `smoke_state=success`,
  `key_valid=true`다. #425와 같은 commit의 직접 smoke는 아니므로 배포 성공의 직접 증거로 쓰지 않는다.

## 검증

PR #425 머지 전:

- `uv run pytest tests/unit/test_candidate_history_support.py -q` -> 3 passed
- `uv run pytest tests/unit/test_candidate_factory.py tests/unit/test_candidate_result_executor.py -q` -> 18 passed
- `uv run pytest tests/integration/test_candidate_result_executor_probe.py -q` -> 3 passed
- synthetic history smoke -> `pass=0`, `fail=2`, `pending=0`, `blocked=0`, `diagnostic_counts={}`
- `uv run pytest` -> 2362 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `git diff --check` -> OK
- Ruby YAML parse for `candidate-result-executor.yml` -> OK
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success, mergeable, merge 방식으로 main에 병합

follow-up 보정 전:

- `uv run pytest tests/unit/test_promotion_loop.py -q` -> 12 passed
- 최신 sidecar local promotion smoke -> 두 전략/포트폴리오 후보가 `DISCARD`
- `uv run pytest tests/unit/test_promotion_loop.py tests/integration/test_promotion_loop_probe.py tests/unit/test_candidate_factory.py -q`
  -> 23 passed
- `uv run ruff check src/auto_invest/analytics/promotion_loop.py tests/unit/test_promotion_loop.py`
  -> All checks passed

## 다음 세션 한 줄

가격 이력 부족은 해결됐다. 남은 두 전략/포트폴리오 후보는 백테스트 실패 후보이므로,
승격하지 말고 재설계 또는 학습 장부로 보내는 promotion loop 보정을 머지한 뒤 handoff를 다시 갱신한다.
