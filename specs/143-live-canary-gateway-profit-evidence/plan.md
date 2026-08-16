# Implementation Plan: Live Canary Gateway And Profit Evidence

**Branch**: `Codex/143-live-canary-gateway-profit-evidence` | **Date**: 2026-08-16 | **Spec**: [spec.md](spec.md)

## Summary

제한 SSH 관문 때문에 실패할 표준 live-canary 직접 명령을 production 전용 Ed25519 서명 요청과
root 소유 고정 helper로 교체한다. 주문 권한과 분리된 체결·성과 관측 루프가 기존 스펙 011 성과
엔진을 실행하고 최초 양의 실제 손익을 누적 sidecar로 보존한 뒤 상위 돈 경로를 자동 재평가한다.

## Technical Context

**Language/Version**: Python 3.11+, Bash, GitHub Actions YAML
**Primary Dependencies**: 기존 Typer CLI, Pydantic, OpenSSL Ed25519, GitHub production environment
**Storage**: 기존 SQLite append-only audit log, root 소유 nonce 파일, force-push sidecar branch
**Testing**: pytest, ruff, `bash -n`, YAML parser, 실제 sidecar 재생
**Target Platform**: GitHub Actions Ubuntu runner와 Vultr Linux production host
**Project Type**: 자동투자 CLI·워크플로·서버 명령 관문
**Performance Goals**: 주문 인증 10분 이내 만료, live-canary 완료 후 10분 이내 첫 증거 발행
**Constraints**: 주문 서명키 저장소 미노출, 일반 SSH 키 단독 주문 금지, 주문은 정규장·293달러·기존 게이트만
**Scale/Scope**: 표준 자본 사다리 live-canary 1개 경로와 단일 실계좌

## Constitution Check

- **I/K1**: 주문은 기존 rebalance CLI의 per-trade/per-symbol/global caps를 그대로 통과한다.
- **II/K2**: `SPYM/IEF/GLDM` 허용 목록과 limit 주문 정책을 변경하지 않는다.
- **IV/K4**: 기존 주문·체결 audit와 `LIVE_PERFORMANCE_SNAPSHOT` 추가 기록만 사용하며 과거 행을 수정하지 않는다.
- **V/K5**: 개인 서명키는 production 환경 secret에만 저장하고 로그·sidecar·저장소에 쓰지 않는다.
- **VI**: 검증된 globalfixed 신호, 20% exploration-canary rung, 293달러 한도, 25% 전 EDGE_CONFIRMED를 유지한다.
- **VII**: KIS 재시도·토큰·서킷 브레이커를 기존 CLI에서 재사용한다.
- **VIII.A/K6**: 코드 배포는 정규장 밖에서만 하고 주문 자체는 기존 정규장 preflight를 통과한다.
- **X.4**: 정확한 배포 지문, 분리 holdout, 50bp 비용, forward 42관측, PSR 0.80 exploration 기준을 바꾸지 않는다.
- 누락·모순된 서명, 센티넬, 자본, 배포, 체결, 시세 증거는 모두 실패 폐쇄한다.
- 헌법·kernel manifest는 수정하지 않는다. 안전 경계 변경 커밋에는 `this changes the safety perimeter`를 남긴다.

## Project Structure

```text
deploy/
├── live-canary-on-instance.sh
├── live-order-signing-public.pem
└── repair-ssh-boundary.sh
.github/workflows/
├── rebalance-live-canary.yml
├── live-profit-evidence.yml
├── money-path.yml
└── capital-path-readiness.yml
src/auto_invest/analytics/
├── live_profit_evidence.py
└── money_path.py
scripts/
├── live_profit_evidence_probe.py
└── money_path_probe.py
tests/unit/
tests/integration/
specs/143-live-canary-gateway-profit-evidence/
```

**Structure Decision**: 기존 배포 helper·analytics core·probe·sidecar workflow 패턴을 그대로 확장한다.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| production 전용 비대칭 서명 | 저장소 SSH 키와 주문 권한을 분리해야 함 | gateway에 주문 명령만 추가하면 일반 workflow가 production 승인을 우회할 수 있음 |
| 별도 live-profit sidecar | 최초 수익을 누적·자동 재평가해야 함 | production run 원문 로그만으로는 최초 양의 손익을 기계 판독·보존할 수 없음 |

## Post-Design Constitution Re-check

모든 주문은 기존 전략·자본·위험·시간 게이트 안에 남고, 새 관문은 production 승인 증거를 추가한다.
관측 경로는 주문 권한이 없으며 기존 append-only 장부와 성과 정의를 재사용한다. 통과.
