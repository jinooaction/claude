# Implementation Plan: 거래비용을 고려한 단타 후보 연구

**Branch**: `codex/190-cost-aware-intraday` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

## Summary

기존177 계약과18후보 결과는 불변이다. 별도 사전등록으로6개 돌파 후보를 만들고
기존 순수 모의 체결기를 재사용한다. 개발과 확인 CLI를 분리하여 개발 실패 시 확인
자료 경로 자체를 열지 않는다. 새 보고서는 기존 실거래 승인기가 수용하는 증거가 아니다.

## Technical Context

- Python3.12+, 기존 numpy/pandas/exchange_calendars/pytest, 새 의존성 없음.
- 입력177의5분 CSV+manifest; 출력 독점 생성 JSON/JSONL, 네트워크·브로커 import 없음.
- 규모:5종목, 개발1,645일·확인495일, 새6+기존18 비교 후보. 봉 캐시를 공유한다.
- 동일 결과 파일 덮어쓰기 거부. 사전등록·입력·선택·장부 해시 검증 및 NaN/Infinity 거부.
- 생성 시각은 내용 지문에서 분리한다. 검증 실패는 오류 코드로 종료한다.

## Constitution Check

- I/II: 기존5종목·종목별20%·전체80%·정수 주·무차입·무공매도 유지.
- III: 봉 처리 중 모델 호출 없음. IV: 기존 감사 기록 불변, 연구 기록 별도 신규 생성.
- V/VII: 비밀값 및 외부 API 사용 없음. VI: 연구→전진 관찰→캐너리→실거래 순서 보존.
- VIII: 전용 브랜치·SDD·전체 pytest/ruff·하네스·인계 검사 후 PR 병합. 장중 배포 보호 유지.
- IX/X: 커널·기존 위험/승격 관문 불변. live_eligible와 promotion_allowed는 항상 false.
- 설계 후 재검토: 비용 완화·과거 실패 삭제·독립 검증 구간 재사용·자본 배정 없음.
- 위험 등급2. 되돌림은 새 연구 모듈·CLI·190 포인터만 제거/복구하며177 결과와 원본은 보존한다.

## Project Structure

- `src/auto_invest/analytics/cost_aware_intraday.py`: 고정 계약 검사,6후보,개발 선택,확인 판정.
- `scripts/cost_aware_intraday_probe.py`: develop/confirm 두 명령, 출력 독점 생성.
- `scripts/cost_aware_intraday_evidence_gate.py`: 원본/계약/장부 재구성 독립 검사.
- `tests/unit/test_cost_aware_intraday.py`, `tests/integration/test_cost_aware_intraday_cli.py`.
- 이 디렉터리 contracts/research/data-model/quickstart/tasks가 완료 증거를 연결한다.

## Implementation phases

1. 사전등록을 커밋하고 개발 자료 지문을 고정한다. 실제 수익률 계산 전이다.
2.177의 IntradayCandidate/resample_dataset/simulate_candidate/지표 계산을 재사용한다.
   family=opening_range_breakout, timeframe=30/60, range_bars=1, buffer=62/124/186bp.
   기존177의 입력/사전등록/등록 후보/보고서 구현은 수정하지 않는다.
3. 개발 양비용 순수익 양수·기준 청산200·양비용 미청산0 필터 후 기존 샤프 순위 선택.
   하나도 없으면 DEVELOPMENT_REJECTED. 확인 명령은 파일 접근 전에 거부한다.
4. 개발 원본과 선택을 재계산해 검증한 뒤 확인495일을247/248로 분할한다.
   PBO는 같은 개발기간의 기존18+새6후보를8등분해 계산한다. DSR은 같은 최종 확인
   기간의24후보 샤프를 사용한다. 비교용 기존후보를 새 선택 대상으로 넣지 않는다.
5.177 판정 함수의 모든 통계 기준 적용. 누락/불능 통계 거부. 결과와 무관하게0자본.

## Complexity Tracking

헌법 예외 없음. 이미 본 개발기간에 적응한 후속 가설이므로24후보 비교만으로 모든
선택 편향이 사라진다고 주장하지 않는다. 최종 실사용 전 전진 관찰이 필수다.
