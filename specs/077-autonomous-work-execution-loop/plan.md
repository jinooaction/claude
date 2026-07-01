# 구현 계획: 자율 작업 실행 루프

**브랜치**: `Codex/077-autonomous-work-execution-loop`  
**스펙**: `specs/077-autonomous-work-execution-loop/spec.md`  
**위험 등급**: 등급 2(운영 체계 변경)

## 요약

기존 자율 성장 루프들은 후보를 발굴하고 검증 패키지를 만들고 결과를 남긴다. 스펙 077은 그 결과를 매일 다시 읽어 "지금 Codex가 착수해야 할 다음 작업"을 하나의 작업 패킷으로 발행한다. 이 패킷은 다음 세션과 운영자가 바로 이해할 수 있는 안전한 인계 표면이다.

## 기술 맥락

- **언어**: Python 3.11
- **패키지**: `auto_invest.analytics`
- **진입점**: `scripts/autonomous_work_execution_probe.py`
- **자동 실행**: `.github/workflows/autonomous-work-execution.yml`
- **출력 sidecar**: `automation/autonomous-work-execution-last-run`
- **생존 감시**: `src/auto_invest/analytics/pipeline_liveness.py`

## 헌법·안전 점검

- 주문·자본·라이브 전략·허용 종목·포지션 한도 변경 없음.
- 브로커 API 호출 없음.
- 비밀값 읽기 없음.
- 외부 유료 서비스 호출 없음.
- 헌법·커널 파일 변경 없음.
- `Backtest -> Canary -> Full` 단계는 유지된다. 이 루프는 해당 단계를 우회하지 않고 다음 작업 후보만 만든다.

## 구조

```text
src/auto_invest/analytics/autonomous_work_execution.py
scripts/autonomous_work_execution_probe.py
.github/workflows/autonomous-work-execution.yml
tests/unit/test_autonomous_work_execution.py
tests/integration/test_autonomous_work_execution_probe.py
specs/077-autonomous-work-execution-loop/
```

## 설계 결정

### 결정 1: 자동 구현자가 아니라 작업 패킷 발행자부터 만든다

- **선택**: sidecar를 읽고 다음 작업 패킷만 발행한다.
- **이유**: 코드 수정·브랜치·PR·머지는 저장소 운영 체계와 안전 경계에 직접 닿는다. 먼저 결정론적 선택기와 인계 표면을 안정화해야 한다.
- **대안**: workflow에서 Codex를 직접 실행해 PR까지 만든다. 현재는 권한, 검증, 비용, 실패 복구 경계가 불충분해 제외한다.

### 결정 2: 안전 후보가 없으면 승인 필요 후보를 드러낸다

- **선택**: 등급 2 이하 후보만 `EXECUTION_READY`가 될 수 있다. 등급 3 이상이나 hard safety surface는 `OPERATOR_APPROVAL_REQUIRED`로 둔다.
- **이유**: 자동화가 돈 경로나 안전 경계를 우회하지 않게 한다.

### 결정 3: pipeline liveness 문제를 최우선으로 본다

- **선택**: 생존 감시가 `CRITICAL`이면 후보 발굴보다 파이프라인 복구 작업을 먼저 발행한다.
- **이유**: 죽은 루프 위에서 성장 후보를 고르는 것은 의미가 없다. 자동화 자체의 생존이 선행 조건이다.

## 되돌림 계획

- workflow 파일을 제거하거나 스케줄을 비활성화하면 sidecar 발행이 멈춘다.
- liveness 레지스트리에서 `autonomous-work-execution` 항목을 제거하면 생존 감시 대상에서 빠진다.
- 코어 모듈과 probe는 읽기 전용이므로 되돌림은 기능 제거만 필요하고 데이터/돈 경로 복구는 없다.
