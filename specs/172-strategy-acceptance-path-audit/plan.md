# 구현 계획: 전략 합격 경로 감사와 연구 교착 해소

**브랜치**: `codex/172-next-priority-strategy-audit` | **날짜**: 2026-08-30 | **명세**: [spec.md](./spec.md)

## 요약

전진 교정에 80% 절대 검출력 하한과 `UNDERPOWERED` 상태를 추가한다. 현재 레짐 결과와
교정 결과를 결합해 8관문 전체가 아니라 통계 핵심만 교정됐음을 드러내는 감사 모듈을 만든다.
동결일 뒤 월별 공개자료를 같은 후보·기준으로 추적하는 주문 없는 자동화를 등록하고, 병렬 연구
후보 ID에서 관찰 횟수를 제거한다.

## 기술 맥락

**언어/버전**: Python 3.11, Bash/YAML
**주요 의존성**: NumPy, 기존 백테스트 통계 모듈, GitHub Actions
**저장소**: 커밋된 JSON 계약과 orphan 사이드카 브랜치
**테스트**: pytest 단위·통합 테스트, Ruff, shell/YAML 정적 안전 검사
**대상**: GitHub Actions Linux 러너와 로컬 분석 CLI
**성능 목표**: 고정 시드 2,000회 교정을 통합 테스트 30초 안에 완료
**제약**: 브로커 API·주문·자본·라이브 설정 접근 0건, 결정론, 누락 시 fail-closed
**범위**: 교정 1개, 감사 모듈/CLI 1쌍, 레짐 전진 관찰 필드, 월별 워크플로 1개, 선택기 오류 1개

## 헌법 점검

- 원칙 I~VII, VIII.A, IX, X의 주문 한도·허용 종목·감사·비밀값·장중 배포·단계 승격을 변경하지 않는다.
- `Backtest -> Canary -> Full`을 유지하며 이번 자동화는 Backtest 이후 관찰 증거만 쌓는다.
- 자본 사다리는 `WAIT_EDGE`, 단 0, 자본 0을 유지한다. `EDGE_CONFIRMED`를 만들지 않는다.
- 후보와 기준의 지문, 동결일, 관문 집합이 누락되면 감사와 관찰을 실패시킨다.
- 헌법·커널 파일을 수정하지 않는다. 안전 경계 판정 표시를 더 엄격하게 하므로 위험 등급 3이다.

## 프로젝트 구조

```text
src/auto_invest/analytics/
├── forward_gate_calibration.py
├── regime_adaptive_challenger.py
├── strategy_acceptance_path_audit.py
└── autonomous_work_execution.py
scripts/
├── forward_gate_calibration_probe.py
└── strategy_acceptance_path_audit_probe.py
.github/workflows/regime-challenger-forward-observation.yml
tests/unit/ and tests/integration/
specs/172-strategy-acceptance-path-audit/
```

기존 순수 분석 모듈과 CLI 패턴을 재사용한다. 실거래 포트폴리오·워커·주문 모듈에는 의존하지 않는다.

## 복잡성 추적

| 추가 구조 | 이유 | 더 단순한 대안을 쓰지 않은 이유 |
| --- | --- | --- |
| 월별 별도 사이드카 | 7/8 후보의 동결 후 증거를 운영 트랙과 분리 보존 | 기존 7개 페이퍼 트랙은 이 레짐 로직을 실행하지 못하며 섞으면 후보 지문이 깨진다 |
