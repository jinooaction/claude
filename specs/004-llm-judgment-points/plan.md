# Implementation Plan: LLM Judgment Points (LLM 판단 지점)

**Branch**: `claude/beautiful-mayer-nDR3x` | **Date**: 2026-05-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-llm-judgment-points/spec.md`

## Summary

Claude를 거래 루프에 처음 부르는 기능. 명시적으로 열거된 세 판단 지점(`volatility_assessment` P1, `daily_summary` P2, `news_screen` P3)을 헌법 III 계약(트리거·입력·출력 스키마·지연 예산·비용 예산)과 함께 코드로 선언하고, 각 호출을 견고한 Anthropic 클라이언트(헌법 VII, `broker/client.py` `ResilientClient` 패턴 미러)로 감싸 토큰 텔레메트리(스펙 002)·감사 로그(`LLM_CALL`)에 기록한다.

**핵심 안전 설계** (이 계획의 중심):

- **자문은 주문 경로 진입 *전* 단계(`execution/order_router.py`, 비커널)에서 소비**되어 OrderRequest를 **줄이거나(size_down) 건너뛸 수만(halt)** 있고, **절대 키우지 못한다**. 그 뒤 기존 K1 게이트(`risk/gates.py`)가 변형 없이 실행되므로 포지션 캡은 LLM 자문과 무관하게 그대로 바인딩된다. → **K1 터치 0.**
- **결정론적 폴백**: LLM 실패·타임아웃·서킷오픈·예산초과·스키마위반 시 자문 없이 v1 동작. 거래는 막히지 않는다.
- **결정성**: 자문(enum/score) → 게이트 결정 변환은 룰이 선언한 결정론적 규칙(임계 confidence·축소 계수)으로만. "LLM이 사이즈를 정한다" 금지.

새 패키지 `src/auto_invest/judgment/`가 프레임워크를 담는다. 텔레메트리(`TokenMeter`, K3)는 **변경 없이 재사용**(호출만; 파일 미수정 → K3 터치 0 목표). 유일한 Kernel 터치는 `persistence/audit.py`(K4)에 **추가-전용** 판단 이벤트 페이로드를 더하는 것 — 스펙 009/010과 동일 패턴.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`)
**Primary Dependencies**: `anthropic>=0.97.0` (AsyncAnthropic), `tenacity>=9.1.4` (지수 백오프 — 기존 `ResilientClient`가 사용), `pydantic` (출력 스키마 검증 — 기존 config 모델이 사용), `typer` (CLI)
**Storage**: SQLite append-only `audit_log` + `token_usage` (기존 스키마 재사용; 새 테이블/마이그레이션 불필요 — 판단 이벤트는 페이로드 JSON으로 기록)
**Testing**: pytest. 단위 `tests/unit/`, 통합 `tests/integration/`. Anthropic은 `_AnthropicProtocol` 덕타이핑 mock(스펙 010 패턴).
**Target Platform**: Linux worker (systemd), dry-run/live 모드 공통
**Project Type**: 단일 프로젝트 (CLI + 워커 데몬)
**Performance Goals**: 판단 지점별 지연 예산 — volatility p95<2s, news p95<5s, daily p95<10s. 비용 예산 — $0.01/$0.02/$0.05 per call. 거래 루프는 LLM을 기다리느라 막히지 않음(폴백 타임아웃).
**Constraints**: LLM은 자문만, 주문 직접 제출 금지. 자문은 노출을 늘릴 수 없음(줄이거나 건너뛰기만). 틱마다 호출 금지(트리거+쿨다운). 프롬프트/응답 본문·비밀 미기록(헌법 V).
**Scale/Scope**: 단일 운영자·단일 계정. 세 판단 지점. 캐너리 5% 코호트.

## Constitution Check

*GATE: Phase 0 전 통과 필수. Phase 1 설계 후 재점검.*

| 원칙 | 적용 | 계획의 준수 |
|------|------|-------------|
| **I. 포지션 캡 (K1, NON-NEG)** | 자문이 사이즈에 영향 | 자문은 order_router에서 **줄이거나 건너뛰기만** — K1 게이트(`risk/gates.py`)는 변형 없이 그 뒤 실행. **K1 터치 0**. 캡은 자문과 무관히 바인딩. ✅ |
| **II. 화이트리스트 (K2, NON-NEG)** | 판단 지점은 화이트리스트 종목에만 발화 | 트리거는 기존 화이트리스트 종목 대상으로만. K2 터치 0. ✅ |
| **III. 판단 지점 계약 (K3, NON-NEG)** | 이 스펙의 본질 | 각 판단 지점이 트리거·입력 계약·출력 스키마·지연/비용 예산을 코드 레지스트리로 선언. `meter.py`/`store.py`(K3)는 **호출만, 미수정** → K3 터치 0 목표. ✅ |
| **IV. 추가-전용 감사 (K4, NON-NEG)** | 호출·자문·폴백 기록 | `LLM_CALL`(기존) + 새 추가-전용 판단 이벤트 페이로드(`persistence/audit.py`, **K4 추가 터치**). 기존 이벤트/행 미변경. 마이그레이션 불필요. ✅ (Kernel 터치 — IX.A 포렌식 콜아웃을 PR에 명시) |
| **V. 비밀 격리 (K5, NON-NEG)** | LLM 본문·키 누출 위험 | 토큰/비용/지연/모델/error_class만 기록, **프롬프트·응답 본문 미기록**. `logging_config.py`(K5) 미수정. ✅ |
| **VI. 단계적 확장 (NON-NEG)** | 자본 닿는 판단 지점 | `volatility_assessment`는 자본 5% 캐너리 코호트에서만 자문 반영, ≥10 거래일. 기존 `canary/`·`strategy/canary.py` 인프라 재사용. ✅ |
| **VII. 외부 API 견고성 (NON-NEG)** | Anthropic 호출 | 새 `judgment/client.py`가 `broker/client.py` `ResilientClient`(레이트리밋+재시도+서킷브레이커) 패턴 미러. 새 메커니즘 발명 금지. ✅ |
| **VIII.A 장중 배포 금지 (K6)** | 런타임 무관, 배포 시 적용 | `worker/schedule.py`(K6) 미수정. 배포는 기존 스펙 006 파이프라인. ✅ |
| **IX. 자기수정 경계** | K4 추가 터치 | 머지는 IX.D 자율 경로(세션 추론 + PR 본문이 승인 기록). 생산 배포는 스펙 007 캐너리. K4 터치 커밋 해시를 PR 본문에 명시. ✅ |
| **X. 측정 기반 성장** | 스펙 011·005 연계 | 판단 지점이 영향 준 거래를 식별 가능하게 남겨 스펙 011이 캐너리 vs 대조군 성과 비교 가능. 이 스펙은 스펙 005가 튜닝할 표면(프롬프트·파라미터)을 생성. ✅ |

**게이트 결과**: 위반 없음. 유일한 Kernel 터치는 K4 추가-전용(audit 이벤트). 이는 헌법 IX.A 포렌식-주의 항목이지 머지 차단 사유가 아니며(v3.0.0), 스펙 009/010이 한 추가 패턴과 동일. Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/004-llm-judgment-points/
├── plan.md              # 이 파일
├── research.md          # Phase 0 — 결정 기록
├── data-model.md        # Phase 1 — 엔티티
├── quickstart.md        # Phase 1 — 검증 시나리오
├── contracts/           # Phase 1 — 판단 지점 계약 + CLI 표면
│   ├── judgment-points.md
│   └── cli.md
└── tasks.md             # Phase 2 (/speckit-tasks 가 생성)
```

### Source Code (repository root)

```text
src/auto_invest/
├── judgment/                    # NEW 패키지 — 판단 지점 프레임워크 (비커널)
│   ├── __init__.py
│   ├── registry.py              # JudgmentPoint 계약 선언 + 조회 (헌법 III)
│   ├── client.py                # 견고한 Anthropic 클라이언트 (헌법 VII, ResilientClient 미러)
│   ├── budget.py                # 판단 지점별 롤링 비용 예산 → 폴백 전환 (US4/FR-041)
│   ├── schemas.py               # 출력 스키마 (pydantic) + 검증 (FR-006)
│   └── points/
│       ├── __init__.py
│       ├── volatility.py        # volatility_assessment 프롬프트·스키마·폴백 (US1)
│       ├── daily_summary.py     # daily_summary (US2)
│       └── news_screen.py       # news_screen (US3)
├── execution/order_router.py    # MODIFY (비커널) — 자문 소비: 주문 축소/건너뛰기 (FR-003/FR-012)
├── persistence/audit.py         # MODIFY (K4 추가-전용) — 판단 이벤트 페이로드
├── reports/ 또는 cli.py         # MODIFY — daily_summary 리포트 섹션 (FR-022) + efficiency 분해 (FR-040)
└── strategy/triggers.py         # MODIFY (비커널, 필요 시) — 변동성 트리거 발화 컨텍스트

tests/
├── unit/
│   ├── test_judgment_registry.py
│   ├── test_judgment_client.py        # 재시도·서킷·타임아웃 → 폴백
│   ├── test_judgment_schemas.py       # 스키마 위반 거부
│   ├── test_judgment_budget.py        # 예산 초과 → 폴백 전환
│   └── test_judgment_points.py        # 세 지점 프롬프트·폴백
└── integration/
    ├── test_judgment_volatility_gate.py   # 자문 → order_router 축소/건너뛰기, 결정성, K1 여전히 바인딩
    ├── test_judgment_fallback_chaos.py    # LLM 항상 실패 → 주문 경로 v1 동작 (SC-001)
    ├── test_judgment_audit_telemetry.py   # LLM_CALL + token_usage 짝, 본문 미기록 (SC-003)
    └── test_judgment_daily_summary.py     # 리포트 섹션 + 폴백
```

**Structure Decision**: 단일 프로젝트. 프레임워크는 새 비커널 패키지 `src/auto_invest/judgment/`에 격리해 기존 게이트/리스크 코드(K1)와 분리한다. 주문 경로 통합은 비커널 `order_router.py`에서 자문을 "축소/건너뛰기"로만 적용해 K1 불변. 유일한 Kernel 접촉은 `persistence/audit.py`(K4) 추가-전용 이벤트.

## Complexity Tracking

> Constitution Check 위반 없음 — 작성 불필요.
