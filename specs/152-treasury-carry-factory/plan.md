# Implementation Plan: Independent Treasury Carry Factory

**Branch**: `Codex/152-independent-asset-carry` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)

## Summary

공식 미국 국채 3개월·2년·5년·10년·30년 금리로 장기 전용 만기 회전 후보 64개를
사전 등록된 문법대로 검증한다. 과거 512회와 현재 64회를 합친 576회 다중검정,
동일 국채 사다리 대조군, 기존 3자산과의 분산 이득, 거래비용, 연구-주문 목표 비중
동일성을 모두 통과한 단 하나의 후보만 기존 캐너리 사다리 입력으로 발행한다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, NumPy, existing Typer CLI and public-data collector
**Storage**: Public-data sidecar CSV/JSON, strategy-factory JSON/Markdown, append-only JSONL trial ledger
**Testing**: pytest, ruff, deterministic fixtures, production no-order workflow
**Target Platform**: GitHub Actions research worker and existing Linux dry-run/live-canary worker
**Project Type**: Single Python package with CLI, workflows, deployment configs, and SDD artifacts
**Performance Goals**: Five public series collected within the existing 480-second budget; 64 current plus 512 prior trial decision within 15 minutes
**Constraints**: Long-only, unlevered, official keyless data, no future leakage, one-month development/holdout embargo, monthly decisions, fail closed, no order/capital/whitelist change without all gates
**Scale/Scope**: Five maturity sleeves, four strategy families, exactly 64 current and 576 cumulative trials, ten chronological score segments

## Constitution Check

| Principle | Design response | Status |
|---|---|:---:|
| I Position limits | Factory moves no money. Any later plan still uses existing per-trade, per-symbol, and global caps. | PASS |
| II Deny by default | Research mappings do not widen live whitelist. Unknown or mismatched execution symbols fail before broker access. | PASS |
| III Judgment points | No per-bar LLM call. Candidate grammar is deterministic and frozen. | PASS |
| IV Audit and reconciliation | Trial ledger is append-only; any later order remains in existing audited reconciled route. | PASS |
| V Secret isolation | Official collection is keyless. Tests and reports contain no account secret. | PASS |
| VI Backtest -> Canary -> Full | A factory winner is only research-canary eligible and cannot skip stages. | PASS |
| VII External failure | Missing, stale, malformed, or mismatched data and evidence fail closed. | PASS |
| VIII.A Market hours | Research workflow moves no capital. Existing deployment guard remains unchanged. | PASS |
| IX Self modification | Money-path additions receive full SDD, tests, PR evidence, and forensic review. | PASS |
| X Measured growth | Promotion requires measured holdout, multiplicity, costs, and diversification evidence. | PASS |

## Project Structure

### Documentation

```text
specs/152-treasury-carry-factory/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── treasury-carry-evidence.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/
├── analytics/treasury_carry_factory.py
├── config/rules.py
├── execution/rebalancer.py
├── market_data/public_data.py
├── portfolio/autoarm.py
└── strategy/rebalance.py
scripts/treasury_carry_factory_probe.py
tests/unit/test_treasury_carry_factory.py
tests/integration/test_treasury_carry_factory_probe.py
deploy/public-data.toml
.github/workflows/autonomous-strategy-factory.yml
```

**Structure Decision**: 기존 거시 공장과 같은 한 패키지 구조를 유지하되, 국채곡선 파싱·수익
근사·후보 평가를 새 분석 모듈에 격리한다. 실제 목표 비중 계산만 전략 모듈에 둬 연구와 실행이
한 함수를 공유하게 한다.

## Phase 0: Research Decisions

1. 공식 재무부/FRED CMT 시계열을 사용하고 관측 월 다음 달에만 신호를 적용한다.
2. 만기별 수익은 전월 수익률의 캐리와 수정 듀레이션 곱하기 금리 변화의 가격효과로 보수적으로 근사한다.
3. 30년 공백은 결측으로 보존하고 그 기간 해당 슬리브만 선택 대상에서 제외한다.
4. 후보 문법은 네 전략군 x 최대 만기 2 x 신호 관찰창 2 x 선택 폭 2 x 신호 강도 2 = 64로 고정한다.
5. 이전 공장의 완전한 512개 점수와 지문을 입력 계약으로 받아 576회가 아니면 승자를 금지한다.

## Phase 1: Design

1. Public-data가 다섯 만기 금리를 수집·신선도 검증하고 기존 교차검증을 유지한다.
2. `TreasuryCurveSnapshot`은 월별 마지막 유효 관측과 최신 일별 관측을 같은 형식으로 만든다.
3. `TreasuryCarryPolicyConfig`와 `treasury_target_weights`를 연구·주문 공용 순수 함수로 추가한다.
4. 공장은 64개 후보의 10/25/50bp 결과와 열 구간 점수를 계산하고 512개 과거 증거와 합친다.
5. 국채 사다리 우위와 기존 3자산 혼합 분산 이득을 모두 판정한다.
6. Probe와 workflow는 기존 sidecar를 읽고 새 결과와 append-only 장부를 발행한다.
7. 승자가 없으면 `selected_candidate_id`, 실행 설정, 자본, 주문은 비어 있어야 한다.

## Implementation Sequence

1. 데이터 시리즈와 파서/스냅샷 테스트
2. 공용 정책 설정과 목표 비중 함수
3. 수익 근사, 후보 생성, 후보 평가
4. 576회 다중검정과 승격 관문
5. CLI/probe/workflow/sidecar 배선
6. 연구-주문 동일성 및 실패 닫힘 통합 테스트
7. 전체 검증, PR, 배포, 생산 no-order 실행, HANDOFF

## Rollback

새 정책 필드, 분석 모듈, probe, workflow 분기와 추가 public-data 시리즈를 하나의 기능 PR로
되돌릴 수 있다. 기존 거시 정책과 라이브 설정은 선택 필드가 없을 때 바이트 수준으로 기존
경로를 유지한다. 어떤 실패에서도 현재 `PREVIEW_ONLY`, 자본 0, 주문 0 상태를 넓히지 않는다.

## Post-Design Constitution Check

설계 후에도 헌법 I~VII, VIII.A, IX, X를 모두 만족한다. 새 코드는 잠재적 목표 비중을 만들 수
있으므로 위험 등급 4를 유지하지만, 실주문 권한은 기존 별도 증거와 사다리 바깥으로 이동하지 않는다.
