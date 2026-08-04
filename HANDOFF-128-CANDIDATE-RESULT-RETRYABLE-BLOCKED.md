# HANDOFF-128 — Candidate Result Retryable Blocked Diagnostics

## 상태

완료. #571이 main에 merge됐고, post-merge `candidate-implementation-results` sidecar가 새 코드로 실제 실행됐다.

운영자 질문에 대한 결론은 이렇다. 엣지 신뢰도(PSR)를 높이면 자본 사다리의 첫 배치 문제는 풀릴 수 있다. 하지만 기준을 낮추거나 같은 증거를 다시 포장해 숫자를 올리는 방식은 안전한 해결이 아니다. 새 forward 증거 또는 더 나은 후보 전략이 엄격한 검증을 통과해야 한다.

## 왜 했나

최신 돈 경로는 `PREVIEW_ONLY`/`NO_EDGE_YET`다. 자본 사다리 PSR은 `0.703355 < 0.95`이고, 최신 forward 토너먼트에서 기준에 가장 가까운 `globalfixed` 후보도 `0.922697 < 0.95`다.

즉 지금 실주문이 안 나가는 직접 이유는 서버나 KIS가 아니라 엣지 신뢰도 부족이다. 자본 배치를 안전하게 열려면 우연이 아닌 성과 증거가 더 필요하다.

동시에 후보 구현 공장은 PSR을 높일 수 있는 후보 패키지 2개를 이미 만들고 있었다. 그런데 후보 결과 실행기는 패키지 상태가 `blocked`이면 곧바로 멈췄다. 패키지가 retryable이고 안전한 no-live 검증 명령을 갖고 있어도 실행하지 않았기 때문에, 자동화는 `blocked`라는 큰 라벨만 반복해서 보고 진짜 다음 원인을 좁히지 못했다.

## 무엇을 고쳤나

- `src/auto_invest/analytics/candidate_result_executor.py`가 unsafe command 검사를 먼저 한다.
- `promotion_patch.factory_retryable == True` 또는 retryable factory diagnostic이 붙은 blocked 패키지는 안전 allowlist를 통과한 no-live 검증 명령을 실행한다.
- non-retryable blocked 패키지는 그대로 blocked다.
- unsafe command, unsupported command, missing command도 그대로 blocked다.
- 후보를 pass로 위조하지 않는다. 명령이 데이터 부족으로 실패하면 `pending`과 retryable diagnostic으로 남긴다.

## 확인한 증거

- PR #571 merge commit: `5d181e743bdae0b23486450d6c7feb304ec321e7`.
- 기능 커밋: `a99ac8e`.
- 최신 `rebalance-paper-forward` sidecar: commit `530f0f3`, timestamp `2026-08-03T23:39:40Z`, 7개 트랙 모두 `NO_EDGE`.
- 최신 후보 수치: `globalfixed` PSR `0.922697 < 0.95`, `global` PSR `0.706071`, `multiasset` PSR `0.746206`.
- 최신 `money-path` sidecar: timestamp `2026-08-03T21:37:56Z`, `PREVIEW_ONLY`/`NO_EDGE_YET`, NAV `$1466.62`, 배치 자본 `$0`, 자본 사다리 PSR `0.703355 < 0.95`.
- post-merge `candidate-implementation-factory` sidecar: commit `5d181e7`, timestamp `2026-08-04T01:10:21Z`, blocked packages 2개.
- post-merge `candidate-implementation-results` sidecar: commit `5d181e7`, timestamp `2026-08-04T01:10:24Z`, `overall_status=degraded`, `pass=0`, `fail=0`, `pending=2`, `blocked=0`.
- 결과 진단 집계: `data_history_missing=2`, `execution_failed=1`.
- 후보 `candidate-1ed634d8bf6d`: `portfolio-walk-forward`가 실행됐고 exit 64, `no ingested datasets; run auto-invest ingest-history`.
- 후보 `candidate-cc96b35062da`: `portfolio-walk-forward`가 실행됐고 exit 64, `no ingested datasets; run auto-invest ingest-history`.
- 로컬 검증: focused candidate-result tests 13 passed, 관련 후보 공장/통합 tests 26 passed, `uv run pytest -q` 2712 passed/5 skipped, `uv run ruff check src tests` 통과, `agent_harness_probe.py --strict` OK(14/14), `check_handoff_facts.py` OK, PR quality gate 통과.

## 안전 경계

이번 변경은 no-live 운영 자동화 진단 복구다.

실제 주문, 실거래 전환, live 재무장, 자본 배분, live 전략 설정, whitelist/caps, 손실 예산, KIS secret, 감사 로그, 헌법, kernel manifest는 바꾸지 않았다.

후보 결과 실행기가 돌린 명령은 allowlist 안의 검증 명령이다. 브로커 API, 주문 라우터 live 확정, 자본 사다리 상태 변경, 실거래 sentinel 변경은 하지 않는다.

## 다음 세션 판단

PSR 부족이 직접 blocker라는 판단은 유지한다. 다만 이번 세션에서 PSR을 직접 올린 것은 아니다. 기준 완화나 과적합 없이 PSR을 올릴 수 있는 후보 검증 경로를 막고 있던 운영 병목을 닫았다.

다음 실제 작업은 `data_history_missing`을 없애는 것이다. 안전한 과거 가격 데이터 준비 또는 `ingest-history` 실행 경로를 만들어 pending 후보 2개의 walk-forward 검증을 pass/fail 증거로 바꿔야 한다.

그 전에는 live 전략 지문을 바꾸지 않는다. 기존 라이브 검증 지문을 덮으면 누적 forward 증거가 리셋되고, 자본 사다리는 어떤 단에서도 자본을 배치하지 않는다.
