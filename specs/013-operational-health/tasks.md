# Tasks: Operational Health Roll-up (`auto-invest health`)

Spec: `specs/013-operational-health/spec.md`. 브랜치 `claude/affectionate-mayer-Sax0o`.

모든 작업은 **읽기 전용·비커널·추가-전용**이다. 거래 워커 루프 무수정.

## T001 — 헬스 롤업 모듈 (P1) ✅
- `src/auto_invest/reports/health.py` 신설.
- `HealthCheck`(name·status·detail·data)·`HealthReport`(generated_at_utc·overall·
  checks·context) dataclass + `to_dict()`(byte-stable).
- 점검 함수: worker_liveness(PID), halt(플래그), reconciliation(결과+신선도),
  recent_errors(24h), activity(마지막 이벤트 신선도).
- 맥락: 오늘 주문 깔때기·보유 종목 수·마지막 성과 스냅샷·마지막 튜너 실행·마지막
  캐너리 검증.
- `build_health_report(conn, *, pid_path, halt_path, now, stale_hours)` — `now` 주입.
- 종합 판정 = 최악 점검(OK<DEGRADED<CRITICAL).

## T002 — CLI `health` 명령 (P1) ✅
- `cli.py` 에 `@app.command() def health(...)`.
- 옵션: `--db`·`--halt-path`·`--format text|json`·`--stale-hours 36`.
- DB 없으면 CRITICAL(db 없음) + 종료 1 (연결 생성 금지).
- `db.migrate` 호출 안 함 — 0001 테이블만 SELECT.
- 종료 코드: OK→0, 그 외→1.

## T003 — 테스트 (P1) ✅
- `tests/integration/test_health_cli.py`: 깨끗→OK/0, MISMATCH→CRITICAL/1,
  halt→DEGRADED, db 없음→CRITICAL/1, json 결정론, read-only(row 수 불변).
- `tests/unit/test_health_report.py`: 점검별 단위(워커 생존/stale, 정합성 신선도,
  오류 집계, 활동 신선도, 종합 판정 = 최악).

## T004 — 테스트+린트 그린, 커밋·푸시 ✅
- `uv run pytest`, `uv run ruff check src tests`.

## T005 — HANDOFF 갱신 + 자동 머지 (P2)
- PR 본문에 Kernel 터치 0건 명시. 테스트+린트 재확인 후 자동 머지(merge).
