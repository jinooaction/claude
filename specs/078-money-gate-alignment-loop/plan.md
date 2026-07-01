# 구현 계획: 돈 경로 게이트 정렬 루프

**브랜치**: `Codex/078-money-gate-alignment-loop`
**날짜**: 2026-07-01
**스펙**: `specs/078-money-gate-alignment-loop/spec.md`
**위험 등급**: 등급 2(운영 체계 변경)

## 요약

스펙 078은 돈 경로 관련 sidecar들이 같은 상태를 말하는지 매일 자동으로 대조한다. 현재 핵심 후보 `candidate-fd04772a23c5`의 요구처럼 `money-path`, 자본 준비도, edge-autoarm, reassign, 전진 페이퍼, pipeline liveness를 하나의 evidence package로 묶고, 기존 게이트를 우회하지 않은 채 불일치와 다음 자동 작업을 발행한다.

## 기술 맥락

- **언어**: Python 3.11
- **패키지**: `auto_invest.analytics`
- **진입점**: `scripts/money_gate_alignment_probe.py`
- **자동 실행**: `.github/workflows/money-gate-alignment.yml`
- **출력 sidecar**: `automation/money-gate-alignment-last-run`
- **생존 감시**: `src/auto_invest/analytics/pipeline_liveness.py`
- **테스트**: pytest, ruff
- **성능 목표**: sidecar 원문 몇 개를 읽는 보고 루프이므로 로컬 실행 5초 이내, workflow 8분 이내

## 헌법·안전 점검

- 원칙 I, II: 포지션 한도와 허용 종목을 바꾸지 않는다.
- 원칙 IV: 감사 로그를 삭제하거나 변경하지 않는다.
- 원칙 V: 비밀값을 읽거나 출력하지 않는다.
- 원칙 VI: `Backtest -> Canary -> Full Live` 단계를 우회하지 않는다.
- 원칙 VIII.A: 이 workflow는 실거래 worker 배포가 아니라 보고 sidecar 발행이다.
- 원칙 X.4, X.5: 자본 사다리와 전략 재지정 게이트를 변경하지 않고, 그 상태를 대조만 한다.

## 구조

```text
src/auto_invest/analytics/money_gate_alignment.py
scripts/money_gate_alignment_probe.py
.github/workflows/money-gate-alignment.yml
tests/unit/test_money_gate_alignment.py
tests/integration/test_money_gate_alignment_probe.py
specs/078-money-gate-alignment-loop/
```

## 설계 결정

### 결정 1: money-path를 1차 기준으로 둔다

- **선택**: `live_money_state.status`, `stage`, `blocking_gate`는 `money-path`를 기준으로 읽고 다른 표면이 이 해석과 맞는지 본다.
- **이유**: 기존 기억과 코드 기준에서 현재 실거래 상태의 단일 기준 표면은 `money-path`다.
- **대안**: 자본 준비도 루프를 기준으로 둔다. 이는 2차 해석 표면이므로 원천과 다를 때 원인을 숨길 수 있어 제외한다.

### 결정 2: 정상 대기와 실패를 분리한다

- **선택**: 전진 관측 부족, `WAIT_EDGE`, reassign `HOLD`, pipeline `OK`가 함께 나타나면 `ALIGNED_WAITING`으로 둔다.
- **이유**: 관측 부족은 정상적인 fail-safe 대기다. 실패처럼 표시하면 운영자가 불필요한 작업을 반복한다.

### 결정 3: 불일치는 작업 후보로 발행한다

- **선택**: stage, live status, blocking gate, liveness, edge-autoarm, reassign 간 모순은 `GateAlignmentIssue`로 구조화한다.
- **이유**: 다음 자동 실행 루프가 이 sidecar를 읽어 복구 작업을 후보화할 수 있어야 한다.

## 되돌림 계획

- workflow 스케줄을 제거하거나 파일을 되돌리면 sidecar 발행이 멈춘다.
- `pipeline_liveness.default_specs()`에서 `money-gate-alignment` 항목을 제거하면 생존 감시 대상에서 빠진다.
- 코어 모듈과 probe는 읽기 전용이므로 되돌림은 기능 제거만 필요하고 돈 경로 복구는 없다.

## Phase 0 연구 산출물

`research.md`에 입력 기준, 정렬 규칙, 안전 경계, liveness 등록 방식을 기록한다.

## Phase 1 설계 산출물

`data-model.md`, `contracts/money-gate-alignment.md`, `quickstart.md`를 유지한다.
