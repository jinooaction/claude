# Implementation Plan: 자동 룰 설계자 (Autonomous Rule Designer)

**Branch**: `claude/spec-010-auto-rule-designer` | **Date**: 2026-05-19 | **Spec**: [spec.md](./spec.md)

## Summary

운영자가 자연어 한 줄로 의도를 적으면 시스템이 룰을 자동 생성·정적 검증·paper-run으로 모의 검증한 뒤, 운영자 OK 한 줄 받으면 라이브 시작. 핵심 기술 접근:

1. **신규 CLI 서브커맨드 `auto-invest design`**: cli.py에 추가. mutex → KIS 잔고 조회 → Claude 호출 → 정적 검증 → paper-run 트리거 → 운영자 OK 인터랙티브 → 자동 라이브.
2. **신규 패키지 `src/auto_invest/design/`**: 7개 모듈(prompt·claude_client·validator·mutex·verifier·state·deploy).
3. **K3 + K4 additive**: `telemetry/meter.py`에 `rule_design` cost-band 추가, `persistence/audit.py`에 4개 페이로드 추가.
4. **백테스트 stub 처리**: spec 008 미완성이므로 import 가드. spec 008 완성 후 별도 PR에서 연결.
5. **paper-run 일주일 분리**: design 명령은 paper-run 1일분만 동기. 나머지 6일은 background. 운영자가 `auto-invest design --check`로 사후 확인.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer (CLI), httpx (KIS API), pydantic (config·payload), anthropic SDK (Claude), pytest (테스트). 모두 기존 의존성.
**Storage**: SQLite audit_log 기존 테이블 그대로. 신규 테이블·migration 0개.
**Testing**: pytest. Claude API는 monkeypatch로 mock. 단위 테스트는 `tests/unit/test_design_*.py`, 통합은 `tests/integration/test_design_*.py`.
**Target Platform**: Linux server. foreground CLI 인터랙티브 데몬.
**Project Type**: CLI + library (기존 spec 001~009와 동일 구조).
**Performance Goals**: design 명령 1회 < 24시간 (SC-001 = 백테스트 + paper-run 1일분 동기).
**Constraints**:
  - Claude API 비용 1회 호출당 < $1 (SC-002).
  - 생성된 룰 정적 검증 통과율 100% (SC-003).
  - paper-run 단계에서 KIS 주문 API 호출 0건 (SC-008 = spec 009 SC-001 인계).

## Constitution Check

| Principle | 영향 | Compliance |
|-----------|------|-----------|
| I. Position Sizing (K1) | 자동 룰도 cap 게이트 활성. 정적 검증 통과 필수. K1 코드 무수정. | ✅ K1 파일 무수정 |
| II. Deny-by-Default Whitelist (K2) | 자동 룰의 종목은 whitelist에 자동 등재 후 사용. K2 코드 무수정. | ✅ |
| III. LLM at Judgment Points Only (K3) | `rule_design` 새 판단점 추가. K3 cost-band additive. | ⚠️ K3 추가 변경 — IX.D 자율 머지 |
| IV. Append-Only Audit (K4) | 4개 페이로드 추가, 기존 무수정. | ⚠️ K4 추가 변경 — IX.D 자율 머지 |
| V. Secret Isolation (K5) | 시크릿 무손상. | ✅ |
| VI. Backtest → Canary → Full Live | paper-run 단계 후 운영자 OK 1회로 라이브. canary 자동화는 spec 007 완성 후 별도 PR. | ✅ |
| VII. External API Robustness | Claude·KIS 모두 ResilientClient 사용. | ✅ |
| VIII.A No Market-Hours Deploys | 자동 라이브 시작이 시장 시간 외라면 spec 006 deploy guard가 막음. K6 무수정. | ✅ |
| IX.D Operator Autonomy Supremacy | 운영자 자율 수행 목표에 직결. | ✅ |

**결론**: K3 + K4 추가 변경 두 건. 둘 다 IX.D 자율 머지 채널 (constitution v3.0.0). PR 본문에 두 commit hash 명시 의무.

## Project Structure

### Documentation

```text
specs/010-auto-rule-designer/
├── plan.md                     # 이 파일
├── spec.md                     # 기능 스펙
├── research.md                 # Phase 0
├── data-model.md               # Phase 1
├── quickstart.md               # Phase 1
├── contracts/
│   ├── design-cli.md           # auto-invest design 서브커맨드 계약
│   ├── design-audit-events.md  # 4개 신규 audit 페이로드 계약
│   └── claude-prompt.md        # Claude 시스템 prompt 계약 (안전 제약 포함)
├── checklists/
│   └── requirements.md
└── tasks.md                    # /speckit-tasks
```

### Source Code

```text
src/auto_invest/
├── cli.py                                # +design 서브커맨드
├── persistence/audit.py                  # K4 additive: 4개 페이로드
├── telemetry/meter.py                    # K3 additive: rule_design cost-band
└── design/                               # 신규 패키지
    ├── __init__.py
    ├── prompt.py                         # Claude system prompt 조립
    ├── claude_client.py                  # anthropic SDK 호출 + token usage 기록
    ├── validator.py                      # 생성된 TOML 정적 검증
    ├── mutex.py                          # design 명령 mutex (spec 009 패턴)
    ├── verifier.py                       # 백테스트 stub + paper-run 트리거
    ├── deploy.py                         # 운영자 OK 받고 라이브 시작
    └── state.py                          # 일주일 paper-run 중간 상태 관리

tests/
├── unit/
│   ├── test_design_audit_payloads.py
│   ├── test_design_mutex.py
│   ├── test_design_validator.py
│   ├── test_design_prompt.py
│   └── test_design_state.py
└── integration/
    ├── test_design_claude_mock.py        # Claude mock으로 end-to-end
    └── test_design_cli.py                # design 명령 진입점 통합
```

**Structure Decision**: spec 009와 동일하게 `design/` 신규 서브패키지로 격리. design 기능이 비활성일 때 import 비용 0.

## Implementation Strategy (단계적 출하)

본 스펙은 spec 008(백테스트)에 의존하지만 spec 008은 아직 미완성. 따라서:

1. **이번 PR**: design 명령 본체 + Claude 호출 + 정적 검증 + paper-run 트리거 + 운영자 OK + 라이브 시작. 백테스트는 import 가드(`try ... except ModuleNotFoundError`)로 처리하고 한글 경고 출력.
2. **spec 008 완성 후 별도 PR**: `verifier.py`에서 백테스트 호출 활성화.

이렇게 하면 spec 010 자체는 지금 머지 가능 + spec 008 완성 후 자동으로 백테스트 단계가 연결됨 (점진 출하).

## Complexity Tracking

| 변경 | Why Needed | Simpler Alternative Rejected Because |
|------|-----------|------------------------------------|
| K3 cost-band 추가 (`rule_design`) | constitution III "judgment points" 원칙: LLM 호출 사이트마다 별도 KPI 한도 필요 (FR-010). | cost-band 없이 호출 — 거부: spec 002 KPI가 호출별 한도를 강제하지 못함. |
| K4 페이로드 4종 추가 | RULE_DESIGN_* 이벤트가 기존 페이로드와 구분되어야 사후 추적 가능 (FR-008, SC-004). | 기존 LLM_CALL 페이로드 재사용 — 거부: 호출 종류 식별 불가, FR-008 위반. |
| `design/` 신규 서브패키지 | 격리·테스트 용이성. 비활성 시 import 비용 0. | 모든 코드를 cli.py에 인라인 — 거부: 250+ LOC가 cli.py에 누적되어 회귀 위험. |
| 백테스트 stub 가드 | spec 008 미완성에 대한 점진 출하 전략. | spec 008 완성을 기다림 — 거부: spec 010 머지 차단, IX.D 자율 수행 위반. |
