# 구현 계획

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
