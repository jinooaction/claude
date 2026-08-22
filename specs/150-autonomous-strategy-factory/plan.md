# Implementation Plan: 자동 전략 공장과 연구 캐너리

**Branch**: `Codex/150-autonomous-strategy-factory` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)

## Summary

기존 후보 공장이 모든 전략 후보를 같은 설정으로 재검사하는 구조를 후보별 설정 생성·실행·시도 장부·전체 다중검정 판정 구조로 교체한다. 첫 64개 후보는 기존 live 포트폴리오 엔진이 표현할 수 있는 주식·채권·금 전략으로 제한한다. 완전 합격 후보는 강화 캐너리와 지문 정합을 거쳐 새 NAV 10% 연구 캐너리 단에만 진입하며, 10%를 넘는 기존 관문은 유지한다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: 표준 라이브러리, Pydantic, 기존 auto-invest 분석·백테스트·자본 사다리 모듈
**Storage**: JSON sidecar와 추가 전용 시험 장부
**Testing**: pytest, ruff, workflow 구조 회귀시험
**Target Platform**: GitHub Actions Linux, 기존 Vultr 관찰 경로, KIS 실계좌 주문 경로
**Project Type**: Python CLI와 자동화 workflow
**Performance Goals**: 한 묶음 64개 후보를 workflow 시간 제한 안에서 완료하고 부분 결과를 보존
**Constraints**: 브로커 호출 없는 연구 실행, 결정론, 자료·코드·전략 지문, 모든 시도 보존, fail-closed
**Scale/Scope**: 첫 묶음 4개 전략군 64개 후보, 단일 승자, NAV 10% 연구 캐너리

## Constitution Check

- 원칙 I·II: K1 캡과 K2 허용 종목을 유지한다.
- 원칙 IV·V: 감사 로그와 비밀값 분리를 유지한다.
- 원칙 VI: Backtest -> 10% 연구 Canary -> 20% 탐색 Canary -> Full 순서를 유지한다.
- 원칙 VIII.A: 연구 workflow는 주문하지 않고 실제 주문은 기존 정규장 경로만 사용한다.
- 원칙 IX: 헌법 X.4 변경은 K-meta 커밋에 `this changes the safety perimeter`를 기록한다.
- 원칙 X.4: 현행 20% 탐색 단 앞에 더 작은 10% 단을 추가한다. 10% 초과에는 기존 40개 forward 관측이 필요하다.
- 원칙 X.5: 전략 재지정 5중 관문은 유지하며 신규 공장 승자는 자동으로 기존 자본을 상속하지 않는다.
- 누락·오래됨·지문 불일치·부분 실행은 단 0을 유지한다.

## Project Structure

```text
specs/150-autonomous-strategy-factory/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── contracts/strategy-factory-evidence.md

src/auto_invest/analytics/
├── strategy_factory.py
└── backtest_overfitting.py

src/auto_invest/portfolio/
├── capital_ladder.py
└── live_entry_revalidation.py

scripts/
└── strategy_factory_probe.py

.github/workflows/
└── autonomous-strategy-factory.yml

tests/unit/
├── test_strategy_factory.py
├── test_backtest_overfitting.py
└── test_capital_ladder.py

tests/integration/
└── test_strategy_factory_probe.py
```

**Structure Decision**: 기존 분석, 자본 사다리, probe, workflow 경계를 재사용하고 신규 공장 로직은 순수 분석 모듈로 격리한다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 헌법 X.4 첫 진입 변경 | 백테스트 합격 전략도 40개 forward 관측 전 주문 불가인 기다림을 없애되 초기 노출을 절반으로 줄임 | 기존 20% 단을 그대로 완화하면 손실 표면이 더 크고, 대기 유지면 사용자 목표를 달성하지 못함 |
