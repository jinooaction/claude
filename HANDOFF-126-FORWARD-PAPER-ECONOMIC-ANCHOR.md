# HANDOFF-126 — Forward Paper Economic Anchor

## 상태

완료. #566이 forward paper 리밸런서의 종이거래 보유 인식 오류를 고쳤고, post-merge 배포와 forward/money-path/capital-path sidecar 재관측까지 성공했다.

## 왜 했나

돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`라 실주문을 막고 있었다. 그런데 최신 `rebalance-paper-forward`는 성공처럼 보이면서도 종이 장부가 경제적으로 깨져 있었다.

원인은 종이 리밸런서가 현재 보유를 `current_positions`에서만 읽은 것이다. 종이 주문 라우터는 실제 브로커 보유 테이블을 쓰지 않고 `ORDER_PAPER_FILLED` 감사 로그만 남긴다. 그래서 다음 실행 때 리밸런서가 이전 종이 보유를 0으로 착각했고, 목표를 다시 사면서 종이 장부 현금이 크게 음수로 왜곡됐다.

## 무엇을 고쳤나

- `src/auto_invest/execution/rebalancer.py`에 paper-only 보유 재구성 경로를 추가했다.
- paper mode에서는 감사 로그의 `ORDER_PAPER_FILLED`를 `performance.engine.reconstruct`로 되살려 현재 가상 보유로 쓴다.
- 종이 fill이 전혀 없는 경우에는 기존 `current_positions` fallback을 유지해 테스트와 수동 시드 사용을 깨지 않게 했다.
- live/non-paper 경로와 명시적 `account_holdings` 입력은 바꾸지 않았다.
- `tests/integration/test_spec_032_live_rebalancer.py`에 같은 DB에서 두 번 paper rebalance를 돌려도 같은 매수를 반복하지 않는 회귀 테스트를 추가했다.

## 확인한 증거

- PR #566 merge commit: `f15f87da11c99583488de06f2387dc9b1dca75ab`.
- 기능 커밋: `3db894022e7637a641290b5c1498c8987b00245f`.
- Deploy on merge run `30674990967`: success.
- Rebalance forward paper validation run `30675023375`: success. 최신 sidecar timestamp `2026-08-01T00:17:37Z`, commit `f15f87da11c99583488de06f2387dc9b1dca75ab`, 7개 트랙 prep/verdict `ssh_exit=0`.
- 최신 forward sidecar는 `planned_buy_notional_usd=0.00`과 여러 `SELL`/`PAPER_FILLED`를 남긴다. 예전처럼 보유를 0으로 보고 다시 사는 병목은 닫혔다.
- Money-path run `30675222849`: success. commit `f15f87d`, timestamp `2026-08-01T00:19:07Z`, `PREVIEW_ONLY`/`NO_EDGE_YET`.
- Capital path readiness run `30675223926`: success. commit `f15f87d`, timestamp `2026-08-01T00:19:09Z`, `ACCUMULATING_EDGE`, 우선 후보 없음.
- #566 브랜치 검증: focused rebalancer tests 9 passed, adjacent tests 81 passed, `uv run pytest -q` 2707 passed/5 skipped, `uv run ruff check src tests` 통과, `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, `git diff --check` 통과, PR quality gate 통과.

## 안전 경계

실제 주문, live 재무장, 자본 배분, whitelist/caps 확대, 손실 예산 변경, KIS secret, 감사 로그 삭제, 헌법, kernel manifest는 바꾸지 않았다. 이 변경은 종이거래 경제 장부를 바로잡는 관측 보정이다.

## 다음 세션 판단

forward paper 장부가 이전 보유를 잊고 반복 매수하던 병목은 닫혔다. 다만 과거 반복 매수로 생긴 음수 현금은 per-trade cap 때문에 한 번에 사라지지 않고 여러 실행에 걸쳐 정리될 수 있다.

돈 경로가 열린 것은 아니다. 최신 money-path는 `PREVIEW_ONLY`/`NO_EDGE_YET`, capital-path-readiness는 `ACCUMULATING_EDGE`, 우선 후보 없음이다. 다음 세션은 먼저 최신 sidecar를 fetch해서 `NO_EDGE`가 바뀌었는지 확인하고, 실주문·재무장·자본 배분은 안전 게이트를 우회하지 않는다.
