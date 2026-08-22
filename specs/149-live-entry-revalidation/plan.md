# Implementation Plan: 최신 엣지 재검증과 병렬 탐색

**Branch**: `Codex/149-live-entry-revalidation-parallel-edge` | **Date**: 2026-08-22 | **Spec**: [spec.md](spec.md)

## Summary

실제 주문 job에 첫 체결 전 최신 탐색 자격 재검증을 추가하고, 같은 판정을 자본 사다리에 연결해 자격 상실 시 단 0으로 자동 복귀시킨다. pipeline 감시 수집은 개별 ref 재시도로 오탐을 제거한다. 자율 작업 루프는 forward 관찰 패킷과 별도로 증거 지문 기반 no-live challenger를 발행한다. 주문 뒤에는 기존 체결·손익 측정에 정합성 점검을 연결한다.

## Technical Context

**Language/Version**: Python 3.11, Bash, GitHub Actions YAML
**Primary Dependencies**: Typer, 표준 JSON, 기존 SSH fixed gateway
**Storage**: Git sidecar, 기존 SQLite 전략 장부
**Testing**: pytest, ruff, shell/YAML 정적 검증
**Target Platform**: GitHub Actions와 Linux production worker
**Constraints**: 첫 체결 전 fail-closed, 실제 주문 직전 검사, 매도·위험 축소 경로 보존, 연구 주문 0건

## Constitution Check

- I/II/III: 한도·whitelist·주문 제한을 변경하지 않는다.
- IV/V: 기존 추가 전용 감사와 비밀값 경계를 유지한다.
- VI/VIII.A: `Backtest -> Canary -> Full`, 정규장, production 서명을 유지한다.
- X.4: 단 1 진입의 PSR 0.80, 40관측, exact fingerprint를 주문 직전에도 보존하며 20%를 넘기지 않는다.
- X.5: challenger는 no-live만 수행하고 5중 재지정 게이트를 우회하지 않는다.
- 위험 등급 4: 실제 주문 허용 조건을 강화하고 자동 무장 해제를 추가한다. `this changes the safety perimeter` 기록이 필요하다.
- 되돌림: 주문 전 재검증 step과 단 1 자동 강등 조건을 되돌리면 기존 동작으로 복귀한다. 감사·체결 장부는 삭제하지 않는다.

## Project Structure

```text
specs/149-live-entry-revalidation/
src/auto_invest/portfolio/live_entry_revalidation.py
src/auto_invest/portfolio/capital_ladder.py
src/auto_invest/analytics/autonomous_work_execution.py
.github/workflows/rebalance-live-canary.yml
.github/workflows/pipeline-liveness.yml
scripts/live_entry_revalidation_probe.py
tests/unit/
tests/integration/
```

## Design Decisions

1. 최신 자격 검사는 브로커 주문 서명 전에 실행한다.
2. 체결 0건일 때만 탐색 진입 자격을 다시 요구해 기존 포지션의 위험 축소를 막지 않는다.
3. 자본 사다리는 명시적 체결 0건과 자격 실패가 함께 있을 때만 단 0으로 내린다.
4. liveness 일괄 fetch 결과가 없으면 해당 ref를 직접 다시 fetch한다.
5. challenger 지문은 forward 관측을 5개 단위로 묶어 지속 탐색과 중복 억제를 함께 만족한다.
