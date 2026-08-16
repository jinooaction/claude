# Implementation Plan: Daily Cross-Asset ML Challenger

**Branch**: `Codex/146-daily-cross-asset-ml` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

## Summary

KIS가 저장한 11개 ETF 조정 일봉을 주간 패널로 바꾸고, 정규화 선형 모델과 얕은 부스팅 모델로 다음 주 상대수익을 학습한다. 검증 오차를 반영한 하한 예측 상위 자산만 제한적으로 배분하며, 비용과 두 기준전략을 동일한 미래 구간에서 비교한다. 결과는 연구 사이드카와 후보 패키지로만 발행한다.

## Technical Context

**Language**: Python 3.11
**Dependencies**: numpy, scikit-learn, SQLite/KIS 기존 읽기 전용 시세 경로
**Storage**: `data/forward_wide.db`, JSON/Markdown sidecar
**Testing**: pytest, ruff, YAML/static safety checks
**Constraints**: deterministic, no leakage, no order call, long-only

## Constitution Check

- I-II 한도·거부 기본값: PASS. 고정 유니버스, 25% 종목 상한, 99% 총 상한이다.
- III AI 판단: PASS. ML은 수익을 예측하고 결정적 관문이 후보 자격을 판정한다.
- IV 감사: PASS. 자료·모델·특징 지문과 재현 명령을 남긴다.
- V 비밀값: PASS. 기존 KIS 환경값을 재사용하고 출력하지 않는다.
- VI 단계 승격: PASS. 이 기능은 Backtest 후보까지만 만든다.
- VII 외부 API: PASS. KIS 시세 조회 실패는 `BLOCKED`다.
- VIII-X 변경·커널·측정: PASS. Kernel과 live 돈 경로는 바꾸지 않고 되돌림은 PR revert다.

## Project Structure

```text
src/auto_invest/analytics/daily_cross_asset_ml.py
scripts/daily_cross_asset_ml_probe.py
.github/workflows/daily-cross-asset-ml.yml
deploy/observe-on-instance.sh
deploy/repair-ssh-boundary.sh
tests/unit/test_daily_cross_asset_ml.py
tests/integration/test_daily_cross_asset_ml_probe.py
```
