# 무료 과거 자료 확보 경로 조사 — 2026-09-14

## 판단

유료 데이터가 필수라는 결론은 근거가 부족하다. 운영자는 무료 대안을 먼저 찾도록
지시했다. Massive 비용 승인 대기를 주 작업의 막힘으로 삼지 않고 유료 경로를 보류한다.
현재5종목·756거래일·정규장5분 OHLCV를 유지한다. 일봉을 분봉으로 만들거나
부족한 거래량을 채우거나 공급자/수정 정책을 섞어 연구 통과를 만들지 않는다.

| 순서 | 경로 | 확인한 근거 | 아직 확인하지 못한 것 |
|---|---|---|---|
| 1 | 기존 한국투자 API 연속 조회 | 공식 예제는 NEXT/KEYB와 요청당120개를 지원한다. 로컬30일/40페이지 제한은 프로그램 상수다. | 실제 최장 과거 범위. 공식 예제에 일반 정규장30일 최대라는 근거가 없으며3년 제공도 입증되지 않았다. |
| 2 | Alpaca Basic 과거 통합시장 자료 | 공식 가격표는 무료·2016년 이후·최근15분 제한·분당200회다. FAQ는15분 이상 과거 SIP 조회에 유료 구독이 필요 없다고 명시한다. 기존 collect_alpaca가 이미 연결돼 있다. | 사용자 계정/키가 없다. Paper 문서는 IEX 전용이라고도 설명하므로 실제 무료 계정의 과거 SIP 권한을 작은 읽기 요청으로 확인해야 한다. |
| 보조 | Yahoo/yfinance | 유지관리자 문서는 분봉 과거60일 제한을 안내한다. | 756거래일 대체로 선정하지 않는다. 최근 구간 교차 확인용 후보다. |
| 보조 | Dukascopy | ETF CFD와 bid/ask 측 자료가 존재한다. | 주식 실제 체결 거래량과 같은 자료라고 볼 근거가 없어 기존 검증에 그대로 넣지 않는다. |
| 제외 | Kibot 무료 샘플 / Alpha Vantage 장기 분봉 | Kibot 현재 무료 분봉은 IBM/OIH 최근3개월, Alpha Vantage는 과거 분봉을 유료로 안내한다. | 현재5종목756일 무료 대안으로 채택하지 않는다. |

Alpaca는 기존 한국투자 매매 계좌를 옮기는 제안이 아니다. 데이터 읽기만 별도로
연결하는 후보이며 입금·실거래 계좌 개설을 이번 조사에서 수행하거나 요구하지 않는다.
Paper 계정은 공식 문서상 이메일 가입이 가능하지만 가입·약관 동의·키 발급은 미수행이다.
공식 문서의 일반 무료 데이터 설명과 Paper 권한 표현 차이를 숨기고 확보를 보장하지 않는다.

## 가장 작은 다음 확인

1. 서버의 기존 KIS 인증을 그대로 사용하는 별도 읽기 진단을 검토한다. 운영 수집기의
   30일 제한을 무작정 제거하지 않는다. SPY 한 종목에서 정상 첫 조회 후 공식 NEXT/KEYB를
   따라 최대80페이지/9600봉까지만 읽고 첫/마지막 시각·페이지 수·종료 이유를 남긴다.
   페이지가 비거나 반복되면 종료한다.30일 이전까지 도달하면 그 범위만 입증된 것이다.
   이 횟수는 탐색 한도이지 공급자의 최대 보관 기간이 아니다.3년 확보 완료로 해석하지 않는다.
2. KIS 장기 범위가 부족한 경우 무료 Alpaca 키로2023-09-07 하루의5종목 SIP5분봉을
   먼저 확인한다. 권한 부족이면 실패로 기록하고 IEX로 조용히 바꾸지 않는다.
3. 샘플 권한과 자료 계약이 확인되면2023-09-07~2026-09-11을 한 공급자/수정 정책으로
   확보하고 기존18개 전략과 독립 증거 검사를 실행한다. 연구 적격과 실제 실행 적격은 구분한다.

기존 Alpaca 수집기는 split 수정 가격을 사용하고 Massive 수집기는 unadjusted다.
동일 자료로 합치지 않으며 실제 KIS 체결 동등성은 별도 검증한다.

## 이번에 실제로 확인한 범위

- 현재 브랜치0ecc101, origin/main d72325b, 초안PR827. 기존 실행 코드 변경 없음.
- collect_kis의30일/40페이지 제한과 collect_alpaca의sip/5Min/페이지 연속 조회를 직접 읽었다.
- 현재 환경과 두 프로젝트 .env에서 KIS/Alpaca 키 존재 여부만 확인했고 모두 없었다.
  서버 키 부재라는 뜻은 아니다. 기존 서버 통로는 고정 kis-smoke 명령만 허용하므로
  임의 원격 명령으로 인증 경계를 우회하지 않는다.
- 공식 문서를 현재 조회했다. 실제 KIS 장기 조회와 Alpaca 인증 GET은 이번 조사에서
  실행하지 않았다. 자료 확보나 전략 통과로 보고하지 않는다.

## 직접 확인한 출처

- KIS 공식 예제: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py
- Alpaca 무료 범위: https://docs.alpaca.markets/us/docs/about-market-data-api
- Alpaca 과거 SIP 조건: https://docs.alpaca.markets/us/docs/market-data-faq
- Alpaca Paper 가입/권한: https://docs.alpaca.markets/us/docs/paper-trading
- Alpaca 분봉 요청: https://docs.alpaca.markets/us/reference/stockbars
- yfinance 유지관리자 문서: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- Dukascopy ETF CFD: https://www.dukascopy.com/europe/english/about/fee-schedule/
- Kibot 무료 범위: https://www.kibot.com/free-historical-intraday-data.html
- Alpha Vantage 과거 분봉: https://www.alphavantage.co/documentation/
