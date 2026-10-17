# 연구 결정

## 현재 단계 — 2026-10-17 실제 연구 결과와 추가 자료 경로

연구 220의 고정 단일 가설도 개발 검증에서 탈락했다. 1,645세션에서 기준/가혹 비용 각각
243건을 청산했지만 수익률은 -30.70296648%/-37.66464256%다. 비용 전에도 손실이다.
최소 누적 시도37, 보호495세션 미개봉, 실제 주문·승격 자격0을 유지한다.
정확1cd9839d의 전체38989180391은5913통과/13생략/실패·오류0이며,
[PR899](https://github.com/jinooaction/claude/pull/899)로 main6bbabc55에 병합됐다.
[원본 검증 보관](https://github.com/jinooaction/claude/releases/tag/research-220-validation-1cd9839d)은
새 연구와 기존 호환 재생, 전체 XML, 초기 문구 호환성 실패까지 보존한다.
소프트웨어 검증 성공은 T013의 전략 합격이 아니다. T013~T016은 계속 미완료다.

추가 HF 원본 수집은 키 부재만의 문제가 아니다. 2026-10-17 재확인한
[10월10일 시행 약관](https://hfdatalibrary.com/pages/terms) 3절은 학술·교육 연구를 목적으로 하며
실자금 전략의 구축·조정에 자료를 의존하지 않도록 명시한다.
[현재 라이선스 안내](https://hfdatalibrary.com/pages/license)도 편집물의 복제·공유 허용과
거래 목적 이용을 구분한다. PR876은 보류하며 앞서 요청한 HF 키 등록도 보류했다.
키가 생겼다는 이유로 새 HF 파일을 실거래 검증 원본으로 채택하지 않는다.

[현재 원천 설명](https://hfdatalibrary.com/pages/issues)은 2022-03-07 이후 IEX 단일 거래소 자료이며,
10월6일 가격 기준을 주식분할만 조정하도록 바꿨다고 설명한다. 새 파일과 옛 파일을 섞지 않는다.
이는 아래 9월의 PiTrading 원본 취득 사실이나 당시 권리 기록을 삭제·소급 변경한 것이 아니다.
옛 고정 묶음은 기존 실패와 연구 재현 기록으로 보존하며 현재 실자금 이용 권리가 확정됐다고 주장하지 않는다.

Alpaca 공식 [자료 안내](https://docs.alpaca.markets/us/docs/about-market-data-api)와
[FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)는 인증된 무료 계정의 2016년 이후 역사 자료,
15분보다 오래된 SIP 조회 경로를 설명한다. 현재 환경과 저장소 비밀 설정에는 해당 키가 없다.
2026-10-17 운영자는 기존 Alpaca 계정 또는 다른 허가된 자료의 유무 질문에
"추가 계정이나 자료가 없습니다"라고 답했다. 질문은 답변 완료이며 같은 계정·키·자료 요청을 반복하지 않는다.
새 가입·유료 구독은 하지 않았고 이를 실행할 추가 승인도 없다. 추가 사용 가능한 자료 접근은 확보되지 않았다.
이는 기존 T012 취득 기록이나 T013~T016의 완료 조건을 바꾸지 않는다.
기존 KIS 계좌와 143달러 예약 복구 범위는 그대로다. 수집기 허용 목록이나 돈 경로 변경은 없다.

## 과거 확인 — 2026-09-21 실제 장기 자료 재검증

T012(756세션 실제 자료 확보)는 완료했다. 운영자는 무료 HF Data Library 가입,
출처 표기,개인 연구자 프로필 등록을 승인했고 실제 원본5개를 내려받았다.
기존 한국투자 계좌는 유지한다. 아래2026-09-06~07의 계정/자료 부족 문단은 당시 기록이다.
Alpaca 새 계정이나736일 추가 KIS 수집을 현재 필수 조건으로 다시 요구하지 않는다.

### 입력과 원본 근거
취득시각2026-09-20T21:56:16.926205Z,1분 Parquet5개 총220131559바이트.
원본SHA256은 [189 취득 기록](../189-kis-five-symbol-review/hf-revalidation.md)의5개와
현재 다시 읽은 파일이 모두 일치했다. 파일의 Parquet 시작/끝 표식도 확인했다.
원본행수·조정방식·공급자 경계는 같은 기록과 manifest에 보존돼 있다.
공급자는 HF Data Library/PiTrading이며 분할·배당 조정 자료다.
2022-03-07 이후 IEX와 섞지 않았다. 관측 분봉만5분으로 집계하고 누락을 만들지 않았다.

정식 입력 검사는5종목의 파일 해시·행수·시각·양수OHLC/거래량·XNYS 정규장·
조기폐장·완전 시각집합·공통 거래일을 검사한다.2026-09-21 실행74509 exit0 결과:
- 실제 자료표시 synthetic=false,공통1645세션,2013-08-23~2020-03-06.
- SPY/QQQ/IWM/TLT/GLD 각각127734개의5분봉,quality_reasons=[].
- manifest SHA256 `c4b6c6336ee0747464fde730f6d894ba3b8814c14567406f49cb0e528ea8fdfc`.
- 자료 지문 `sha256:5d6ae81596425c147f3456bbbd10798834ec4260da2a03cf8a889f6a13c7b357`.
- 원본과 입력은 `/Users/mason/Projects/claude-data-research/20260921-hf-raw/` 및 그 아래 `research-input/`에 보존.

재현은 현재 `noise_band_intraday.load_development`의 고정 manifest 검사와
`intraday_paper_challenger.load_intraday_dataset`의 전체 입력 검사로 수행했다.
자료표시만 믿은 것이 아니라 원본 취득 기록·해시와 실제 CSV의 완전성을 함께 확인했다.
공급자가 설명하는 거래소 범위를 독립적으로 인증하거나 조정가격을 실체결 가격으로
검증했다는 뜻은 아니다. 이 한계는 T014(공급자/체결 동등성)에 남긴다.

### 남은 단계
T013 통과전략은 없으며 실제 검증29후보 모두 미통과다. T014의 동일 후보60세션
전진관찰/체결 동등성, T015의 검증된 전략 단타운영/강화 캐너리, T016 실제체결/
감사/대사 증거는 그대로 남는다. 미개봉495일이나 합성 자료로 대신하지 않는다.
이 기록은 문서의 오래된 상태를 갱신하며 API 수집기 허용 목록이나 돈 경로를 바꾸지 않는다.

## 공급자

Alpaca Basic의 역사 자료는 2016년부터이며 SIP end가 15분 이상 과거면 무료 권한으로
접근 가능하다. 계정 키는 필요하다. IEX 실시간은 SIP와 다르므로 대체하지 않는다.
근거: https://docs.alpaca.markets/us/docs/market-data-faq 및
https://docs.alpaca.markets/us/docs/about-market-data-api (2026-09-06 확인).
GET `/v2/stocks/bars`, 5Min, sip, split, limit10000, next_page_token을 끝까지 읽는다.
근거: https://docs.alpaca.markets/us/reference/stockbars

KIS는 `/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice`, HHDFS76950200,
NMIN5, PINC1, NREC120, NEXT/KEYB를 사용한다. 약 한 달 보존이며 나스닥 부분시장
시세와 정정 가능성을 기록한다. 756세션의 대체 자료가 아니다.
근거: https://apiportal.koreainvestment.com/apiservice 및
https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_itemchartprice

## 지속 모의 운용

177 전체 기간 재생을 매번 실행하면 늦게 온 과거 봉으로 거래를 새로 만들 위험이 있다.
별도 입력 커서·처리 시각·주문 생성 시각을 기록하고 다음 봉만 체결 가능하게 한다.
다섯 종목 같은 시각의 봉을 원자적 배치로 처리한다. 고정 후보별 독립 가상 계좌다.
자료·주문·청산 모형이 다르므로 기존 연구 지문으로 실거래 승격하지 않는다.

## 단계 완료

계정 접근, 실제 3년 자료, 역사 합격, 전진 60세션, 별도 실주문 경계는 외부/후속 조건이다.
이 조건을 단위 시험이나 합성 자료로 대체하지 않는다. 모든 미완료를 tasks에 유지한다.

## 실제 접근 확인 — 2026-09-06 KST

로컬에서 collect 명령을 Alpaca와 KIS 각각 실행했다. 두 명령 모두 exit2,
`DATA_ACCESS_REQUIRED`다. 현재 프로세스 환경에 해당 공급자 키가 없고, 조회 요청이나
실주문은 발생하지 않았다. 기존 production KIS 키 부재를 뜻하지 않으며 그 비밀값을
로컬로 복사하지 않았다. Alpaca 계정 보유 여부는 운영자에게 비동기로 질문했다.
키를 채팅에 붙여넣지 않는다. 본 결과는 네트워크 계약의 실자료 성공 증거가 아니다.

## 기존 서버 계정으로 확인한 실제 자료 — 2026-09-06

PR767 main9f99501의 KIS smoke34007993027은7/7 통과했다. 기존 서버 키와
토큰 캐시로 2026-09-04 완결 세션 SPY/QQQ/IWM/TLT/GLD 각각78개의5분봉을
읽었고 정확한390개 시각·종목 집합을 검증했다. 요약 상태는
`INTRADAY_DATA_CONTRACT_OK`, 공급자는 `kis-nasdaq-partial-unadjusted`다.
수집 배치 지문은
`sha256:3056d3d75df8b3c49d1659940f9cd0f26284ce590e265ad65aba2da3eae98bc1`다.
원본은 서버 pytest 임시 디렉터리에만 저장했다. 공개 로그에는 지문과 봉 수만
남겼으며 영구 연구 자료 보관을 완료했다고 주장하지 않는다.
실제 주문0, live/forward promotion=false다. 현재 계정으로 최근 분봉 접근은
가능하다. 756세션 SIP 역사, 지속 운용, 전략 합격과60세션 관찰은 별도 미완료다.

## 생산 진단 서비스 연결 — 2026-09-07 KST

PR769/a8fb91a의 배포34045229510과 유닛 동기화34045310271 뒤 관측34045385754가
단타 timer active,service success,실제 생산 소스 지문 일치,2026-09-04 원본 영구
보관 COMPLETE,신선도11.9초를 확인했다. 상태는 휴장 WAIT_SESSION,실제주문0,
qualified_forward_sessions0이다. KIS34045313477도5종목×78봉·7/7을 통과했다.
독립 서버 운용을 설치하지 않아 자료가 쌓이지 않던 문제는 해결됐다.
이 기록은 756세션 역사,검증된 후보60세션 또는 단타 실제체결 증거가 아니다.
Alpaca 계정 접근은 아직 확인되지 않았다. 기존 저빈도 자본과 주문 권한은 유지한다.
재관측34045564976에서도 active/success/COMPLETE를 유지하며 상태 시각이
16:25:21→16:28:24UTC로 전진했고 신선도31초를 통과했다.
