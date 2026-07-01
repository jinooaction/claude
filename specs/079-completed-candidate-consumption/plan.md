# 구현 계획: 완료 후보 소비 및 차순위 자동 승격 루프

**Branch**: `Codex/079-completed-candidate-consumption` | **Date**: 2026-07-02 | **Spec**: `specs/079-completed-candidate-consumption/spec.md`

## Summary

스펙 079는 자율 작업 실행 루프가 이미 출시된 후보를 반복 선택하지 않게 한다. 새 `released-work` 보고 루프가 완료된 spec 산출물에서 명시 후보 식별자를 읽어 완료 장부를 발행하고, `autonomous-work-execution`은 이 장부를 읽어 완료 후보를 `RELEASED`로 억제한 뒤 차순위 후보를 선택한다.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: 표준 라이브러리, 기존 `auto_invest.analytics` 모듈  
**Storage**: GitHub Actions sidecar branch (`automation/released-work-last-run`)  
**Testing**: pytest, ruff  
**Target Platform**: GitHub Actions Ubuntu runner, local macOS 개발 환경  
**Project Type**: Python CLI/analytics 모듈 + GitHub Actions 운영 자동화  
**Performance Goals**: repository scan 로컬 5초 이내, workflow 8분 이내  
**Constraints**: 읽기 전용, 결정론, 비밀값 미접근, 브로커/주문/자본/live 설정 변경 금지  
**Scale/Scope**: 수십 개 spec 디렉터리와 자동 후보 sidecar 몇 개

## Constitution Check

- 원칙 I~VII: 주문·자본·포지션 한도·허용 종목·감사 로그를 변경하지 않는다.
- 원칙 VIII.A: 배포 제한 경로를 변경하지 않는다. 새 workflow는 보고 sidecar만 발행한다.
- 원칙 IX: 기존 `Backtest -> Canary -> Full` 흐름을 우회하지 않는다.
- 원칙 X: 실제 돈 경로는 `money-path`, 자본 사다리, edge-autoarm, reassign 게이트가 계속 권위 표면이다.
- 위험 등급: 등급 2 운영 자동화 변경. 등급 3/4 안전 경계·돈 경로 변경 없음.

## Project Structure

```text
src/auto_invest/analytics/released_work.py
src/auto_invest/analytics/autonomous_work_execution.py
src/auto_invest/analytics/pipeline_liveness.py
scripts/released_work_probe.py
scripts/autonomous_work_execution_probe.py
.github/workflows/released-work-ledger.yml
.github/workflows/autonomous-work-execution.yml
tests/unit/test_released_work.py
tests/unit/test_autonomous_work_execution.py
tests/integration/test_released_work_probe.py
tests/integration/test_autonomous_work_execution_probe.py
specs/079-completed-candidate-consumption/
```

**Structure Decision**: 기존 sidecar 보고 루프 패턴을 따른다. 코어는 `src/auto_invest/analytics`, workflow 진입점은 `scripts`, 자동 실행은 `.github/workflows`, 회귀는 unit/integration 테스트에 둔다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 없음 | 해당 없음 | 해당 없음 |
