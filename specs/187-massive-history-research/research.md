# 확인한 근거

2026-09-14 조회:
- https://massive.com/pricing : 개인 Stocks Starter 월29달러,5년 역사·분봉. 무료는2년.
- https://massive.com/docs/rest/stocks/aggregates/custom-bars : 5분 OHLCV, adjusted=false,
 sort=asc, 기초 봉 limit최대50000, 거래 없는 구간은 봉이 없음.
- https://massive.com/docs/rest/quickstart : Authorization: Bearer 인증 지원.

로컬 실행 환경과 두 프로젝트의 .env에서 MASSIVE_API_KEY/POLYGON_API_KEY 존재만
확인했으며 없었다. 비밀값은 출력하지 않았다. 계정 가입·구독·결제는 하지 않았다.
2026-09-14 운영자에게 첫1개월29달러 데이터 비용 허용을 요청했다. 답변은 별도 기록한다.
새 공급자는 SIP 기반 자료이며 KIS 부분시장 체결/거래량과 동등하다고 인증하지 않는다.
