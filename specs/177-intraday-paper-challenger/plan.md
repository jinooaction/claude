# 구현 계획: 비용 현실형 장중매매 페이퍼 챌린저

**브랜치**: `codex/177-intraday-paper-challenger` | **작성일**: 2026-09-02 | **명세**: [spec.md](spec.md)
**입력**: `/specs/177-intraday-paper-challenger/spec.md`

## 요약

현재 일봉 라이브 전략은 그대로 유지한다. 별도 장중 연구 엔진이 5분 기준봉을 엄격히 검증하고
15분·30분·60분으로 재구성한 뒤, 3개 경제 가족의 고정 18후보를 미래정보 없이 순차 재생한다.
KIS 미국주식 비용을 반영한 기준·스트레스 체결 모형, 개발·차단·최종 확인 분리, PSR·DSR·PBO,
종목·거래 집중도와 독립 증거 소비자를 한 폐회로로 만든다.

현재 저장소와 production에는 요구 기간의 장중 자료가 없다. 따라서 엔진 완료와 시장 엣지
확인을 분리한다. 입력이 756세션·200거래를 못 채우면 정상적으로
`INSUFFICIENT_EVIDENCE`를 발행하며, 합성 fixture는 절대 합격 증거가 되지 않는다.

## 기술 배경

**언어/버전**: Python 3.11 이상
**주요 의존성**: 기존 NumPy, pandas, Pydantic, `exchange_calendars`, 공용 백테스트 지표·과최적화 모듈
**저장소**: 공급자 manifest + 종목별 5분 OHLCV CSV 입력, JSON·JSONL·Markdown 증거 출력
**시험**: pytest 단위·통합 시험, Ruff, JSON 계약과 독립 증거 소비자
**대상 환경**: 로컬 macOS와 GitHub Actions Linux 연구 환경
**프로젝트 형식**: Python 연구 라이브러리 + 명령줄 탐침
**성능 목표**: 5종목·756세션 이상·18후보의 전체 재생과 검증을 10분 안에 완료
**제약**: 네트워크·브로커·실주문·라이브 DB·비밀값 접근 0건, 메모리 1.5GB 이하,
동일 입력 바이트 재현, 미래정보 누출 금지
**규모/범위**: SPY·QQQ·IWM·TLT·GLD, 5분 기준봉, 15/30/60분 평가, 18후보

## 헌법 확인

*GATE: Phase 0 전에 통과했으며 Phase 1 설계 뒤 다시 확인했다.*

- **I 포지션 한도**: 모의 초기자본 100,000달러, 종목당 20%, 전체 80%, 거래량 참여 한도를
  사전등록한다. 이것은 연구 비교용이며 라이브 한도 코드를 호출하거나 바꾸지 않는다.
- **II 기본 거부**: 정확히 SPY·QQQ·IWM·TLT·GLD와 정규장 롱·현금만 허용한다. 다른 심볼,
  공매도, 마진, 레버리지, 시간외 자료는 실패 폐쇄한다.
- **III LLM 판단점**: 후보 생성·신호·체결·판정은 모두 순수 결정 코드다. 실행 중 LLM 호출은 0건이다.
- **IV 감사**: 모든 모의 거래와 미체결을 JSONL 추가 기록으로 발행하고 결과가 그 SHA-256을
  참조한다. 실제 주문 감사 장부는 읽거나 쓰지 않는다.
- **V 비밀값**: 공급자 자격증명 수집은 범위 밖이다. 입력은 비밀 없는 CSV와 manifest뿐이다.
- **VI 단계 출시**: 결과는 백테스트 단계다. 합격해도 자본 0의 `PAPER_CHALLENGER`이며 최소
  60세션 전진 페이퍼 계약만 제안한다.
- **VII 외부 API**: 실행기가 외부 API를 호출하지 않는다. 향후 수집기는 별도 명세와 공급자
  한도·재시도 계약이 필요하다.
- **VIII.A 장중 배포 금지**: 연구 코드는 실거래 로직·설정을 수정하지 않지만, 자동 배포는 기존
  장중 차단을 그대로 따른다.
- **IX 안전 경계**: 헌법·커널·K1~K6 파일은 수정하지 않는다. 새 파일은 돈 경로 소비자에
  등록하지 않는다.
- **X 측정 기반 성장**: 공용 성과 정의와 기존 PSR·DSR·PBO 구현을 재사용한다. 22번째 연구
  가족으로 자본 진입 장부에 추가하지 않으며 새 프로그램 교정 전에는 진단 전용이다.
- **누락 증거**: 5종목, 756세션, 200 비용 후 거래, manifest·원본 지문·18후보 중 하나라도
  부족하면 `INSUFFICIENT_EVIDENCE`로 실패 폐쇄한다.

Phase 1 재점검 결과 위 경계를 바꾸는 설계는 없다. 헌법 위반과 예외 승인 항목은 0건이다.

## 프로젝트 구조

### 이 기능의 문서

```text
specs/177-intraday-paper-challenger/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── checklists/requirements.md
└── contracts/
    ├── intraday-bars.md
    ├── intraday-preregistration.json
    └── intraday-result.schema.json
```

### 소스 코드

```text
src/auto_invest/analytics/
├── intraday_paper_challenger.py
└── intraday_paper_challenger_evidence.py

scripts/
├── intraday_paper_challenger_probe.py
└── intraday_paper_evidence_gate.py

tests/
├── unit/
│   ├── test_intraday_paper_challenger.py
│   └── test_intraday_paper_challenger_evidence.py
└── integration/
    └── test_intraday_paper_challenger_probe.py
```

**구조 결정**: 기존 `analytics` 순수 연구 모듈 + 얇은 `scripts` 탐침 + 독립 소비자 구조를
재사용한다. `cli.py`, 라이브 워크플로, 배포 설정과 데이터베이스 마이그레이션은 건드리지 않는다.

## 구현 단계

1. 정확한 18후보·5종목·비용·분할·안전 필드를 JSON 사전등록으로 고정한다.
2. 5분 CSV와 공급자 manifest를 파싱해 시각, XNYS 세션, 완전성, 지문을 검증한다.
3. 정규장 개장 기준으로 15·30·60분 봉을 재구성하고 부분 마지막 봉의 신규 진입을 금지한다.
4. 세 전략 가족을 닫힌 봉에서 판정하고 다음 봉에만 정수주 모의 체결한다.
5. KIS 기준·스트레스 비용, 거래량 참여, 부분·완전 미체결을 같은 장부에 계산한다.
6. 개발에서만 승자를 고르고 차단·최종 확인, PSR·DSR·PBO·집중도를 판정한다.
7. 전체 후보와 안전 필드를 발행하고 독립 소비자가 후보·승자·관문·장부 지문을 재계산한다.
8. 실제 장중 자료가 없거나 짧은 현재 상태를 `INSUFFICIENT_EVIDENCE`로 재현한다.
9. 단위·통합·전체 시험, 린트, 엄격 하네스, HANDOFF와 PR 품질 관문을 통과한다.

## 복잡성 추적

헌법 위반이 없어 별도 예외는 없다.
