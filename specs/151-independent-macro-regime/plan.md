# Implementation Plan: 독립 거시 레짐 전략군

**Branch**: `Codex/151-independent-macro-regime` | **Date**: 2026-08-23 | **Spec**: [spec.md](spec.md)

## Summary

스펙 150의 공장·누적 다중검정·10% 연구 캐너리 연결은 유지하고, 가격 매개변수와 다른
거시 입력을 쓰는 네 전략군 64개를 추가한다. 시장 자료와 발표 지연을 반영한 월간 스냅숏,
단일 목표 비중 함수, 사전 탐색 192회 재생 장부를 먼저 완성한 뒤 홀드아웃을 한 번만 연다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: 표준 라이브러리, Pydantic, NumPy, 기존 공장·포트폴리오 모듈
**Storage**: 공개 자료 sidecar CSV/JSON, 추가 전용 시험 장부, 공장 판정 JSON/Markdown
**Testing**: pytest, ruff, workflow YAML·셸 구문·정적 불변식
**Target Platform**: GitHub Actions Linux, Vultr 주문 미리보기·production 경로
**Project Type**: Python CLI, 분석 모듈, 포트폴리오 실행기, 자동화 workflow
**Performance Goals**: 64개 공식 후보와 192개 재생 시도를 15분 안에 평가
**Constraints**: 미래 누출 없음, 유료 API 없음, long-only, 무레버리지, 결측 fail-closed
**Scale/Scope**: SPY·IEF·GLD 신호, SPYM·IEF·GLDM 실행, 누적 시도 총 512

## Constitution Check

- 원칙 I·II: 기존 K1 한도와 K2 허용 종목을 유지하고 신규 종목을 추가하지 않는다.
- 원칙 IV·V: 거시 자료 커밋·시각·지문을 감사 증거로 남기며 비밀값을 읽지 않는다.
- 원칙 VI: Backtest -> NAV 10% 연구 Canary -> 20% 탐색 Canary -> 상위 단계를 유지한다.
- 원칙 VII: FRED·Cboe 오류, 오래됨, 빈 파일은 재시도 뒤 차단하며 성공으로 대체하지 않는다.
- 원칙 VIII.A: 주문은 기존 정규장 production 경로만 사용한다.
- 원칙 X.2: 연구와 주문 미리보기가 같은 목표 비중 함수를 사용한다.
- 원칙 X.4: 단 0 진입 조건과 10% 이상 승격·하향 조건을 바꾸지 않는다.
- 원칙 X.5: 후보 합격은 자동 자본 상속이 아니며 기존 정확한 지문·강화 캐너리 관문을 거친다.
- 헌법·kernel 목록 변경은 계획하지 않는다. 필요해지면 별도 K-meta 판단과 커밋 표식을 요구한다.

## Project Structure

```text
specs/151-independent-macro-regime/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── EXPLORATORY-FINDINGS.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── contracts/macro-strategy-factory-evidence.md

src/auto_invest/analytics/
├── macro_strategy_factory.py
└── strategy_factory.py

src/auto_invest/market_data/
├── macro_regime.py
└── public_data.py

src/auto_invest/config/rules.py
src/auto_invest/strategy/rebalance.py
src/auto_invest/execution/rebalancer.py
src/auto_invest/portfolio/autoarm.py
src/auto_invest/cli.py

scripts/
├── macro_strategy_factory_probe.py
└── strategy_factory_probe.py

deploy/
├── public-data.toml
└── live-canary-on-instance.sh

.github/workflows/
├── collect-public-data.yml
└── autonomous-strategy-factory.yml

tests/unit/
tests/integration/
```

**Structure Decision**: 자료 수집, 순수 정책 계산, 공장 판정, 실제 주문 실행을 분리하되
목표 비중 계산 함수만 연구와 주문 경로가 함께 사용한다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 없음 | 기존 공장과 자본 관문 안에서 확장 | 별도 주문 경로나 별도 자본 사다리는 만들지 않음 |

## Phase 0: Research Decisions

1. 공식 전달 경로는 FRED DGS2·DGS10·CPIAUCNS·SAHMREALTIME과 Cboe VIX로 고정한다.
2. 금리와 VIX는 당일 장 마감 뒤, CPI와 삼 규칙은 45일 지연 뒤 다음 기간부터 쓴다.
3. 192개 대화 중 탐색 조합은 정식 후보가 아니지만 모두 재생해 다중검정 벌점에 넣는다.
4. 공식 후보 문법은 홀드아웃 재실행 전에 변경할 수 없고 변경하면 새 시도 묶음이다.
5. 거시 자료가 없으면 자동 현금 청산하지 않고 해당 재조정 전체를 주문 전에 차단한다.

## Phase 1: Design Gates

- 자료 심층화가 1990년 이전부터 이어지는지 검증한다.
- 개발 1990~2006과 홀드아웃 2007~현재를 코드에서 분리한다.
- 네 전략군 64개와 사전 탐색 192개의 정확한 문법·ID를 동결한다.
- 두 기준 포트폴리오는 균등 3자산과 `factory-relative_momentum-cb2e32f74390`으로 고정한다.
- 정책 함수의 연구/주문 경로 동일성을 속성 시험으로 고정한다.
- 공장 판정이 512회 누적 벌점을 사용하지 않으면 fail-closed한다.
- 64개 공식 후보와 192개 재생이 15분 안에 끝나는 성능 회귀를 추가한다.
- 합격 이후에도 기존 공장·강화 캐너리·정합성·자본 사다리를 그대로 재사용한다.
