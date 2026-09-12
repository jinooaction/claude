# 구현 계획

FR009 (위험3): 공식 주식잔고조회 TTTC8434R를 읽기 전용으로 연결한다. 결제 기준
자산표가 장중 국내 보유를 완전히 포함한다는 가정을 피하기 위한 현재 잔고 원본이다.
INQR_DVSN=02, FUND_STTL_ICLD_YN=Y, PRCS_DVSN=00으로 같은 계좌의 전 페이지를
수집한다. 호출자는 기존 제한/재시도/차단기를 사용하고 전체 읽기는30초로 제한한다.
종목별 수량/매도가능/평가/대출과 반복 요약을 검증한다. 공개값은 건수/숫자 상태이며
KRW 현금을 USD로 바꾸거나 전체 계좌/NAV 승인을 부여하지 않는다. 원본 기록기의
고정 GET 목록에 이 경로만 추가하고 기존 계좌 묶음을 유지한다. 복구는 추가 조회를
되돌리는 것이며 원본 기록은 삭제하지 않는다. 모의 다중 페이지/변화/오류/시각/취소,
장부 재열기/비노출과 실제 승인된 서버 수집을 검증한다.
공식 근거:
https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_account_balance/inquire_account_balance.py
https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py
https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/domestic_stock/inquire_balance/chk_inquire_balance.py

FR008은 추가 API 없이 같은 저장 원본을 분석한다. 전체 자산표는 원본 행 순번과
고정5열의 숫자 상태만 남기며20/17행 이외의 표는 해석하지 않는다. 일반 잔고는 OTCB,
지원 미국 거래소,그 외로 구분해 수량·가격·평가액의 상태별 건수를 반환한다. 현재/결제
요약은 모든 요약 행을 보존해 고정 현금·채무 항목의 상태를 기록한다. 실패/과다/임의
입력·금액 비노출·중복/반복 보고·실제 수집 연결을 검증하고 전체 회귀와 서버 확인을
진행한다. 판정·돈 경로 변경 없음. 복구는 새 출력 연결을 되돌리며 원본 기록은 보존한다.

1. 184의 AccountHistory와 모의 원본 통합 시험을 main 기반 별도 worktree에 분리한다. 거래 비용·자격·주문 코드는 포함하지 않는다.
2. main의 intraday_balance_check에 --history-db와 --execution-db만 추가한다. 기존 무옵션 출력/조회는 유지한다.
3. 기존 main 도달성 검사를 보존하는 서버 고정 경로에 비공개 저장을 연결한다. 임의 셸·PR 코드 실행을 허용하지 않는다. 저장 디렉터리 소유·권한과 실패 반환을 검증한다.
4. 관련 시험 후 전체 회귀·린트·하네스·인계·PR 관문을 수행한다. 안전 경계 변경 커밋에 this changes the safety perimeter를 기록한다.
5. 독립 출시 후 서버 원본의 수집 범위와 계산 계약을 검토해184 입력기로 이어간다. 공개 보고서에는 금액을 내보내지 않는다.

6. FR006: 기록 성공 후 같은 메모리 원본에 구조 분석기를 적용해 진단 결과에 연결한다.
   누락/잘못된 숫자는0으로 바꾸지 않는다. 중복 계산은 유효한 현금 구성5개로만 수행하며
   나머지 주문가능/환율 필드는 개별 분포만 기록한다. 원본 장부와 검증 판정은 보존한다.
   공식 필드 근거: https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py
   실패 시 원본을 보존하고 구조 분석 불가로 표시한다. 되돌림은 출력 연결 제거이며 기록을 삭제하지 않는다.

## 근거
FR007은 고정 원본 필드만 Decimal 정밀도80으로 계산한다. 복수 USD 통화 행이나
복수 요약 행을 선택/합산하지 않고 비교 불가로 처리한다. 응답별 결과를 보존하며
반올림 허용폭을 임의 추가하지 않는다. 현재/결제 보고서 사이의 현금 의미 차이는 유지한다.
산식 설명: https://file.truefriend.com/Storage/research/hts_guest_0130.pdf 40쪽.
과거 HTS 설명과 현재 API 필드의 대조 후보이며 일치해도 인증을 부여하지 않는다.

현재 deploy/kis-smoke-on-instance.sh는 목표 커밋이 origin/main의 조상인지 검사한다. PR793 전체를 미완료 상태로 병합하는 대신 원본 수집만 독립적으로 완성한다.
