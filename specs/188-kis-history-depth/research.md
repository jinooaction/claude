# 근거

공식 예제2026-09-14 확인: NREC 최대120, PINC=1, 다음조회 NEXT=1,
KEYB는 직전 마지막 봉에서 n분을 뺀 YYYYMMDDHHMMSS다.
https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py

기존 collect_kis의30일/40페이지는 로컬 정책이다. 일반 정규장 자료의 전체 보관 기간으로
확정할 근거가 없다. 새 조회는 임의 과거 커서를 처음부터 넣지 않고 정상 첫 페이지부터 진행한다.
최대80페이지는 탐색 비용 한도이며 제공자 한도라고 해석하지 않는다.
