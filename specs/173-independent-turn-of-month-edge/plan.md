# 구현 계획: 독립 월말·월초 전략과 교정 의미 정렬

**브랜치**: `codex/173-parallel-independent-edge` | **날짜**: 2026-08-30 | **명세**: [spec.md](./spec.md)

## 요약

표준 전진 교정의 오합격 안전성과 검출력을 분리해 연구 결과는 보존하되 교정 완료 전 자본을 차단하고,
빈 앵커드 입력이 표준 유의성 방식을 지우는 통합 오류를 고친다. 이어 Kenneth French 공식 일별
시장·무위험 수익을 이용해 결과 사전 미확인 상태로 고정한 16개 월말·월초 후보를 개발/차단/
홀드아웃으로 검증한다. 누락된 레짐 가족을 중앙 장부에 복원하고 새 가족까지 19개·784행으로
맞추되, 새 결과는 라이브 동등성이 없으므로 자본·주문·라이브 설정을 바꾸지 않는다.

## 기술 맥락

**언어/버전**: Python 3.11, Bash/YAML, JSON Schema 2020-12
**주요 의존성**: NumPy, 기존 PSR/DSR/PBO 모듈, 기존 Fama-French ZIP 파서, GitHub Actions
**저장소**: 커밋된 사전등록 JSON과 orphan sidecar 브랜치의 JSON/Markdown 증거
**테스트**: pytest 단위·통합 테스트, Ruff, JSON/YAML 정적 검사, 생산 프로브 재생
**대상**: GitHub Actions Linux 러너와 로컬 분석 CLI
**성능 목표**: 16개 후보 1926년~현재 재생 60초 이내, 전체 워크플로 기존 25분 제한 이내
**제약**: 결과 전 계약 동결, 결정론, 미래값 누출 0, 브로커·주문·자본·라이브 설정 접근 0
**범위**: 교정/결합 판정 보정, 분석 모듈·프로브 1쌍, 중앙 공장 연결, 19가족·784행 감사

## 헌법 점검

- 원칙 I~VII, VIII.A, IX, X의 주문 한도·허용 종목·감사·비밀값·장중 배포 제한을 바꾸지 않는다.
- X.4의 10% 연구 진입과 20% 이상 승격 경로를 우회하지 않는다. 새 전략은 라이브 동등성이 없어
  `promotion_allowed=false`이며 자본 사다리 후보가 될 수 없다.
- 표준 전진 진입에는 같은 커밋·같은 `paired_active_return_psr_v1`의 완전 교정을 요구한다.
  `UNDERPOWERED`는 연구 결과를 남기지만 자본은 `WAIT_EDGE`다.
- 앵커드와 탐색은 전체 경로 별도 교정 전 진단 전용이고 표준 교정을 자기 증거로 가장하지 않는다.
- 공장 진입은 기존 가족 단위 전체 경로 교정을 계속 사용한다.
- 상향 승격·상향 재산정은 현재 경로 자격을 요구하고, 강등·정지·위험 축소는 언제나 허용한다.
- 기존 배치 자본은 0이다. 센티넬·자본 비율·손실 예산·승격 단계는 수정하지 않는다.
- 헌법·커널 목록은 변경하지 않는다. 위험 등급은 4이며 노출을 여는 변경이 아니라 잘못된
  차단과 안전 교정 소비를 정렬하는 변경이다.

## 프로젝트 구조

```text
src/auto_invest/analytics/
├── forward_gate_calibration.py
├── research_family_audit.py
└── turn_of_month_equity_factory.py
src/auto_invest/portfolio/
├── backtest_anchored.py
└── capital_ladder.py
src/auto_invest/cli.py
scripts/turn_of_month_equity_factory_probe.py
.github/workflows/autonomous-strategy-factory.yml
tests/unit/
├── test_forward_gate_calibration.py
├── test_backtest_anchored.py
├── test_capital_ladder.py
├── test_research_family_audit.py
└── test_turn_of_month_equity_factory.py
tests/integration/
├── test_ladder_decide_cli.py
├── test_forward_edge_autoarm_workflow.py
├── test_strategy_factory_workflow.py
└── test_turn_of_month_equity_factory_probe.py
specs/173-independent-turn-of-month-edge/
```

기존 순수 분석·통계·CLI 패턴을 재사용한다. 새 전략 모듈은 주문 모듈을 import하지 않으며,
생산 프로브는 파일 입력 또는 공식 URL 읽기만 지원한다.

## 구현 단계

1. 교정 결과에 오합격/검출력 별도 필드를 추가하고 기존 숫자와 결정성을 보존한다.
2. 결합 판정에 표준·앵커드 원본 방법과 증거를 보존한다.
3. `ladder-decide`가 같은 커밋의 표준 교정을 읽어 표준 직접 진입과 이후 상향 노출을 fail-closed 한다.
4. 앵커드·탐색을 별도 교정 전 진단 전용으로 두고 돈 경로의 10%/20% 설명을 실제 코드와 맞춘다.
5. 출시 레짐 16개 후보를 중앙 감사 장부의 18번째 가족로 복원한다.
6. 16개 달력 후보와 공식 일별 자료 검증·월별 비용 후 수익 변환을 구현한다.
7. 개발 전용 선택, 홀드아웃 통계·경제성·집중도·위약 관문을 구현한다.
8. 기존 752행 뒤에 레짐 16행과 달력 16행을 붙이고 중앙 가족 감사를 19개로 재구성한다.
9. 별도 결과와 중앙 결과를 sidecar에 발행하되 선택 배포 설정은 항상 `null`로 둔다.
10. 생산 공개 자료로 한 번 재생해 실제 판정과 실패 관문을 고정 증거로 남긴다.

## 복잡성 추적

| 추가 구조 | 이유 | 더 단순한 대안을 쓰지 않은 이유 |
| --- | --- | --- |
| 독립 달력 공장 모듈 | 일별 월 경계·비용·집중도 검사가 기존 월별 공장과 다름 | 기존 옵션/원자재 모듈에 섞으면 데이터 시계와 후보 지문이 결합된다 |
| 표준 교정 CLI 입력 | 오합격 안전 실패와 검출력 경고를 실제 소비 경로에서 구분 | 보고서 문구만 고치면 안전 실패를 돈 경로가 계속 무시한다 |
| 중앙 장부 연결 | 누락 레짐과 신규 달력을 실제 행·가족로 재현 | 별도 보고서만 두면 17/18/19 가족 숫자가 다시 어긋난다 |

## 설계 후 헌법 재점검

모든 쓰기는 연구 JSON·문서·코드·테스트뿐이다. 실거래 센티넬, live 포트폴리오, whitelist,
caps, 손실예산, 브로커 API, 비밀값을 건드리지 않는다. 새 가족은 역사 관문을 통과해도 라이브
동등성 실패 때문에 자본 소비자가 거부한다. 따라서 기존 최대 손실 표면은 넓어지지 않는다.
