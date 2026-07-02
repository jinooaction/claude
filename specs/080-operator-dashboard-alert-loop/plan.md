# 구현 계획: 운영자 대시보드와 모바일 알림 루프

**Branch**: `Codex/operator-dashboard-alert-loop` | **Date**: 2026-07-02 | **Spec**: `specs/080-operator-dashboard-alert-loop/spec.md`

## Summary

스펙 080은 이미 발행되는 자율 루프 sidecar를 한 번 더 사람이 읽기 쉬운 운영자 상태로 합친다. 같은 `OperatorStatusReport`를 모바일 상태판과 모바일 알림 루프가 함께 사용한다. 상태판은 매일 갱신되고, Telegram 알림은 개입이 필요한 상태에서만 best-effort로 전송된다. 주문, 자본, live 설정, 브로커, 서버 SSH는 건드리지 않는다.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: 표준 라이브러리, 기존 `auto_invest.analytics`, 기존 Telegram helper  
**Storage**: GitHub Actions sidecar branch (`automation/operator-status-last-run`)와 GitHub Pages `gh-pages`  
**Testing**: pytest, ruff  
**Target Platform**: GitHub Actions Ubuntu runner, local macOS 개발 환경  
**Project Type**: Python CLI/analytics 모듈 + 정적 HTML 생성 + GitHub Actions 운영 자동화  
**Performance Goals**: sidecar 요약 로컬 5초 이내, workflow 8분 이내, Telegram send bounded timeout/retry  
**Constraints**: 읽기 전용, 결정론, 비밀값 원문 미저장, broker/order/capital/live/SSH 경로 금지  
**Scale/Scope**: 자율 루프 sidecar 6~20개, 운영자 1명, text-only 모바일 알림

## Constitution Check

- 원칙 I(포지션 한도)와 II(허용 종목): 주문 계획이나 종목 universe를 만들지 않는다.
- 원칙 III(LLM 판단 지점): LLM 호출이 없다.
- 원칙 IV(감사 로그): 감사 로그 schema나 기록 방식을 바꾸지 않는다. 이 기능은 GitHub sidecar만 발행한다.
- 원칙 V(비밀값 분리): Telegram token/chat id는 GitHub Secrets에서 런타임에만 읽고, HTML/sidecar/log에 원문을 남기지 않는다.
- 원칙 VI(Backtest -> Canary -> Full): 전략 승격이나 live 단계 변경을 하지 않는다.
- 원칙 VII(외부 API 장애 대응): Telegram 전송은 기존 bounded helper를 재사용하고 실패해도 운영 sidecar 발행과 돈 경로를 막지 않는다.
- 원칙 VIII.A(장중 배포 금지): trading logic 변경이 아니며 deploy 제한 경로를 완화하지 않는다.
- 원칙 IX(자기 수정 경계): kernel 파일, 헌법, 커널 manifest, 주문 제한, 비밀값 저장 경로를 바꾸지 않는다.
- 원칙 X(측정 기반 자율 성장): 기존 측정 sidecar를 운영자 관측 표면으로 승격하지만, 새 투자 판단이나 자본 결정을 하지 않는다.
- 위험 등급: 등급 2 운영 자동화 변경. 등급 3/4 안전 경계·돈 경로 변경 없음.

## Project Structure

```text
src/auto_invest/analytics/operator_status.py
src/auto_invest/analytics/pipeline_liveness.py
scripts/operator_status_probe.py
scripts/generate_mobile_status.py
.github/workflows/operator-mobile-alerts.yml
.github/workflows/mobile-status-pages.yml
tests/unit/test_operator_status.py
tests/unit/test_operator_mobile_alerts_workflow.py
tests/unit/test_pipeline_liveness.py
tests/integration/test_operator_status_probe.py
tests/integration/test_mobile_status_page.py
specs/080-operator-dashboard-alert-loop/
```

**Structure Decision**: 새 판단 코어는 `src/auto_invest/analytics/operator_status.py`에 둔다. workflow와 상태판은 이 코어가 만든 같은 JSON 계약을 소비한다. 기존 Telegram audit tailer는 주문 이벤트 관찰자이므로 변경하지 않는다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 없음 | 해당 없음 | 해당 없음 |

## Phase 0: Research

연구 결과는 `research.md`에 정리했다. 핵심 결정은 기존 모바일 상태판을 대체하지 않고 확장하며, 알림 전송은 상태 보고 sidecar 발행 이후 best-effort로 수행하는 것이다.

## Phase 1: Design & Contracts

- `data-model.md`: 운영자 상태 보고, 입력 표면, 알림 판정 엔티티.
- `contracts/operator-status.md`: probe manifest, JSON, Markdown, workflow 안전 계약.
- `quickstart.md`: 로컬 재현, workflow sidecar 확인, 모바일 상태판 확인.
