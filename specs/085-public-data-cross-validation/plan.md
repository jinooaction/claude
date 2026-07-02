# Implementation Plan: 공개 데이터 교차 검증 확장

**Branch**: `Codex/085-public-data-cross-validation` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/085-public-data-cross-validation/spec.md`

## Summary

FRED graph CSV DGS2/DGS10을 연구 전용 공개 데이터 수집 채널에 추가하고, 재무부 UST2Y/UST10Y와의 수준 대조를 summary cross_checks에 더한다. FRED는 최신 후보 검증에서 channel user-agent가 아니라 기본 HTTP client user-agent로 열리는 증거가 있었으므로, FRED 수집 항목에만 user-agent 모드를 명시적으로 허용한다. 라이브 매매 신호, KIS 가격 경로, 주문, 자본, whitelist/caps는 변경하지 않는다.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: httpx, Typer CLI, pytest, ruff; new dependency 없음  
**Storage**: repository files plus research-only sidecar branch output; live DB untouched  
**Testing**: pytest focused tests, full `uv run pytest`, `uv run ruff check src tests`  
**Target Platform**: GitHub Actions Linux runner and local Python test environment  
**Project Type**: Python CLI and workflow-backed research data channel  
**Performance Goals**: Collection remains within existing 12-minute collect step and 480-second wall-clock budget  
**Constraints**: No secrets, no broker API, no live trading data write, no KIS path consumption, fail-soft per item  
**Scale/Scope**: Add 2 FRED rate series and 2 FRED-vs-Treasury level checks to existing 9-item public-data channel

## Constitution Check

- **I Position caps**: PASS. No order path or sizing logic touched.
- **II Whitelist**: PASS. No tradeable universe, order type, session, or account whitelist touched.
- **III LLM judgment points**: PASS. No LLM call surface touched.
- **IV Audit/reconciliation**: PASS. No audit schema or broker reconciliation path touched.
- **V Secret isolation**: PASS. FRED graph CSV is keyless; no new secret or API key.
- **VI Staged rollout**: PASS. Research-only evidence surface; no strategy promotion or live rollout.
- **VII External API robustness**: PASS with controls. Existing bounded timeout, retry, fail-soft item quarantine, summary diagnostics, and cross-check gates remain; FRED uses an explicit user-agent mode because latest probes show channel UA can tarpit while default UA succeeds.
- **VIII.A Market-hours deploy**: PASS. PR merge changes code/docs only; production deploy remains governed by existing deploy workflow.
- **IX Self-modification boundary**: PASS. No Kernel file touched.
- **X Measurement-driven growth**: PASS. The change increases measurement reliability before future strategy/data decisions.

## Project Structure

### Documentation (this feature)

```text
specs/085-public-data-cross-validation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── public-data-fred-cross-check.md
└── tasks.md
```

### Source Code (repository root)

```text
deploy/public-data.toml
.github/workflows/collect-public-data.yml
src/auto_invest/market_data/public_data.py
tests/unit/test_public_data.py
tests/unit/test_collect_public_data_workflow.py
CLAUDE.md
HANDOFF.md
HANDOFF-089-PUBLIC-DATA-CROSS-VALIDATION.md
```

**Structure Decision**: Use the existing single Python project structure. The feature extends the current public-data module, config, workflow comments, and tests; no new package or dependency is needed.

## Complexity Tracking

No constitution violation or added architectural complexity.
