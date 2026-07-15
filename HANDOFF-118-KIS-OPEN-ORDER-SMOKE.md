# HANDOFF-118 — KIS 열린 주문 smoke와 스펙 118 마무리

## 한 줄 결론

스펙 118 이후 남은 운영 확인 지점은 KIS live smoke에 열린 미체결 주문 0건 검사를 추가하고, main 기준 smoke·장부·자율 루프를 다시 실행해 닫았다.

## 기준 상태

- 기준 `main`: `2b9fe8583019ee3459ecce443bd9d0442178f335` — PR #527 KIS smoke 열린 주문 검사 보강
- 직전 기능 기준: `158052add91cc059b4d61a18ea1e5efad508185b` — PR #525 스펙 118 운영자 이해 가능 보고 생존성 계약
- #527 기능 커밋: `a3b324e0966ff1ab23c0541e5fe46a4027f7c5a4`
- 확인 시점: 2026-07-15 KST
- 돈 경로: 계속 `PREVIEW_ONLY`
- 실제 주문·취소·실거래 전환: 수행하지 않음
- live sentinel, capital, whitelist, caps, loss budget, 헌법, kernel manifest, 비밀값: 변경 없음

## 해결한 남은 위험

스펙 118은 최종 보고 품질 계약을 넣었지만, 완료 보고 후 다음 네 가지가 아직 실제 표면으로 닫혀 있지 않았다.

1. 서버 배포 상태와 감사 증거.
2. 최신 KIS read-only smoke가 실제 서버 secrets로 통과하는지.
3. KIS 계좌에 열린 미체결 주문이 남아 다음 자동화 판단을 오염시키지 않는지.
4. released-work와 autonomous-work가 최신 main 기준으로 같은 결론을 내는지.

기존 `tests/integration/test_live_broker.py`는 quote, 외화예수금, 보유 종목, 합산 잔고 4개만 확인했다. #527은 최근 7일 KIS 주문/체결 조회를 추가해 열린 미체결 주문이 하나라도 있으면 live smoke가 실패하도록 만들었다.

## 적용 기준

- 새 검사는 `get_order_executions_resolving_market`을 통해 KIS `inquire-ccnl` 읽기 전용 GET 경로만 사용한다.
- 최근 7일의 주문/체결 행을 모아 `unfilled_qty > 0`이고 terminal이 아닌 주문이 있으면 실패한다.
- `KIS_LIVE_TEST=1`이 없으면 기존처럼 로컬/일반 CI에서는 skip한다.
- GitHub Actions `KIS smoke (autonomous)` workflow는 서버 임시 checkout에서 이 5개 live smoke를 실행한다.

## 검증

- 로컬 focused smoke gate: `uv run pytest tests/integration/test_live_broker.py -q` → 5 skipped.
- 로컬 린트: `uv run ruff check tests/integration/test_live_broker.py` → All checks passed.
- 전체 테스트: `uv run pytest` → 2638 passed, 5 skipped.
- 전체 린트: `uv run ruff check src tests` → All checks passed.
- 하네스: `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14).
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` → OK.
- PR 본문 품질 관문: `uv run python scripts/check_pr_quality_gate.py /tmp/pr-body-open-live-orders.md` → `pr-quality-gate-ok`.
- 브랜치 KIS live smoke: run `29422539457`, commit `a3b324e0966ff1ab23c0541e5fe46a4027f7c5a4`, `5 passed`, 최근 주문/체결 행 0개, 열린 미체결 주문 0개.
- main KIS live smoke: run `29422806756`, commit `2b9fe8583019ee3459ecce443bd9d0442178f335`, `5 passed`, 최근 주문/체결 행 0개, 열린 미체결 주문 0개.

## post-merge 자동화

- `KIS smoke (autonomous)` run `29422806756`: success, `smoke_state=success`, `smoke_exit=0`, `tests_total=5`, `tests_failed=0`.
- `Deploy on merge to main` run `29422806870`: workflow conclusion success, systemd unit sync success, deploy oneshot은 미국 장중 배포 금지로 `2026-07-15T20:00:00Z` 이후 자동 재배포 대기. 이는 안전장치 동작이며 장중 강제 배포하지 않는다.
- `Execution quality package` run `29422841373`: success, `overall_status=OBSERVE`, KIS smoke 5개 반영.
- `Released work ledger` run `29422911779`: success, `overall_status=OK`, `released_count=38`, `candidate-operator-report-liveness-contract` released.
- `Autonomous work execution loop` run `29422962267`: success, `overall_status=RELEASED`, 현재 실행 가능한 안전 후보 없음.

## 안전 경계

- 등급 2 읽기 전용 운영 smoke 보강이다.
- 실제 주문, 주문 취소, 실거래 재무장, 자본 증액, 자본 배분, whitelist/caps 확대, 손실 예산, live sentinel, K1/K2/K4/K5/K6, 헌법, kernel manifest, 비밀값, 외부 유료 서비스는 바꾸지 않았다.
- KIS secrets는 기존 GitHub Actions 서버 smoke 경로에서만 쓰며 로그에는 값이 노출되지 않는다.
- 장중 배포 금지는 유지했다. `Deploy on merge`가 거부한 것은 안전 경계가 작동한 결과다.

## 다음 후보

최신 autonomous-work sidecar 기준 현재 실행 가능한 안전 후보는 없다. 다음 작업을 고르려면 후속 frontier 갱신 또는 새 operator 지시가 필요하다.
