# Implementation Plan: 오너 단회 장중 긴급 배포

**Branch**: `codex/179-operator-emergency-live-deploy` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/179-owner-emergency-live-deploy/spec.md`

## Summary

정규장 일반 배포 금지는 유지하되, GitHub namespace 소유자 또는 헌법에 정확히 등록된 시스템 오너가 현재 `main`의 특정 커밋 하나를 15분 이내 한 번만 승인했을 때만 장중 긴급 배포를 허용한다. 기존 강제 SSH 경계에 목적 제한 명령을 추가하고, 루트 helper가 승인 감사를 먼저 남긴 뒤 두 자동 주문 경로와 이전 작업자를 중지하고 최종 중개사 쓰기를 잠근다. 이 정지 상태에서 KIS 읽기 전용 검사로 미체결 주문 0건을 확인한다. 배포 실행기는 고정 요청 파일의 소유권·권한·시간·대상·단회성과 앞선 승인을 재검증한다. 기존 90초 건강 검사와 롤백 결과가 확인될 때만 잠금을 해제하고 자동 예약을 복구한다. 확인된 롤백 뒤 별도의 정상 배포가 이미 정확한 최신 `main`을 건강하게 실행 중이면 오래된 잠금만 추가 전용 감사와 함께 회수한다. 생산이 rollback 기준과 새 승인 대상 사이의 건강한 커밋에 있으면 같은 증거를 현재 생산 HEAD에 묶어 확인하고, 비종료 인계 사건을 남겨 같은 잠금 아래 새 단회 요청과 기존 exact-target 배포 상태기계로 이어간다.

## Technical Context

**Language/Version**: Python 3.11+, Bash, GitHub Actions YAML  
**Primary Dependencies**: pydantic 2.13+, exchange-calendars 4.13+, Typer, systemd, OpenSSH forced-command gateway, KIS REST client  
**Storage**: 기존 SQLite `audit_log`, 루트 소유 `/run/auto-invest-deploy/emergency-request.json`, `/run/auto-invest-deploy/live-order-maintenance.lock`  
**Testing**: pytest 9+, shell syntax 검사, ruff, strict agent harness, HANDOFF 사실 검사, PR 품질 관문  
**Target Platform**: Ubuntu 생산 서버, systemd, GitHub Actions  
**Project Type**: Python CLI + 서버 운영 스크립트 + 배포 워크플로  
**Performance Goals**: 승인 후 5분 이내 배포 시작, 요청 검증과 주문 잠금은 첫 생산 변경 전에 완료  
**Constraints**: 요청 유효시간 최대 15분, 건강 검사 최소 90초, 미체결 주문 0건, 한 번만 사용, 일반 장중 배포·수동 주문·자본/전략 변경 금지  
**Scale/Scope**: 단일 생산 계정, 단일 배포 서비스, GitHub·서버 두 자동 주문 출처, 10% 운용 캐너리

## Constitution Check

*GATE: Phase 0 전 통과, Phase 1 설계 뒤 재확인 완료.*

- **I 포지션 한도**: 통과. 배포 예외는 주문 권한이 아니며 포지션·자본·노출 한도를 바꾸지 않는다.
- **II 허용목록**: 통과. 허용 종목이나 주문 종류를 변경하지 않는다.
- **III 제한된 LLM 판단**: 통과. 생산 배포와 주문 경로에 새 LLM 호출을 넣지 않는다.
- **IV 추가 전용 감사**: 통과. `DEPLOY_EMERGENCY_AUTHORIZED`, cleanup-only 복구의 `DEPLOY_EMERGENCY_RECOVERY_COMPLETED`, 건강한 중간 배포 인계의 비종료 `DEPLOY_EMERGENCY_ORPHAN_RECOVERED`를 기존 장부에 추가하고 관련 이전 rollback·후속 정상 배포 상관관계 식별자를 연결한다.
- **V 비밀값 분리**: 통과. 요청에는 이유 원문이 아닌 SHA-256 다이제스트만 전달하며 KIS 비밀값을 출력하지 않는다.
- **VI 단계 배포**: 통과. 강화 캐너리와 10% 단 1을 유지하고 배포 성공이 자본 승격이나 주문 승인이 되지 않는다.
- **VII 외부 API 장애**: 통과. KIS 읽기 전용 검사 실패는 배포 전 실패 폐쇄하며 재시도로 주문하지 않는다.
- **VIII.A 장중 배포 규율**: 통과. 헌법 15.4.0의 정확한 단회 등록 오너 예외, 최초 도입 bootstrap, 시작 전 HALTED 인계, terminal rollback orphan의 cleanup-only 회수와 건강한 중간 배포에서 새 exact-target 요청으로의 엄격한 인계, 현재 배포 시도에 묶인 결과 판정을 구현하며 일반 경로는 계속 차단한다.
- **VIII.B 배포 자동화**: 통과. 승인·시작·성공/실패·롤백 감사, 90초 건강 검사, 복구 실패 시 주문 정지를 보존한다.
- **IX 안전 경계**: 통과. 최신 K6/K-meta 변경은 전용 헌법 커밋 `c4fac235`에 `this changes the safety perimeter`를 기록했다. 구현 커밋도 K6/K4 변경 표식을 남긴다.
- **X 측정 기반 성장**: 통과. 전략·알파·자본 사다리는 바꾸지 않는다.
- **운용 진입 계약**: 10% 단 1, 정확한 전략 지문, 기존 첫 진입·정수주·KIS·정합 증거를 그대로 소비한다. 누락 시 주문은 실패 폐쇄한다.

**Post-design re-check**: 통과. 외부로 노출되는 새 기능은 namespace 소유자 또는 workflow 소스에 고정된 정확한 등록 시스템 오너만 사용할 수 있는 `workflow_dispatch` 입력과 고정 SSH 명령 하나뿐이다. 서버 요청 파일은 루트 소유 0600, 짧은 수명, 정확한 SHA, 단회 감사 조회로 제한된다. 유지보수 잠금은 세 주문 경계가 독립 확인한다.

## Project Structure

### Documentation (this feature)

```text
specs/179-owner-emergency-live-deploy/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── emergency-deploy-request.schema.json
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/auto_invest/
├── deploy/
│   ├── emergency.py
│   └── runner.py
├── execution/order_router.py
└── persistence/audit.py

deploy/
├── emergency-deploy-on-instance.sh
├── live-canary-on-instance.sh
├── live-canary-scheduled-on-instance.sh
├── repair-ssh-boundary.sh
├── AUTO-DEPLOY.md
└── README.md

.github/workflows/deploy-on-merge.yml

tests/
├── integration/test_deploy_end_to_end.py
└── unit/
    ├── test_emergency_deploy.py
    ├── test_emergency_deploy_shell.py
    ├── test_live_canary_gateway.py
    ├── test_live_canary_workflow.py
    ├── test_live_canary_server_scheduler.py
    └── ../integration/test_order_router.py
```

**Structure Decision**: 기존 단일 Python 패키지, 배포 스크립트, GitHub Actions 구조를 확장한다. 새로운 일반 API나 수동 주문 진입점은 만들지 않는다.

## Complexity Tracking

헌법 15.4.0이 목적 제한 예외, 등록 오너 신원, 정확한 target checkout bootstrap, 시작 전 HALTED 인계, terminal rollback orphan의 회수와 건강한 중간 배포에서 새 대상으로의 인계, 현재 배포 시도에 묶인 결과 판정을 명시하므로 정당화가 필요한 위반은 없다. 일반 장중 차단보다 복잡하지만, 주문 잠금·미체결 0건·단회 요청·90초 건강·롤백·후속 배포 감사를 서로 다른 경계에서 검증해야 단일 실패가 실거래와 겹치지 않는다.
