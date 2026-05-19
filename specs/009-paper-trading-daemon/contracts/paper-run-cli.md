# Contract: `auto-invest paper-run`

**Spec**: 009 · **Phase**: 1 · **Date**: 2026-05-19

paper-trading 데몬을 띄우는 CLI 진입점. live `auto-invest run`과 같은 worker 코드 패스를 타지만 broker 주문은 시뮬로 처리된다.

---

## Usage

```
auto-invest paper-run \
    [--config PATH] \
    [--db PATH] \
    [--halt-path PATH] \
    [--env-file PATH] \
    [--base-url URL] \
    [--capital FLOAT] \
    [--require-session-open/--ignore-session-window] \
    [--prices PATH]
```

**옵션 의미는 `auto-invest run`과 동일**. paper-run은 `--dry-run` 플래그를 받지 않는다 (dry-run은 spec 001에서 정의된 smoke test이며 paper-run과 다른 의도).

---

## Behavior

### 시작 시퀀스

1. config·secrets·prices 로드 (live와 동일). 실패 시 exit 2.
2. stage uniqueness 검증 (live와 동일). 위반 시 exit 2.
3. migration gate (live와 동일). pending migration 있으면 exit 1.
4. **mutex check** (paper-run 특유):
   - audit_log에 가장 최근의 `worker_started` 또는 `paper_run_started` 이벤트 조회.
   - 그 이벤트 이후 대응되는 `worker_stopped` 또는 `paper_run_stopped`가 없으면 → 다른 모드가 실행 중.
   - 충돌 시: `PaperRunRejectedPayload(attempted_mode="paper", reason="mutex_conflict", ...)` 기록 후 exit 70. stderr에 한글 에러 메시지: "live worker가 실행 중입니다 (started_at=...). live 종료 후 paper-run을 다시 시작하세요."
5. KIS token 발급 (live와 동일 — quote 호출에 필요).
6. ResilientClient + Worker 생성, `WorkerSettings.paper_mode=True`.
7. `worker.record_start(secret_keys=...)`가 paper_mode=True를 보고 `PaperRunStartedPayload` 기록.
8. signal handler 등록 → `worker.run_forever()`.

### tick 동작

- live와 동일. 단 OrderRouter.submit_order의 broker 호출 직전 분기가 paper로 진입 → `OrderPaperFilledPayload` 기록.
- 게이트 차단 시: live와 동일하게 `OrderRejectedByGatePayload` 기록.

### 종료 시퀀스

- SIGTERM/SIGINT → 다음 tick 완료 후 stop event 보내고 `worker.record_stop("signal_received")`.
- record_stop이 paper_mode=True 보고 `PaperRunStoppedPayload(reason="signal_received", session_started_event_id=...)` 기록.
- DB connection close, exit 0.

### 비정상 종료

- 예외 발생: `try/finally`에서 `PaperRunStoppedPayload(reason="crash")` 기록 시도 (best-effort).
- OS-level kill (SIGKILL, OOM, kernel panic) — audit 기록 못 함. 다음 paper-run 시작 시 mutex check가 stale `PaperRunStarted`를 감지 — 운영자는 stderr 메시지를 보고 수동 정리:
  - 옵션: 데몬은 "마지막 started 이벤트가 N분 이상 stop 짝 없이 떠 있음 + PID 죽었음"을 확인하면 자동 `PaperRunStoppedPayload(reason="crash")`를 보강 기록한 뒤 진행. (이 자동 정리는 P3 우선순위로, 본 스펙에서는 stretch goal — tasks.md에서 결정.)

---

## Exit Codes

| Code | 의미 |
|------|------|
| 0 | 정상 종료 (signal_received) |
| 1 | 일반 오류 (예외, migration 실패) |
| 2 | 설정 오류 (config·prices·stage uniqueness) |
| 70 | mutex 충돌 (live worker가 이미 실행 중) |

---

## stdout/stderr 출력

- 시작 시 stdout: `paper-run started (session_id=N, ruleset_sha256=...)` 1줄.
- 매 tick 후 stdout: live와 동일한 로그 (logger.INFO).
- 시뮬 체결 시 stdout: `[PAPER FILL] rule_id=... symbol=... side=BUY qty=10 @ $123.45 (ask)` 1줄.
- mutex 충돌 시 stderr: 위 "live worker가 실행 중입니다 ..." 한글 메시지.

---

## audit_log 영향

본 명령 1회 실행이 audit_log에 남기는 이벤트:

- 시작 시: `secrets_loaded` (기존) + `rule_load` (기존) + `paper_run_started` (신규).
- tick 당: 시그널 없으면 0개. 시그널 있으면 `order_intent` + (게이트 통과 시) `order_paper_filled` 또는 (차단 시) `order_rejected_by_gate`.
- 외부 API 오류 시: `error` 또는 `order_rejected_by_broker` (quote 호출 실패 시).
- 종료 시: `paper_run_stopped`.

**Live row 보호**: `worker_started`, `worker_stopped`, `fill`, `order_submitted`는 paper-run에서 단 1줄도 INSERT되지 않는다 (SC-006).

---

## 테스트 가능한 invariants

| Invariant | 검증 방법 |
|-----------|----------|
| paper-run이 KIS 주문 API에 접근 안 함 | `tests/test_paper_order_router.py` — broker.post를 raise하도록 monkeypatch, 100 tick 실행, 예외 미발생 확인 |
| paper-run이 game-over 후 live row 무수정 | `tests/test_paper_no_live_writes.py` — paper-run 전·후 positions·fills row count 비교 |
| paper-run이 mutex 거부 시 exit 70 | `tests/test_paper_mutex.py` — 가짜 `worker_started`를 미리 INSERT 후 paper-run 호출, exit code 검증 |
| signal handler가 다음 tick 완료 후 정상 종료 | `tests/test_paper_integration.py` — SIGTERM 보내고 stop event 기록 확인 |
