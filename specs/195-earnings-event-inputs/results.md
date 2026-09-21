# 검증 기록

2026-09-21. 구현은 연구 입력용이며 통과 전략·전체 실사용 완료 판정이 아니다.

## 실제 원문

194에서 보존한 Microsoft 일정·발표문을 input-195-v1.json으로 분류하고 실제 import했다.
원문 지문은 [194 기록](../194-sparse-opening-research/event-input-feasibility.md)과 일치한다.
현재 로컬 관측 완료 시각은 `2026-09-21T04:33:00.352847+00:00`이다.
이전 다운로드 시각을 복원하거나 임의로 과거 시각을 넣지 않았다.

- 원문 2개, 사건 2개(scheduled/reported 각각1개).
- `2014-01-24T00:00:00Z` 조회: 사건0개.
- 실제 관측 완료 시각 조회: 사건2개.
- 예정의 after_close를 실제 발표 시각으로 복사하지 않고 실제 발표는 date_only로 남겼다.
- source_authenticity_verified=false, local_observation_only=true, live_eligible=false.
- coverage_unknown_issuers에 Microsoft를 유지한다. 두 문서 확인은 회사 전체 역사 범위 증명이 아니다.
- 묶음 지문: `03978ab6bc409878f6de3efd813c6e6ae1f833422c574aea72fbb0b0270028b7`.

자료는 저장소 밖 `/Users/mason/Projects/claude-data-research/20260921-hf-raw/event-source-pilot-v1/`의
input-195-v1.json, bundle-195-v1/, query-195-historical-v1.json, query-195-observed-v1.json이다.
타사 원문 전체나 새 수익률 자료를 저장소에 추가하지 않았다.

## 자동 검사와 검토

- 구현 전 단위 모듈 없음과 CLI 없음으로 실패 확인, 구현 후 신규26개 통과.
- 기존 관측 입력16개를 포함한 관련42개 통과(1.32초).
- `uv run ruff check src tests scripts/earnings_event_inputs.py`: 통과.
- 하네스14/14, HANDOFF 사실 검사 통과. 최초 검사에서 오래된 main 요약행을 발견해 실제748b14e로 정정했다.
- 독립 검토의 동률 시각 정정본·저장 후 manifest 크기 초과를 반례로 재현한 뒤 수정했다.
- 전체 회귀 검사는 아직 결과 대기. 병합·배포는 아직 미완료다.

## 남은 전체 목표

과거 공시 전체 범위/과거 버전 증거, 전진 수집, 통과 전략, 동일 후보 전진 관찰,
실행 동등성, 단타 실주문 운영 검증은 남았다. 이 도구는 소급 증거를 만들거나
기존 최소31회 전략 시도를 지우지 않는다. 495일 확인 자료는 열지 않았다.
