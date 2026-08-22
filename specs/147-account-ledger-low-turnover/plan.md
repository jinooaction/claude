# Implementation Plan: 신뢰 가능한 라이브 증거와 저회전 AI 후보

**Branch**: `Codex/147-account-ledger-low-turnover` | **Date**: 2026-08-22 | **Spec**: [spec.md](spec.md)

## Summary

기존 성과 엔진의 체결 재구성을 유지하되 검증된 시작 전 보유 종목을 전략 범위에서 제외하는 순수 필터와 측정 계약 지문을 추가한다. live NAV·성장·forward 입력은 최신 계약 표본만 사용하고, 정합성 복구는 읽기 전용 판정으로만 노출한다. 연구 경로에는 기존 일봉 교차자산 AI를 감싸는 최소 보유기간·거래 임계값·비용 인식 배분을 추가한다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer, NumPy, scikit-learn, Pydantic, SQLite
**Testing**: pytest, ruff
**Target Platform**: GitHub Actions와 Linux production worker
**Constraints**: 주문 0건, halt 자동 해제 0건, 감사 로그 추가 전용, 기존 K1/K2·자본 사다리 보존

## Constitution Check

- I/II: 주문 제한과 허용 종목은 변경하지 않는다.
- IV: 기존 감사 행은 수정하지 않고 선택 필드만 추가한다.
- V: 비밀값을 새로 읽거나 저장하지 않는다.
- VI: Backtest -> Canary -> Full 단계를 유지한다. AI 결과는 연구 전용이다.
- X: 자본 승격은 최신의 오염되지 않은 측정 증거만 소비한다.
- 위험 등급 4: 돈 경로 입력을 강화하지만 실제 주문·자본·전략은 변경하지 않는다.
- 되돌림: 새 측정 계약 필드와 필터·워크플로 인자만 되돌리면 기존 동작으로 복귀한다. 감사 행은 그대로 남는다.

## Project Structure

```text
src/auto_invest/performance/
src/auto_invest/portfolio/
src/auto_invest/reconciliation/
src/auto_invest/analytics/
tests/unit/
tests/integration/
deploy/
.github/workflows/
specs/147-account-ledger-low-turnover/
```

## Design Decisions

1. 외부 보유 청산을 삭제하지 않고 전략 보고에서 제외 증거로 남긴다.
2. 계약 지문이 달라지면 과거 NAV 점을 이어 붙이지 않는다.
3. 정합성 OK는 자동 resume가 아니라 resume 가능성 보고의 필요조건일 뿐이다.
4. 저회전 배분은 예측 모델을 다시 과적합하지 않고 거래 결정층에 보수적 제약을 둔다.
