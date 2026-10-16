# Implementation Plan: Capital Path Readiness Loop

**Branch**: `Codex/076-capital-path-readiness-loop` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/076-capital-path-readiness-loop/spec.md`

## Summary

2026-10-16 보정 계획: 공통 순수 함수 `money_path_status.live_blocking_detail`에서
명시된 실제 차단 설명만 선택한다. 076 준비도·078 정렬·080 운영판·183 모바일 소비자를
같이 보정하고 기존 JSON 스키마/상태 판정·주문 권한은 보존한다. 실제 원본 재생과
추가 반례를 작은 로컬 검사로 확인하고 기존 volume-priority 전체 회귀의 경로 필터에
이 소비자/검사들을 연결해 정확 PR HEAD를 GitHub에서 검증한다. 새 스케줄/생산 실행 경로는 없다.
기존 암호화 검사와 필수 반례는 유지한다. 전체 큰 검사는 로컬에서 실행하지 않는다.
원본 accb5f4d 시각을 현재 실시간 계좌 상태로 바꾸어 표시하지 않는다.

Add a read-only capital path readiness loop that consumes already-published sidecars, classifies current capital readiness, highlights the nearest safe money action, suppresses rejected strategy/portfolio candidates, and publishes a durable sidecar for other loops and future sessions.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Standard library JSON/dataclass parsing, existing pytest/ruff, GitHub Actions sidecar publishing  
**Storage**: JSON and Markdown sidecars on `automation/capital-path-readiness-last-run`; no database  
**Testing**: pytest, ruff  
**Target Platform**: Local repo and GitHub Actions runner  
**Project Type**: Python analytics library + probe script + GitHub Actions workflow  
**Performance Goals**: Parse current sidecars and emit JSON/Markdown in under 1 second locally excluding package startup  
**Constraints**: Read-only evidence consumption; no broker, order, capital, whitelist, caps, live strategy, secret, constitution, or kernel changes  
**Scale/Scope**: Tens of sidecar inputs and candidates; deterministic single-run sidecar output

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Reason |
|-----------|--------|--------|
| I. Position sizing and exposure limits | PASS | No order sizing or capital mutation path touched. |
| II. Deny-by-default whitelist | PASS | No universe or whitelist change. |
| III. Claude judgment points | PASS | No LLM call sites added. |
| IV. Append-only audit and reconciliation | PASS | Reads and publishes sidecars only; no audit deletion. |
| V. Secret isolation | PASS | No secret inputs required; KIS is not called. |
| VI. Backtest -> Canary -> Full | PASS | Readiness routes to existing gates and does not bypass validation. |
| VII. External API robustness | PASS | No new external API calls. |
| VIII.A No live deploys during market hours | PASS | Existing deploy guard remains; no live money deployment. |
| IX/X autonomous change safety | PASS | Adds read-only operating loop; no constitution or kernel touch. |

## Project Structure

### Documentation (this feature)

```text
specs/076-capital-path-readiness-loop/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── capital-path-readiness.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
src/auto_invest/analytics/capital_path_readiness.py
scripts/capital_path_readiness_probe.py
.github/workflows/capital-path-readiness.yml
src/auto_invest/analytics/pipeline_liveness.py
tests/unit/test_capital_path_readiness.py
tests/integration/test_capital_path_readiness_probe.py
tests/integration/test_pipeline_liveness_probe.py
```

**Structure Decision**: Create a new loop instead of expanding `money_path.py`. `money_path` remains the source of truth for live money state; this feature consumes it alongside promotion/evolution/reassignment surfaces and publishes a higher-level readiness package.

## Complexity Tracking

No constitution or architecture violations.
