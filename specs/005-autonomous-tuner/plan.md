# Implementation Plan: Autonomous Tuner (자율 튜너)

**Branch**: `claude/wonderful-brown-dkVmU` | **Date**: 2026-05-24 | **Spec**: `specs/005-autonomous-tuner/spec.md`
**Input**: Feature specification from `specs/005-autonomous-tuner/spec.md`

## Summary

자율 튜너는 측정 → 분석 → 행동 루프를 헌법 안전 경계 안에서 닫는 **순수 결정론적** 엔진이다. 기존 KPI 스냅샷(`telemetry/kpi.py`)을 롤링 윈도로 읽어 탐지 규칙을 돌려 후보 변경을 만들고, 각 후보를 기존 Kernel 매니페스트 리더(`deploy/kernel_guard.py`)에 비춰 L1/L2/L3/L4 권한 등급으로 분류한 뒤(Kernel 교집합 = 무조건 L4), L1 후보 중 적용 경로가 있는 노브(v1: `config/llm_kpi_thresholds.toml` 임계값 조이기)를 장 시간 마진 밖·측정 충분 시에만 멱등하게 적용한다. 모든 행동은 추가-전용 감사(`AUTO_TUNED_*`)로 남고, 매 실행마다 `auto-tuner-report.json`을 일일 리포트 형제로 산출한다. CLI는 `auto-invest tune`.

**기술 접근**: 새 비커널 패키지 `src/auto_invest/tuner/`. LLM 미호출(순수 룰). 유일한 Kernel 터치는 `persistence/audit.py`(K4) 추가-전용 이벤트 4종. K1·K2·K3·K5·K6·K-meta 터치 0건.

## Technical Context

**Language/Version**: Python 3.11 (기존 프로젝트와 동일)
**Primary Dependencies**: 표준 라이브러리 + `tomli`/`tomllib`(TOML 읽기) + `tomli-w`(TOML 쓰기, L1 적용용) + pydantic(감사 페이로드, 기존) + typer(CLI, 기존). 새 외부 의존성 최소화.
**Storage**: SQLite 감사 로그(`persistence/audit.py`, 기존) + 설정 TOML(`config/llm_kpi_thresholds.toml`, 기존) + 리포트 JSON 파일.
**Testing**: pytest(기존). 결정론적 단위/통합 테스트. LLM·네트워크 미사용이라 모킹 표면 작음 — 합성 `token_usage`/`audit_log` 행 + 임시 설정 파일.
**Target Platform**: Linux 서버(기존 워커 호스트). CLI 한 번 실행(세션 마감 후 cron/타이머 또는 수동).
**Project Type**: single project (CLI + 라이브러리). 기존 `src/auto_invest/` 레이아웃 확장.
**Performance Goals**: 한 번 실행이 수 초 내. 롤링 윈도 SQL 집계는 기존 `compute_snapshot` 성능 특성 그대로(인덱스된 `token_usage`).
**Constraints**: LLM 미호출(비용 0). 설정 파일 쓰기는 원자적(임시 파일 + rename). 장 시간 마진(개장 후/폐장 전 30분) 밖에서만 적용. 멱등.
**Scale/Scope**: 단일 운영자·단일 계정. v1 적용 노브 1종(KPI 임계값). 탐지 규칙 4종(임계값 조이기 = 적용, 나머지 cost/cache/latency drift = 후보 기록).

## Constitution Check

*GATE: Phase 0 research 전 통과 필수. Phase 1 design 후 재점검.*

| 원칙 | 적용 여부 | 본 스펙의 준수 방식 |
|------|----------|---------------------|
| **I. 포지션 사이징** | 간접 | 튜너는 `risk/gates.py`(K1)를 읽지도 쓰지도 않는다. K1 교집합 후보는 L4 강제(자동 적용 거부). 캡 표면 불변. |
| **II. 화이트리스트** | 간접 | K2 미터치. 화이트리스트 후보는 L4 강제. |
| **III. LLM 판단 지점 계약** | 간접 | 튜너는 **LLM을 호출하지 않는다**(순수 룰). 판단 지점 *측정치*를 읽을 뿐. K3(`telemetry/meter.py`·`store.py`) 미터치 — 읽기 전용 의존(`compute_snapshot`). |
| **IV. 추가-전용 감사** | **직접** | 튜너의 모든 행동은 `AUTO_TUNED_*` 추가-전용 감사 행. K4(`persistence/audit.py`) 추가-전용 터치(이벤트 타입 4종 추가, 기존 행·타입 불변, 마이그레이션 불필요). 스펙 004·009·010과 동일 패턴. |
| **V. 비밀 격리** | 간접 | 튜너는 KIS/Anthropic 비밀에 접근하지 않는다. K5 미터치. 리포트·감사에 비밀 미기록. |
| **VI. 백테스트→캐너리→본운영** | **직접** | L2/L3 후보(주문 행동에 닿는 변경)는 튜너가 **후보 기록만** 하고, 실제 승격은 스펙 007 캐너리(`canary/run.py`)가 별도 수행. 튜너는 캐너리를 우회하지 않는다. |
| **VII. 외부 API 견고성** | 무관 | 튜너는 외부 API를 호출하지 않는다. |
| **VIII.A 장중 배포 금지** | **직접** | FR-A03: 개장 후/폐장 전 30분 마진 안에서는 L1 적용 거부. 기존 `worker/schedule.py`(K6) 장 시간 판정을 읽기만. K6 미터치. |
| **VIII.B 배포 자동화** | 간접 | L1 임계값 변경은 설정 파일 변경이라 다음 배포 시 스펙 006 파이프라인을 탄다(별도). 튜너는 배포를 직접 트리거하지 않는다(v1). |
| **IX. 자기수정 경계** | **직접(핵심)** | 권한 등급 분류 = IX.A Kernel 매니페스트 기반. FR-A05: `kernel.toml` 교집합 = L4 강제(방어 심층화). FR-A06: 튜너는 K-meta(`kernel.toml`·헌법) 자동 수정 금지. 기존 `deploy/kernel_guard.py` 재사용(IX.C: 하드코딩 경로 금지). |
| **X. 측정 기반 자율 성장** | **직접(핵심)** | FR-A14: 충분한 측정 신호(롤링 윈도 최소 표본) 없이는 튜닝 거부. 임계값 조이기는 30일 안정성 증거에 기반. thin 데이터 튜닝 금지. |

**Kernel 터치 선언(forensic, IX.A)**: 유일한 Kernel 터치는 `src/auto_invest/persistence/audit.py`(K4) — `AUTO_TUNED_L1`·`AUTO_TUNED_L2_CANARY_ENTERED`·`AUTO_TUNED_L4_FORENSIC`·`AUTO_TUNER_RUN` 4종 **추가-전용**. 기존 이벤트 타입·행 불변, DB 마이그레이션 불필요. PR 본문에 K4 커밋 해시 명시. K1·K2·K3·K5·K6·K-meta 터치 0건.

**게이트 결과**: ✅ 통과. 위반 없음. Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/005-autonomous-tuner/
├── spec.md              # 본 스펙(승격 완료)
├── plan.md              # 이 파일
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── tune-cli.md      # `auto-invest tune` CLI 계약 + auto-tuner-report.json 스키마
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/auto_invest/
├── tuner/                       # 새 비커널 패키지
│   ├── __init__.py              # 공개 API 재노출
│   ├── models.py                # CandidateChange, AuthorityTier, Classification, TunerRunResult (frozen dataclasses)
│   ├── classify.py              # 권한 등급 분류 — kernel_guard 재사용, Kernel 교집합=L4 강제
│   ├── detect.py                # 탐지 규칙 — KPI 스냅샷 → 후보 변경 (롤링 윈도, 안정성 판정)
│   ├── knobs.py                 # 튜닝 가능 노브 레지스트리 — v1: KPI 임계값 조이기(읽기/쓰기/클램프)
│   ├── gates.py                 # 안전 게이트 — 장 시간 마진(schedule 재사용) + 측정 기반(헌법 X)
│   ├── report.py                # auto-tuner-report.json 직렬화
│   └── runner.py                # 오케스트레이션 — detect→classify→gate→apply→audit→report (멱등)
├── persistence/
│   └── audit.py                 # [K4 추가-전용] AUTO_TUNED_* 페이로드 4종
└── cli.py                       # [수정] `auto-invest tune` 서브커맨드 추가

tests/
├── unit/
│   ├── test_tuner_detect.py     # 탐지 규칙 단위(안정성 판정·후보 생성)
│   ├── test_tuner_classify.py   # 분류 + Kernel 교집합=L4 전수(K1~K6·K-meta)
│   ├── test_tuner_knobs.py      # 임계값 조이기·클램프·멱등·원자적 쓰기
│   ├── test_tuner_gates.py      # 장 시간 마진 + 측정 기반 게이트
│   └── test_tuner_report.py     # 리포트 직렬화·감사 정합
└── integration/
    └── test_tuner_e2e.py        # CLI end-to-end: dry-run/apply, 감사 기록, 리포트 파일
```

**Structure Decision**: 기존 `src/auto_invest/` single-project 레이아웃을 따른다. 새 패키지 `tuner/`는 스펙 004의 `judgment/` 패키지와 같은 형태(models·detect·classify·runner 분리). 기존 모듈(`telemetry/kpi.py`·`deploy/kernel_guard.py`·`performance/engine.py`·`worker/schedule.py`·`reports/daily.py`)은 **읽기 전용 의존**으로 재사용하고 수정하지 않는다(K4 audit.py 추가-전용 제외).

## 단계적 구현 순서 (User Story → Phase 매핑)

- **Phase 1 (US1, P1)**: `models.py`·`detect.py`·`classify.py` + K4 감사 페이로드. 탐지+분류 read-only 코어. dry-run CLI 골격. → MVP: "튜너가 무엇을 하려는가"를 결정론적으로 산출.
- **Phase 2 (US2, P1)**: `knobs.py`(임계값 조이기·클램프·원자적·멱등) + `runner.py` apply 경로 + `AUTO_TUNED_L1` 감사. → 측정→행동 루프 닫힘.
- **Phase 3 (US3, P2)**: `gates.py` — 장 시간 마진(`schedule` 재사용) + 측정 기반(헌법 X 최소 표본). runner에 게이트 통합.
- **Phase 4 (US4, P2)**: `report.py` + CLI `tune` 완성(--dry-run/--apply/--window/--as-of/--output-root/--json/--db) + 통합 테스트.
- **Phase 5 (검증)**: 전체 테스트 + 린트, tasks.md 완료 표시, HANDOFF 갱신.

## Complexity Tracking

> Constitution Check 위반 없음 — 비움.
