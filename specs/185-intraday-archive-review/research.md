# 조사 근거

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
