# 조사 근거

2026-09-14 후속: 서버 연구34767824895는 현재 식별자의1일만 검사했다. 이를
서버 전체 보관 이력으로 단정할 수 없으므로 모든64자리 코드 폴더의 정상 보관 묶음을
독립 검증하고 공급자/합성 여부별 거래일 합집합을 자료 재고로 보고한다. 원본 코드가
달라도 원본/CSV 검증은 각각 필요하다. 합집합 개수는 합친 전략 성과나 전진 실적이 아니다.

공식 해외주식 분봉 예제의 현재 확인 범위:
https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py
한 요청 최대120건과 이전 응답 마지막 봉보다 앞선 시각을 이용한 다음 조회가
설명되어 있다. 이 예제만으로 전체 과거 보관 기간을 확정할 수 없다. 아래의30일은
현재 collect_kis가 강제하는 수집 범위이며, 이번 공식 예제 조회로 증권사의 절대
최대 보관 기간을 재확인했다는 뜻은 아니다. 장기 자료가 불가능하다고 단정하지 않는다.

181 service_cycle은 /var/lib/auto-invest-intraday/소스식별자/sessions/날짜 아래에
원본 응답·5종목 CSV·manifest를 보관한다. 미완 partial 폴더는 삭제하지 않는 계약이다.
read_service_status는 현재 식별자와 상태 신선도를 검증한다. 기존177 load_intraday_dataset은
단일 자료 폴더의 형식·CSV 지문·완결 세션을 검증하며 run_intraday_paper_challenger는
18개 후보와756세션 기준으로 연구 판정을 만든다. 여러 날짜 폴더를 이 검증기에 넘기는
경로가 없어서 별도 결합기를 추가한다. 기존 모의 수집기의 qualified_forward_sessions=0은
고정 진단 상태로, 실제 자료 개수의 출처로 사용하지 않는다.

입력 파일은 공개 시장자료이며 API 자격값이나 계좌 잔고를 읽지 않는다. 두 공급자의
부분 시장·수정 정책을 같은 것으로 취급하지 않는다. 자료를 합치는 기능이 과거30일
조회 한계나756세션 실제 자료 부족, 정식60세션, 실시간 현금/NAV를 해결하는 것은 아니다.
