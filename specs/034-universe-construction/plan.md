# 스펙 034 — 구현 계획

## 헌법 점검 (I–X)

- **I 포지션 캡 / II 화이트리스트 / IV 감사 / V 시크릿**: 무변경. 유니버스 구성은 선택
  전용이며 구성 결과는 실주문 전 화이트리스트와 교집합된다 — 라이브 거래 집합을 넓힐 수 없다.
- **III LLM 판단 지점**: LLM 미사용(결정론 Decimal).
- **VI 백테스트→캐너리→풀라이브**: 이 작업은 백테스트(연구) 단계 전용. 라이브 경로 무변경.
- **IX 자기수정 경계 (커널)**: **비커널.** `risk/gates.py`·caps·whitelist·worker·audit 무변경.
  신규 모듈(`strategy/universe.py`)·CLI 명령·스크립트 플래그만 추가.
- **X 측정 기반 성장**: 단일 잣대(스펙 008 metrics, 스펙 027 DSR) 재사용. 새 측정 정의 0건.

## 접근

1. 순수 유동성 순위 모듈(`strategy/universe.py`) — 기존 전략 모듈 스타일(결정론 Decimal,
   sentinel 처리, NON-KERNEL 헤더).
2. CLI `build-universe` — 적재 데이터셋(`CSVDataSource`)을 읽어 OHLCVBar→PriceBar 변환 후
   모듈 호출. 읽기 전용.
3. 수집 스크립트 `--all` 플래그 — 전체 횡단면 추출.
4. 넓은 유니버스 설정 + `portfolio-walk-forward`(기존 표본 외 + DSR 엔진 재사용)로 검증.
5. 결과를 `FINDINGS.md` 에 정직하게 기록(음수 발견 포함).

## 파일

- 신규: `src/auto_invest/strategy/universe.py`, `tests/unit/test_spec_034_universe.py`,
  `specs/034-universe-construction/{spec,plan,tasks,FINDINGS}.md`, `sp500-broad-portfolio.toml`.
- 수정: `src/auto_invest/cli.py`(build-universe 명령 추가), `scripts/fetch_sp500_subset.py`(--all).

## 리스크

- 넓은 적재(약 50만+ 행)는 SQLite 멱등 적재로 처리 — 검증됨(619,029행). 데이터는 깃 무시.
- 음수 발견 가능성(실제로 그러함) — 정직하게 기록하는 것이 헌법 X 의 핵심.
