# HANDOFF-116 — 스펙 117 `SUBMISSION_UNKNOWN` broker lookup 복구

## 한 줄 결론

스펙 117은 주문 제출 응답 유실로 남은 `SUBMISSION_UNKNOWN` 주문을 재주문하지 않고, KIS `inquire-ccnl` 읽기 전용 조회에서 단일 강한 일치가 있을 때만 broker order id를 복구하도록 main에 들어갔다.

## 기준 상태

- 기준 `main`: `8fd6b90b7c0003104065b88ba0149e0002254953` — PR #521 스펙 117 머지
- 기능 커밋: `69fad52e7770e9df1f2f455071c4bdb9e5864471`
- 확인 시점: 2026-07-13 KST
- 돈 경로: 계속 `PREVIEW_ONLY`
- 실제 주문·취소·실거래 전환: 수행하지 않음
- live sentinel, capital, whitelist, caps, loss budget, 헌법, kernel manifest, 비밀값: 변경 없음

## 해결한 실패 모드

스펙 112는 주문 `POST` 자동 재시도를 제거하고 불명확 실패를 `SUBMISSION_UNKNOWN`으로 남겼다. 스펙 115는 unresolved BUY가 신규 BUY를 막게 했다. 하지만 그 상태를 자동으로 확인해 해소하는 broker lookup 복구 경로는 없었다.

이제 `sync_fills`는 열린 `SUBMITTED` 주문이 없어도 unresolved `SUBMISSION_UNKNOWN` 주문이 있으면 KIS `inquire-ccnl`을 조회한다. 조회 결과에서 다음 조건을 모두 만족하는 broker order id가 정확히 하나일 때만 회복한다.

1. symbol이 같다.
2. broker side가 있으면 local side와 같다.
3. `filled_qty == local qty`이거나, `unfilled_qty`가 있고 `filled_qty + unfilled_qty == local qty`다.
4. 같은 broker order id가 다른 unknown 주문에도 걸치지 않는다.

회복되면 `orders.kis_order_id`, `orders.submitted_at_utc`, `order_routing`을 채우고 `SUBMISSION_UNKNOWN -> SUBMITTED` 전이를 남긴다. 같은 broker evidence는 기존 fill planner로 이어져 `FILL`, `PARTIALLY_FILLED`, `FILLED`, `EXPIRED`를 처리한다.

## 실패 시 동작

- broker match가 없으면 그대로 `SUBMISSION_UNKNOWN`이다.
- 후보가 여러 개면 그대로 `SUBMISSION_UNKNOWN`이다.
- broker 조회가 실패하면 `ERROR` 감사만 남기고 주문 상태를 바꾸지 않는다.
- unresolved `SUBMISSION_UNKNOWN` BUY는 계속 degraded execution state를 만들어 신규 BUY를 막는다.

## 검증

- 구현 전 focused regression: `uv run pytest tests/integration/test_fill_sync.py -q -k "submission_unknown"` → 4 failed. 기존 코드는 `SUBMISSION_UNKNOWN`만 있을 때 `inquire-ccnl`을 호출하지 않았다.
- 구현 후 focused regression: 같은 명령 → 4 passed.
- 전체 fill sync: `uv run pytest tests/integration/test_fill_sync.py -q` → 13 passed.
- 인접 검증: `uv run pytest tests/integration/test_worker_fill_sync.py tests/integration/test_worker_order_lifecycle.py tests/integration/test_order_router.py tests/unit/test_execution_state.py tests/unit/test_live_order_path.py -q` → 47 passed.
- 전체 테스트: PR #521 머지 전 `uv run pytest -q` → 2630 passed, 4 skipped.
- 린트: `uv run ruff check src tests` → All checks passed.
- diff 공백: `git diff --check` → 통과.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` → OK.
- PR 품질 관문: `python3 scripts/check_pr_quality_gate.py /tmp/pr-body-117.md` → `pr-quality-gate-ok`.

## post-merge 자동화

#521 main push 뒤 다음 GitHub Actions run이 success다.

- `Deploy on merge to main`: `29258260571`
- `Released work ledger`: `29258261111`
- `Autonomous work execution loop`: `29258261452`
- `KIS smoke (autonomous)`: `29258261147`
- `Execution quality package`: `29258301296`

#521 직후 released-work sidecar는 `specs/117-submission-unknown-broker-lookup/tasks.md`의 post-merge 항목이 아직 체크되지 않아 스펙 117을 제외했다. 이 handoff 갱신은 T023~T025를 완료로 표시하므로 다음 released-work run이 `candidate-submission-unknown-broker-lookup`을 released로 소비해야 한다.

## 남은 운영 확인

저장소 코드 기준 실행 안전성 111~117은 닫혔다. 남은 것은 저장소 밖 운영 상태 확인이다.

- 운영 서버에서 현재 실행 중인 `auto-invest` 프로세스 수
- systemd와 분리 프로세스로 시작된 오래된 live worker 존재 여부
- GitHub Actions 비밀값과 Environment 보호 규칙
- KIS 계좌의 현재 열린 주문과 실제 보유 상태
- `operator-design` 최근 예약 실행 여부와 결과

위 항목은 실제 서버·KIS·GitHub Environment 권한이 필요한 확인이며, 이 PR에서는 추측하지 않는다.

## 다음 후보

자율 루프의 다음 일반 후보는 `candidate-operator-report-liveness-contract`다. 단, 실제 돈 안전 질문이 다시 들어오면 먼저 서버·KIS 운영 상태 전수 확인을 별도 작업으로 잡는다.
