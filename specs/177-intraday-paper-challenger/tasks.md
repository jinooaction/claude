# 작업 목록: 비용 현실형 장중매매 페이퍼 챌린저

**입력**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`
**방식**: 금융 연구 경계이므로 각 기능 시험을 먼저 작성해 실패를 확인한 뒤 구현한다.

## 형식

- `[P]`: 다른 파일에서 독립 진행 가능
- `[USn]`: 명세의 사용자 이야기 번호
- 모든 작업은 정확한 파일 경로를 포함한다.

## Phase 1: 계약과 기반

- [x] T001 Spec 177 요구사항·계획·자료 모델·사전등록·결과 계약을 `specs/177-intraday-paper-challenger/`에 고정한다.
- [x] T002 [P] 사전등록 18후보·5종목·비용·안전 필드와 지문 검증 실패 시험을 `tests/unit/test_intraday_paper_challenger.py`에 추가한다.
- [x] T003 사전등록 모델·후보 registry·정규 JSON 지문을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T004 [P] 5분 CSV의 시각·OHLCV·심볼·원본 지문·행 수·XNYS 세션 오류 시험을 `tests/unit/test_intraday_paper_challenger.py`에 추가한다.
- [x] T005 manifest와 5분 CSV 파서, 자료 품질 상태를 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.

**확인점**: 사전등록과 원시자료가 손상되면 전략 계산 전에 실패 폐쇄한다.

## Phase 2: 사용자 이야기 1 - 공정한 후보 비교 (P1)

**목표**: 같은 원시자료에서 15·30·60분, 3가족, 18후보를 빠짐없이 재생한다.

**독립 시험**: 2세션 합성 자료에서 18개 ID가 고유하고 모든 주기의 봉·신호가 기대값과 같다.

- [x] T006 [US1] 15·30·60분 리샘플의 OHLCV·부분 마지막 봉·불완전 봉 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T007 [US1] XNYS 개장 기준 리샘플과 진입 가능 봉 판정을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T008 [US1] 추세 지속·개장 범위 돌파·VWAP 평균회귀의 닫힌 봉 신호 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T009 [US1] 세 전략 가족의 결정적 신호·청산 상태 기계를 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T010 [US1] 후보 누락·중복·사전등록 불일치가 배치 전체를 막는 시험을 `tests/unit/test_intraday_paper_challenger.py`에 추가한다.

**확인점**: 후보 18개를 정확히 한 번씩 같은 자료로 평가할 수 있다.

## Phase 3: 사용자 이야기 2 - 비용과 미체결 (P1)

**목표**: 다음 봉·정수주·KIS 비용·거래량 참여를 반영한 체결만 손익에 넣는다.

**독립 시험**: 비용이 커지면 순성과가 좋아지지 않고 참여 한도를 넘는 수량은 부분·완전
미체결로 남는다.

- [x] T011 [US2] 신호 봉과 같은 봉 체결 금지, 다음 봉 시가 체결 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T012 [US2] 기준·스트레스 수수료·호가·미끄러짐과 정수주 가격 계산 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T013 [US2] 거래량 참여 한도의 FULL·PARTIAL·UNFILLED 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T014 [US2] 모의 주문·체결·포지션·당일 강제청산 엔진을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T015 [US2] 주문·체결·미체결·비용 JSONL 감사 행과 정규 SHA-256 생성을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.

**확인점**: 체결되지 않은 수량과 비용 전 성과가 순성과로 섞이지 않는다.

## Phase 4: 사용자 이야기 3 - 시간 분리와 과최적화 (P1)

**목표**: 개발에서만 고른 후보를 차단·최종 확인에서 한 번 평가한다.

**독립 시험**: 확인 수익을 바꿔도 선택 ID가 고정되고 다중비교·집중도 실패가 합격을 막는다.

- [x] T016 [US3] 마지막 126+126세션 분리와 최소 504개 개발 세션 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T017 [US3] 확인 구간 변경이 개발 선택을 바꾸지 않는 회귀 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T018 [US3] 공용 샤프·PSR·DSR·PBO·낙폭·이익계수·분기·집중도 관문 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T019 [US3] 구간별 일별 수익·거래 지표와 개발 전용 선택을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T020 [US3] 전체 18후보 다중비교·집중도·기준/스트레스 최종 판정을 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.

**확인점**: 전체 기간 최고 성과나 확인 구간 재선택으로 합격할 수 없다.

## Phase 5: 사용자 이야기 4 - 자료 부족과 무엣지 분리 (P2)

**목표**: 계산 실패, 자료 부족, 충분한 자료의 무엣지를 서로 다른 상태로 보존한다.

**독립 시험**: 짧은 실제 자료, 합성 자료, 충분하지만 음수인 자료가 올바른 상태를 낸다.

- [x] T021 [US4] 누락 종목·756세션 미만·200거래 미만·합성 자료 판정 시험을 `tests/unit/test_intraday_paper_challenger.py`에 먼저 추가한다.
- [x] T022 [US4] `INSUFFICIENT_EVIDENCE`와 `NO_INTRADAY_EDGE` 상태·필요 추가 증거를 `src/auto_invest/analytics/intraday_paper_challenger.py`에 구현한다.
- [x] T023 [US4] 현재 저장소에 장중 실자료가 없음을 거짓 합격 없이 재현하는 통합 시험을 `tests/integration/test_intraday_paper_challenger_probe.py`에 추가한다.

**확인점**: 엔진 시험 통과가 시장 엣지 확인으로 표시되지 않는다.

## Phase 6: 사용자 이야기 5 - 페이퍼 안전 경계와 독립 소비자 (P2)

**목표**: 어떤 결과도 자본·주문을 열지 않고 소비자가 생산자 판정을 다시 계산한다.

**독립 시험**: 판정·후보·지문·안전 필드 하나를 바꾸면 독립 소비자가 증거를 거부한다.

- [x] T024 [P] [US5] 18후보 동일성·선택·관문·안전 필드 변조 시험을 `tests/unit/test_intraday_paper_challenger_evidence.py`에 먼저 추가한다.
- [x] T025 [US5] 독립 증거 평가기와 상태 재계산을 `src/auto_invest/analytics/intraday_paper_challenger_evidence.py`에 구현한다.
- [x] T026 [US5] JSON·JSONL·한글 요약을 원자적으로 발행하는 탐침을 `scripts/intraday_paper_challenger_probe.py`에 구현한다.
- [x] T027 [US5] 독립 판정 명령을 `scripts/intraday_paper_evidence_gate.py`에 구현한다.
- [x] T028 [US5] 탐침 재실행의 결과·장부 지문 동일성과 실제 주문 0건 통합 시험을 `tests/integration/test_intraday_paper_challenger_probe.py`에 추가한다.

**확인점**: `PAPER_CHALLENGER`도 자본 0이고 최소 60세션 전진 페이퍼만 요구한다.

## Phase 7: 마무리와 품질 관문

- [x] T029 quickstart 명령과 계약 JSON 파싱을 실제로 재생하고 `specs/177-intraday-paper-challenger/quickstart.md`를 사실과 맞춘다.
- [x] T030 관련 단위·통합 시험과 `uv run ruff check src tests`를 통과한다.
- [x] T031 전체 `uv run pytest`를 통과한다.
- [x] T032 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과한다.
- [x] T033 PR 본문을 `.github/pull_request_template.md`에 맞춰 작성하고 `scripts/check_pr_quality_gate.py`를 통과한다.
- [ ] T034 Spec 177 작업 상태와 실제 자료 부족·실거래 무변경 사실을 `HANDOFF.md`에 갱신한다.
- [ ] T035 커밋·푸시·PR 검사·merge commit·off-hours exact-main 배포 상태를 확인한다.

## 의존성 순서

1. T001 → T002~T005로 계약·입력 기반을 닫는다.
2. T006~T010이 후보 비교 기반을 제공한 뒤 T011~T020의 체결·판정을 붙인다.
3. T021~T023은 완성된 판정기에 자료 부족 상태를 추가한다.
4. T024~T028은 생산자 출력이 안정된 뒤 독립 소비자와 탐침을 닫는다.
5. T029~T035는 모든 사용자 이야기 완료 뒤 실행한다.

## 병렬 가능 지점

- T002와 T004는 같은 시험 파일을 순차 편집해야 하므로 실제 구현에서는 직렬로 처리한다.
- T024는 생산자 결과 계약이 고정된 뒤 별도 시험 파일에서 진행 가능하다.
- 문서 계약 검증과 소스 린트는 구현 완료 뒤 병렬 실행할 수 있다.

## 완료 기준

- 18후보·5종목·3주기의 재생과 비용·시간·통계 관문이 자동 시험으로 재현된다.
- 자료가 없거나 짧으면 `INSUFFICIENT_EVIDENCE`, 충분한 무엣지는 `NO_INTRADAY_EDGE`다.
- 합격을 포함한 모든 상태에서 실주문 0건, 자본 0%, 라이브 변경 0건이다.
- 전체 시험·린트·엄격 하네스·HANDOFF·PR·배포 확인까지 끝나야 완료다.
