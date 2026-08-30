# Implementation Plan: PEAD와 21가족 프로그램 관문

**Branch**: `Codex/175-pead-gate-recalibration` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/175-pead-program-gate/spec.md`

## Summary

현재 20가족에 똑같은 1% 상한을 적용한 연구 관문은 21번째 가족을 성능과 무관하게 막는다.
이를 후보 수별 교정 상한으로 확장하되, 가족 간 독립을 가정하지 않는 보수적 합계 20%를
유지한다. 동시에 공개 복제자료의 두 PEAD 신호를 결과 전에 고정한 16개 후보로 평가해,
역사적으로 출판된 엣지가 남아 있는지와 지금 계좌에서 실행 가능한지를 분리해 보고한다.

새 `3.2` 증거는 연구 진단 전용이다. 기존 헌법이 허용하는 `3.1` 실자본 진입 계약은 바꾸지
않으며, 기존 돈 경로 소비자는 알 수 없는 계약을 계속 실패 폐쇄한다.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: 표준 라이브러리, NumPy, 기존 `auto_invest.analytics` 통계 모듈  
**Storage**: JSON/Markdown sidecar와 공개 월별 CSV 입력  
**Testing**: pytest, Ruff, JSON Schema 및 독립 증거 소비자  
**Target Platform**: GitHub Actions Linux 연구 워커와 로컬 macOS 검증 환경  
**Project Type**: Python 연구 라이브러리 + 명령줄 탐침 + CI 워크플로  
**Performance Goals**: 고정 난수 500회 교정과 816행 감사를 CI 한 번 안에 재현  
**Constraints**: 주문 0건, 자본 0%, 라이브 설정 변경 0건, 결과 확인 후 기준 변경 금지,
기존 `3.1` 계약 호환 유지  
**Scale/Scope**: 기존 800후보·20가족 + PEAD 16후보·1가족 = 816후보·21가족

## Constitution Check

*GATE: Phase 0 연구 전 통과했으며 Phase 1 설계 후 다시 확인했다.*

- **Rung 0 연구 격리**: 공개 복제자료만 읽고 브로커·주문·계좌·비밀값 경로를 호출하지 않는다.
- **20% 프로그램 예산**: `11 × 0.010 + 10 × 0.009 = 0.200`의 가족별 합계로 보수적으로
  유지한다. 가족 간 독립을 가정한 확률은 참고 진단값으로만 쓴다.
- **헌법의 3.1 진입 계약**: 헌법 X.4의 `3.1`·최대 20가족 제한은 그대로 둔다. `3.2`는
  진단 전용이며, 이 기능만으로 자본 10% 단계도 열지 않는다.
- **정확한 동일성**: 후보 ID와 전략 지문, 자료 SHA-256, 분할, 비용, 가족 크기를 장부에
  고정하고 독립 소비자가 다시 계산한다.
- **시간 분리**: 개발은 1996-12까지, 1997년은 차단, 1998-2016은 출판 후, 2017년 이후는
  최근 구간이다. 타당성 조사에서 일부 결과를 본 사실은 명시하고 비공개 홀드아웃이라 하지 않는다.
- **실행 동등성**: 개별 종목의 시점보존 구성, 상장폐지 가격, 공매도·정수주·현재 비용,
  전진 관찰이 없으므로 모든 연구 캐너리·승격·배포 필드는 false 또는 null이다.
- **누락 증거 실패 폐쇄**: 이전 800행, 가족 구성, 데이터 월·종목 수, 교정값 중 하나라도
  어긋나면 결과를 만들지 않는다.

Phase 1 재점검 결과도 동일하다. 헌법·커널·화이트리스트·포지션 한도·라이브 자본 코드는
수정 대상에서 제외했다.

## Project Structure

### Documentation (this feature)

```text
specs/175-pead-program-gate/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── contracts/
    ├── forward-observation.md
    ├── pead-preregistration.json
    └── pead-result.schema.json
```

### Source Code (repository root)

```text
src/auto_invest/analytics/
├── edge_gate_calibration.py          # 기존 3.1 + 진단 전용 프로그램 확장
├── pead_factory.py                   # 자료 검증, 16후보, 시간분리 평가
└── pead_factory_evidence.py          # 독립 816행·21가족 소비자

scripts/
├── edge_gate_calibration_probe.py
├── pead_factory_probe.py
├── pead_evidence_gate.py
└── validate_public_factory_sidecar.py

tests/
├── unit/
│   ├── test_edge_gate_calibration.py
│   ├── test_pead_factory.py
│   └── test_pead_factory_evidence.py
└── integration/
    ├── test_pead_factory_probe.py
    ├── test_pead_evidence_gate.py
    └── test_strategy_factory_workflow.py

.github/workflows/autonomous-strategy-factory.yml
```

**Structure Decision**: 기존 분석 모듈·독립 소비자·명령줄 탐침·sidecar 워크플로 구조를
그대로 확장한다. 별도 서비스나 실거래 진입점을 만들지 않는다.

## Implementation Phases

1. 후보 수 16·64의 고정 난수 교정 결과에 가족별 상한과 21가족 구성을 추가한다.
2. 공개자료 파서가 출시본, 월, 두 신호, 롱·숏 종목 수, SHA-256을 엄격히 검증하게 한다.
3. 고정된 8개 가중치와 두 배율로 16개 후보를 만들고 개발 구간만으로 승자를 고른다.
4. 출판 후·최근·시대·집중도·낙폭·비용 스트레스·부호 반전을 모두 계산한다.
5. 결과를 역사적 엣지, 최근 지속성, 전진 확인, 현재 계좌 적격으로 나눠 발행한다.
6. 이전 800행과 새 16행의 ID·지문·가족 구성·상한을 독립 소비자가 재계산한다.
7. 워크플로에서 회계 팩터 결과 다음에 PEAD를 실행하고 최종 816행 sidecar를 게시한다.
8. 단위·통합·전체 테스트, 린트, 하네스, 인계 사실 검사를 거쳐 PR을 머지한다.

## Complexity Tracking

| 결정 | 필요한 이유 | 단순 대안이 부족한 이유 |
|---|---|---|
| `3.2`를 진단 전용 새 계약으로 둠 | 21가족을 평가하면서 헌법의 `3.1` 돈 경로를 보존 | 기존 버전 의미를 조용히 바꾸면 이전 증거와 자본 진입 판단이 섞임 |
| 가족별 상한 합계를 사용 | 가족 간 상관을 몰라도 프로그램 20% 예산을 지킴 | 독립 가정으로 확률을 곱하면 오합격을 과소평가할 수 있음 |
| 역사 합격과 실계좌 적격을 분리 | 공개 롱숏 포트폴리오는 소액 정수주 계좌와 다름 | 단일 합격/불합격은 전략 부재와 실행 증거 부족을 다시 혼동함 |

