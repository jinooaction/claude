# Implementation Plan: Tuner L2/L3 → Hardened-Canary Auto-Submission

**Branch**: `claude/upbeat-bell-Sq9qm` | **Date**: 2026-05-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/012-tuner-canary-queue/spec.md`

## Summary

스펙 005 자율 튜너의 L2/L3 후보가 현재 "감사 로그 한 줄 적고 끝"인 죽은 분기를,
**스펙 007 하드닝 캐너리로 실제 투입해 검증하는 살아있는 경로**로 바꾼다. 접근:

1. 튜너 L2/L3 분류 결과를 캐너리가 평가 가능한 **구조화된 후보 기록(CanaryCandidate)**
   으로 구체화하고, 추가-전용 감사 이벤트 + 튜너 리포트에 남긴다(P1, MVP).
2. apply 모드에서 그 후보를 **git plumbing 으로 임시 후보 rev(작업트리 무수정·미푸시)**
   로 만들고 `run_canary(CanaryOptions)` 를 호출해 과거 리플레이 + 합성 충격 + 퍼즈로
   검증한 뒤 합격/불합격을 기록한다(P2).
3. 합격해도 라이브 워커로 **자동 승격하지 않으며**(운영자/스펙 006 게이트 전용,
   헌법 IX.B-2), 안전 불변(작업트리·원격·라이브 설정 무변경)을 테스트로 고정한다(P3).

v1 의 구체적 튜닝 노브: 판단 지점 `max_tokens`(비용·지연에 직접 영향, 가역, 클램프).
모델 라우팅을 깨끗하게 조정 가능하게 하려고 `config/judgment_tunables.toml`(비커널)을
신설해 `judgment/registry.py` 가 폴백 기본값과 함께 읽는다 — 파일 없으면 현재 하드코딩
값과 동일(런타임 동작 무변경).

## Technical Context

**Language/Version**: Python 3.11 (기존 코드베이스)
**Primary Dependencies**: 기존만 사용 — `auto_invest.canary.run.run_canary`(스펙 007), `auto_invest.tuner.*`(스펙 005), `auto_invest.persistence.audit`(K4), `auto_invest.deploy.kernel_guard`, 표준 라이브러리 `subprocess`(git plumbing). 새 외부 의존성 0.
**Storage**: SQLite `audit_log`(추가-전용, K4). 설정 파일 `config/judgment_tunables.toml`(신규, 비커널). 캐너리 산출물은 기존 `data/canary/`.
**Testing**: pytest. 신규 단위/통합 테스트는 임시 git 저장소·임시 DB·주입 가능한 캐너리 러너 더블로 결정론 보장.
**Target Platform**: Linux(운영 워커) + 개발 컨테이너.
**Project Type**: 단일 프로젝트(CLI + 라이브러리). 기존 `src/auto_invest/` 레이아웃 유지.
**Performance Goals**: 튜너 1회 실행에 후보당 캐너리 1회. 캐너리 자체 시간은 스펙 007 소관. 후보 구체화(git plumbing)는 후보당 수십 ms.
**Constraints**: 작업트리 무변경, origin 미푸시, 라이브 승격 0건. 캐너리 리플레이 데이터 없으면 fail-safe(종료 0). 결정론(LLM 미호출).
**Scale/Scope**: 세션당 L2/L3 후보 0~소수. v1 구체 노브 1종(max_tokens). cache_miss 는 proposal-only 유지(범위 밖, 문서화).

## Constitution Check

*GATE: Phase 0 전 통과 필수, Phase 1 후 재확인.*

| 원칙 | 평가 |
|------|------|
| **I. 포지션 사이징(K1)** | 터치 없음. 캐너리 검증은 시뮬레이션이며 risk/gates.py 미수정. ✅ |
| **II. 화이트리스트(K2)** | 터치 없음. ✅ |
| **III. LLM 판단 지점 한정(K3)** | K3 파일(`telemetry/meter.py`·`telemetry/store.py`) 미터치. `judgment/registry.py`·새 config 는 비커널. 모델/토큰 튜닝은 헌법 III 의 비용 관심사라 **반드시 L2(캐너리)** 로 분류돼 검증을 거친다(헌법 VI). 자동 적용 아님. ✅ |
| **IV. 추가-전용 감사(K4)** | 신규 이벤트 타입 추가(추가-전용). 기존 `AUTO_TUNED_*` 패턴(spec 005 커밋 `8bbfca2`)과 동일. 기존 이벤트·마이그레이션 무수정. K4 **추가-전용 터치 1건**(이벤트 타입 추가). ✅ |
| **V. 비밀 격리(K5)** | 터치 없음. git plumbing·캐너리는 비밀 미접근. ✅ |
| **VI. 백테스트→캐너리→본운영** | 이 기능이 정확히 "캐너리(2단계)"를 자율 후보에 연결. 합격해도 본운영(승격)은 운영자 게이트. ✅ 강화. |
| **VII. 외부 API 견고성** | 외부 API 신규 호출 없음(캐너리는 로컬 시뮬레이션). ✅ |
| **VIII.A 장중 배포 금지(K6)** | 캐너리 검증은 배포 아님(시뮬레이션). `worker/schedule.py` 미터치. 라이브 승격은 범위 밖. ✅ |
| **VIII.B 배포 자동화** | 이 기능은 배포를 일으키지 않음. 해당 없음. |
| **IX.A Kernel 포렌식** | K4 추가-전용 1건. 커밋 본문에 K4 터치 커밋 해시 명시 예정. K1·K2·K3·K5·K6·K-meta 터치 0건 목표. |
| **IX.B-2 캐너리 = 생산 배포 게이트** | 핵심 준수: 캐너리를 **검증용**으로만 호출. 합격이 곧 배포가 아니다. 라이브 승격 0건(FR-C12-07·SC-C12-04). ✅ |
| **IX.D 운영자 자율 수행** | 본 작업은 운영자 지시("우선순위대로 다음 작업 자율 수행")로 진행. ✅ |
| **X. 측정 기반 성장** | 후보는 측정(KPI 스냅샷) 신호에서 도출. 측정 부족이면 후보 미생성(기존 게이트 재사용). 캐너리는 spec 008 metrics 동일 잣대. ✅ 강화. |

**게이트 결과**: 통과. Kernel 터치는 K4 추가-전용 1건뿐(forensic callout 예정). 위반 없음 → Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/012-tuner-canary-queue/
├── plan.md              # 이 파일
├── spec.md              # 기능 명세
├── research.md          # Phase 0 — 후보 구체화·캐너리 투입 방식 결정
├── data-model.md        # Phase 1 — CanaryCandidate / CanaryValidationResult / 감사 이벤트
├── quickstart.md        # Phase 1 — 운영자/개발자 실행·검증 경로
├── contracts/
│   └── tuner-canary.md  # 내부 인터페이스 계약(튜너↔캐너리, 감사 이벤트 스키마)
└── checklists/
    └── requirements.md  # 스펙 품질 체크리스트(완료)
```

### Source Code (repository root)

```text
src/auto_invest/
├── tuner/
│   ├── candidate.py     # 신규: L2/L3 분류 → CanaryCandidate 구체화(결정론)
│   ├── canary_submit.py # 신규: 후보 → 임시 rev(git plumbing) → run_canary → 결과
│   ├── detect.py        # 수정: cost_drift/latency_degradation 에 구체 max_tokens 노브 제안
│   ├── knobs.py         # 수정: max_tokens 노브 계산(클램프·가역) 추가
│   ├── models.py        # 수정: CanaryCandidate / CanaryValidationResult 데이터 타입
│   ├── runner.py        # 수정: L2/L3 분기를 candidate→canary_submit 로 배선
│   └── report.py        # 수정: 캐너리 후보·검증 결과 섹션
├── judgment/
│   └── registry.py      # 수정: config/judgment_tunables.toml 폴백 로드(동작 불변)
└── persistence/
    └── audit.py         # 수정(K4 추가-전용): 신규 캐너리 후보/검증 이벤트 타입

config/
└── judgment_tunables.toml  # 신규(비커널): 판단 지점 max_tokens 튜닝 표면

tests/
├── unit/
│   ├── tuner/test_candidate.py        # 후보 구체화 결정론·클램프
│   ├── tuner/test_canary_submit.py    # 임시 rev 생성·정리·미푸시(임시 git repo)
│   ├── tuner/test_knobs_max_tokens.py # max_tokens 노브 계산
│   └── judgment/test_tunables_config.py # config 폴백(없으면 기존값)
└── integration/
    └── tuner/test_canary_pipeline.py  # detect→classify→candidate→(stub canary)→audit/report
```

**Structure Decision**: 기존 `src/auto_invest/tuner/` 패키지를 확장한다(신규 파일 2개 +
기존 4개 수정). 판단 튜닝 표면은 비커널 config 신설로 깨끗하게 분리. 캐너리 투입은
스펙 007 `run_canary` 를 **소비만** 하고 캐너리 내부는 손대지 않는다.

## Phasing (P1 → P2 → P3, 각 단계 독립 출시 가능)

- **P1 (MVP)**: L2/L3 분류 → 구조화된 CanaryCandidate → 튜너 리포트 + 추가-전용 감사 이벤트(멱등). dry-run 무변경. 캐너리 호출 없음. **출시 가치**: 죽은 로그 분기가 운영자가 보고 손으로 캐너리 돌릴 수 있는 실행 가능 후보로 바뀜.
- **P2**: 판단 튜닝 config + 후보 구체화(git plumbing, 무푸시·정리) + `run_canary` 자동 호출 + 합격/불합격 기록. 리플레이 데이터 없으면 fail-safe. 후보별 오류 격리. **출시 가치**: 후보가 실제로 캐너리 검증을 받음.
- **P3**: 안전 하드닝·관측 — "라이브 미승격(운영자 게이트)" 명시, `auto-invest tune` 출력 표면, 작업트리·미푸시·라이브 무변경 불변 테스트, 집계 요약.

## Complexity Tracking

위반 없음 — 비워 둠.
