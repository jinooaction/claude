# Implementation Plan: 누락 보존 시초 돌파 연구

**Branch**:codex/194-sparse-opening-research | **Date**:2026-09-21 | **Spec**:[spec.md](spec.md)

## Summary
193 관측 입력과 단일 후보를 연결한다. 전체 기간 공유 현금·보유·청산대기 장부를
새로 유지하고 기존177의 일별 초기화 실행기는 재사용하지 않는다.

## Technical Context
- Python3.11,기존 exchange_calendars,표준 CSV/JSON,193 ObservedSeries.
- 오프라인CSV manifest,새 출력 폴더의JSON/CSV. broker/DB/network접근없음.
- pytest반례와별도현금재계산.30종목×1515거래일,날짜별처리로메모리를제한한다.
- 최근14개달력일의시초요약·현재날짜관측·계좌상태를유지한다.

## Constitution Check
I/II:연구명목한도/고정30파일·실제자본0. III:분봉별LLM없음.
IV/V:연구장부추가기록·비밀값미사용. VI:승격경로없음. VII:오프라인입력만.
VIII.A:장중배포금지유지. IX/X:Kernel/실주문/운영설정미변경.
누락증거를합격으로바꾸지않는다. 설계전후위반없음. 활성포인터/새연구경로등급2.

## Project Structure
- src/auto_invest/analytics/sparse_opening_research.py:신호·연구계좌·결과.
- scripts/sparse_opening_research.py:계약확인·재생·장부재검사.
- tests/unit/test_sparse_opening_research.py:인과성/현금/잔량반례.
- tests/integration/test_sparse_opening_research_cli.py:실행·지문·오류·덮어쓰기.
- contracts/preregistration.json:성과조회전봉인.

## Implementation Strategy
입력검사→신호반례→계좌반례→CLI→실자료→독립산술→전체회귀→출시.
계약을검토하고봉인커밋이후실제성과를실행한다.193및177~192계약은유지한다.
실패시새연구경로중단/포인터193복원. 기존기능제거없음.
