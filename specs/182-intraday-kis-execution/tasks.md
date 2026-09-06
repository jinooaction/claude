# KIS 단타 실행 작업
## 기반
- [x] T001 `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md` 작성과 돈경로 확인.
## US2 취소 안전성
- [x] T002 [US2] `tests/integration/test_intraday_execution_contract.py`에 취소계약/거절/응답유실 시험.
- [x] T003 [US2] `broker/overseas.py`, `execution/authority.py`, `execution/cancellation.py`에 필수인수·무재시도·단일요청 감사.
- [x] T004 [US2] `worker/loop.py` 즉시취소확정·재호가를 최종상태 동기화로 교체하고 회귀시험 보정.
## US1 반복주문·청산
- [x] T005 [US1] `tests/unit/test_intraday_execution.py` 시간/현금/노출/귀속/중복/재시작/취소경합 시험.
- [x] T006 [US1] `execution/intraday.py` 상태재관측·claim·매도우선·종료청산·차단사유 구현.
## US3 계정없는 검증
- [x] T007 [US3] `scripts/intraday_execution.py` 네트워크없는 KIS전체계약 재현.
- [x] T008 [US3] `tests/integration/test_intraday_execution_contract.py` CLI·router/authority/fill_sync·원본보존 검증.
## 출시
- [x] T009 전체3500/8·ruff·하네스14/14·HANDOFF·PR검사, PR771/18521b9 병합, 정상배포34052281701/감사34052386141/서비스관측34052387436 확인.
## 전체완료 외부/후속조건
- [ ] T010 181 T012~T014의 실제역사자료·전략합격·60세션·동등성 증거.
- [ ] T011 단타전략·자본승인 후 별도 반복실주문 헌법경계·강화캐너리·생산gateway 설치.
- [ ] T012 소액주문·체결·청산·대사 생산증거 후 전체완료.
의존성 T001→T002→T003→T004, T005→T006→T007/T008→T009.
자료조사와 로컬설계만 독립병렬. T010 이전에도 T002~T009는 진행 가능하다.
실제증거 없는 T010~T012는 체크하지 않는다.

## US4 자본 검토 후속
- [x] T013 후속 명세·계획·연구·자료 모형·명령 계약으로 범위와 가정을 기록.
- [x] T014 순수 검토 계산기·CLI와 참고 가격 예시 구현.
- [x] T015 실제 컴파일러 일치·정수주 경계·오입력·무접근 검증, 41개 통과.
- [x] T016 100/600달러 검토 보고서, 전체3541/8·린트·하네스14/14·인계, PR773/a9d7e41 병합.
T013→T014→T015→T016. T010~T012의 합격이나 실제 자본 승인을 대신하지 않는다.
