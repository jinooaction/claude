# Implementation Plan: Paper-Trading Daemon

**Branch**: `claude/continue-previous-session-20p3O` | **Date**: 2026-05-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-paper-trading-daemon/spec.md`

## Summary

운영자가 자본 100달러 live 노출 전 "일주일 paper-trading 관찰" 단계를 가질 수 있도록 데몬과 리포트 CLI를 추가한다. 핵심 기술 접근:

1. **단일 차단 지점**: `src/auto_invest/execution/order_router.py:347` (`place_order(self.broker, ...)` 호출) 직전에 paper 모드 분기. paper 모드면 실제 broker 호출 대신 시뮬 체결 처리. 이 위치 외 다른 broker.order_* 경로는 없음(grep 검증).
2. **K4 additive 확장**: `src/auto_invest/persistence/audit.py`에 4개 새 페이로드 추가 — `PaperRunStartedPayload`, `PaperRunStoppedPayload`, `OrderPaperFilledPayload`, `PaperRunRejectedPayload`. 기존 페이로드·migration 파일 무수정. K4 터치이지만 IX.D 자율 머지 채널.
3. **K1·K6 무수정**: cap/whitelist/halt/session 게이트는 그대로 호출. paper 모드는 게이트 평가 후의 broker 호출만 바꾼다 (FR-005, FR-014).
4. **상호 배타**: `src/auto_invest/paper/mutex.py` 신규 — 시작 시 audit_log의 최근 `WORKER_STARTED`/`PAPER_RUN_STARTED` 이후 stop 이벤트가 없는지 확인. SQLite 단일 쿼리로 충분 (race window는 사람 손 속도로 무시 가능).
5. **paper-report**: `src/auto_invest/paper/report.py` 신규 — audit_log를 SQL aggregation으로 룰별 집계. 가상 포지션은 `ORDER_PAPER_FILLED` 이벤트 누적으로 derived (별도 테이블 없음).
6. **새 CLI 서브커맨드**: `cli.py`에 `paper_run`, `paper_report` 두 함수 추가.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), httpx (KIS API), pydantic (config·payload), pytest (테스트). 모두 기존 코드베이스 의존성.
**Storage**: SQLite (audit_log 기존 테이블 그대로 사용 — 새 row만 INSERT, 새 컬럼·테이블 없음)
**Testing**: pytest. 단위 테스트는 `tests/test_paper_*.py`, 통합 테스트는 `tests/test_paper_integration.py` (mocked broker).
**Target Platform**: Linux server (Vultr 인스턴스). foreground CLI 데몬. systemd 통합은 후속.
**Project Type**: CLI + library (기존 spec 001~008 구조 그대로)
**Performance Goals**:
  - paper-run tick은 live와 동일 (1초 간격, SC-002에서 일주일 연속 검증)
  - paper-report 일주일치 집계 200ms 이내 (SC-003)
**Constraints**:
  - 실주문 API 호출 0건 (SC-001)
  - live·paper 동시 실행 거부 (SC-007)
  - audit_log·positions에 paper 모드가 비-paper row를 단 한 줄도 안 건드림 (SC-006)
**Scale/Scope**:
  - 일주일 = 5영업일 × 6.5시간 × 3600초 / tick_interval (1s) ≈ 117,000 tick
  - 룰 ~10개, 종목 ~20개 → 시그널 ~수백 건 추정 → audit row ~수만 건
  - SQLite 200ms aggregation은 10만 row 범위에서 검증된 수준

## Constitution Check

*GATE: Phase 0 전·Phase 1 후 모두 통과해야 함.*

| Principle | 영향 | Compliance |
|-----------|------|-----------|
| I. Position Sizing (K1) | paper-run은 cap 게이트를 live와 동일 호출 (FR-005, FR-016). K1 코드 무수정. | ✅ 통과 — K1 파일 무수정 |
| II. Deny-by-Default Whitelist (K2) | paper-run도 whitelist 게이트 통과 필수. K2 무수정. | ✅ 통과 |
| III. LLM at Judgment Points Only (K3) | paper-run은 LLM 호출 경로 변경 없음. K3 무수정. | ✅ 통과 |
| IV. Append-Only Audit (K4) | 4개 페이로드 추가, 기존 페이로드·migration 무수정. additive. | ⚠️ K4 추가 변경 — IX.D 자율 머지 채널, PR 본문에 커밋 해시 명시 필요 |
| V. Secret Isolation (K5) | paper-run도 같은 secrets 로더 사용. K5 무수정. | ✅ 통과 |
| VI. Backtest → Canary → Full Live | paper-trading은 backtest 다음·canary 이전 단계로 위치. canary 자체 무수정. | ✅ 통과 — 단계 추가만, 기존 단계 변경 없음 |
| VII. External API Robustness | paper-run도 같은 ResilientClient 사용 (quote 호출). 변경 없음. | ✅ 통과 |
| VIII.A No Market-Hours Deploys | paper-run 실행은 deploy가 아닌 worker 실행. 영향 없음. K6 무수정. | ✅ 통과 |
| VIII.B Automated-Deploy Requirements | paper-run은 deploy 자동화에 포함 안 됨. | ✅ 통과 |
| IX.A Kernel Forensic List | K4 1회 추가 변경. K1·K2·K3·K5·K6·K_meta 무수정. | ⚠️ K4 터치 — PR 본문에 commit hash 명시 |
| IX.B Autonomous Workflow | 머지는 IX.D 자율 채널, merge method = merge (squash 금지). | ✅ 통과 — CLAUDE.md 자동 머지 규칙 적용 |
| IX.C Kernel Manifest | kernel.toml 무수정. | ✅ 통과 |
| IX.D Operator Autonomy Supremacy | 운영자 지시("spec 009로 정식")에 따른 자율 진행. | ✅ 통과 |

**결론**: K4 추가 변경 1건을 제외하면 위반 없음. K4 추가는 IX.D 자율 머지 채널에 해당 (constitution v3.0.0).

## Project Structure

### Documentation (this feature)

```text
specs/009-paper-trading-daemon/
├── plan.md                    # 이 파일
├── spec.md                    # 기능 스펙
├── research.md                # Phase 0 — 기술 결정 근거
├── data-model.md              # Phase 1 — 엔티티·이벤트 페이로드 스키마
├── quickstart.md              # Phase 1 — 운영자 온보딩
├── contracts/
│   ├── paper-run-cli.md       # paper-run 서브커맨드 계약
│   ├── paper-report-cli.md    # paper-report 서브커맨드 계약
│   └── paper-audit-events.md  # 신규 audit 페이로드 4종 계약
├── checklists/
│   └── requirements.md        # spec 품질 체크리스트
└── tasks.md                   # Phase 2 — /speckit-tasks에서 생성
```

### Source Code (repository root)

```text
src/auto_invest/
├── cli.py                                # +paper_run, +paper_report 서브커맨드
├── execution/
│   └── order_router.py                   # broker 호출 직전 paper 분기 1줄 (단일 차단 지점)
├── persistence/
│   └── audit.py                          # K4 additive: +PaperRunStartedPayload, +PaperRunStoppedPayload, +OrderPaperFilledPayload, +PaperRunRejectedPayload
├── worker/
│   └── loop.py                           # WorkerSettings에 paper_mode: bool 추가 (default False); record_start/stop이 paper 모드면 PaperRun* 페이로드 사용
└── paper/                                # 신규 패키지
    ├── __init__.py
    ├── mutex.py                          # paper·live 상호 배타 가드 (audit_log 기반)
    ├── report.py                         # paper-report 집계 로직
    └── virtual_positions.py              # ORDER_PAPER_FILLED 이벤트 누적 → 가상 포지션 derived

tests/
├── test_paper_mutex.py                   # 상호 배타 단위 테스트 (SC-007)
├── test_paper_order_router.py            # 단일 차단 지점 동작 (SC-001, SC-004)
├── test_paper_audit_payloads.py          # 4개 신규 페이로드 검증
├── test_paper_report.py                  # 집계·튜닝 피드백 (SC-003, SC-005)
├── test_paper_virtual_positions.py       # 가상 포지션 derived 계산
├── test_paper_integration.py             # CLI 진입점 + worker loop + audit 통합
└── test_paper_no_live_writes.py          # paper-run이 live row 무수정 (SC-006)
```

**Structure Decision**: spec 001~008과 동일한 src/auto_invest/ 단일 패키지. paper 전용 모듈은 새 서브패키지 `paper/`로 격리 — paper 기능이 비활성일 때 import 비용 0. 게이트·broker·worker 코드는 paper 모드 플래그 1개만 추가하고 분기 로직은 최소화 (FR-014: "paper 전용 룰 평가 분기는 허용하지 않는다"를 코드 구조로 강제).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| K4 additive 페이로드 4종 추가 | FR-006, FR-013, paper 모드 이벤트가 live 이벤트와 구분되어야 SC-006·FR-011을 만족 | 기존 페이로드 재사용 — 거부 이유: live·paper 구분이 사라져 FR-011 위반 |
| `paper/` 신규 서브패키지 | 격리·테스트 용이성, 비활성 시 import 비용 0 | 모든 코드를 `worker/`에 인라인 — 거부 이유: paper 비활성 경로에 dead code 유입 |

(위 두 항목은 위반이 아닌 정당화된 추가 — 표는 운영자 사후 검토 용이성을 위해 기록)
