# Implementation Plan: Autonomous Production Approval

**Branch**: `Codex/144-autonomous-production-approval` | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

## Summary

GitHub `production` 환경의 사람 검토자만 제거하고 환경 전용 개인키와 main-only 정책은 유지한다.
워크플로에는 환경 비밀값에 접근하지 않는 기계 승인 작업을 먼저 두어 이벤트·ref·무장·자본을
검증하고, 그 성공 결과를 production 서명 작업의 필수 입력으로 만든다.

## Technical Context

**Language/Version**: Python 3.11+, Bash, GitHub Actions YAML  
**Primary Dependencies**: 기존 money-path, GitHub production environment, OpenSSL Ed25519  
**Storage**: GitHub 환경 설정, 기존 추가-전용 감사 장부와 sidecar branch  
**Testing**: pytest, ruff, bash syntax, YAML parser, GitHub API와 주문 없는 실서버 사전점검  
**Target Platform**: GitHub Actions Ubuntu runner와 Vultr production host  
**Project Type**: 자동투자 워크플로·운영 상태  
**Performance Goals**: 예약 run이 사람 대기 없이 production 작업으로 즉시 진행  
**Constraints**: 실제 주문은 schedule만, 수동은 주문 0건, 환경 개인키 비노출  
**Scale/Scope**: 표준 자본 사다리 live-canary 한 경로와 production 환경 한 개

## Constitution Check

- **I/K1, II/K2**: 포지션 한도와 `SPYM/IEF/GLDM` 허용 목록을 변경하지 않는다.
- **IV/K4**: 기존 주문·체결 추가-전용 감사 로그를 유지한다.
- **V/K5**: 개인키는 production 환경 secret에만 남고 코드·로그·sidecar에 쓰지 않는다.
- **VI/X.4**: 기존 20% exploration rung, 293달러 자본, 상향 증거 조건과 20% 손실 예산을 유지한다.
- **VII**: KIS 장애·재시도·서킷 브레이커는 기존 live CLI가 계속 집행한다.
- **VIII.A/K6**: 주문은 미국 정규장 preflight를 계속 통과해야 한다.
- 정확한 배포 SHA, 서명, nonce, 센티넬, rung, NAV 중 하나라도 없거나 다르면 실패 폐쇄한다.
- 사람 승인만 제거하며 손실 표면을 넓히는 자본·전략·허용 종목 변경은 없다.
- 헌법과 kernel manifest는 수정하지 않는다. 커밋에 `this changes the safety perimeter`를 기록한다.

## Project Structure

```text
.github/workflows/rebalance-live-canary.yml
src/auto_invest/analytics/money_path.py
tests/unit/test_live_canary_workflow.py
tests/unit/test_money_path.py
specs/144-autonomous-production-approval/
```

**Structure Decision**: 새 서비스나 키를 만들지 않고 기존 서명 관문 앞에 기계 승인 작업만 추가한다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| production required reviewer 제거 | 정규장 예약 run의 마지막 사람 의존점을 없애야 함 | 개인키를 repository secret으로 옮기면 더 많은 workflow에 노출됨 |

## Post-Design Constitution Re-check

사람 검토는 이벤트·ref·무장·자본을 검증하는 기계 작업으로 대체되고, production 환경 개인키와
서버 이중 검증은 그대로다. 기존 자본과 최대 손실 경계는 변하지 않는다.

