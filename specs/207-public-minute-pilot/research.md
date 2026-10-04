# Research: 공개 분봉 원본의 실제 접근과 경계

공식 게시자 설명서는 https://huggingface.co/datasets/ggaddam/OHLCV-1m/raw/ef1551b11d8ee3e35c7521cf36deee155b43e77d/README.md 이다.
공식 저장/API 설명은 https://huggingface.co/docs/hub/en/api 및 https://huggingface.co/docs/hub/xet/index 이다.

2026-10-02 UTC 실제 API200/private=false/gated=false를 확인했다.
403개 월별 파일 합계84447702480바이트, 2014~2019의72파일18839731617바이트는
목록상의 존재이지 전체 취득이나 완전성 증거가 아니다. 카드52MB 안내와 전체 범위가 다르다.
두 개발 월의 footer 37674바이트는 실제206/Content-Range/지문을 확인했다.
전체 SHA는 목록 값이므로 파일 전체를 실제 받은 뒤 대조해야 한다.

시간 경계: 2014-01-02T09:00Z~2014-02-01T00:59Z,
2019-12-02T09:00Z~2020-01-01T00:59Z.
뉴욕 날짜는 각각1월/12월 04:00~19:59이므로 UTC 월 비교를 선택하지 않는다.
DuckDB 시간대 문자열 변환과 표준 ZoneInfo로 별도 pytz 설치를 피한다.
정규장 기대 분은 XNYS 실제 달력의 개장 이상·폐장 미만, 가용시각은 봉 시작+1분이다.

선택: 고정 두 전체 파일 + 정확 지문, 소량 합성 TDD, 큰 작업은 GitHub.
제외: 18.84GB 일괄 다운로드, 승인/구독 필요한 paperswithbacktest 자료, 새 계정/쿠키,
가공된 첫 행을 성과로 해석하기, 205 미병합 코드를 의존성 없이 복사하기.

새 전체 원본을 공개 평문으로 재배포하지 않는다. 기존 연구 암호화 런타임/키를
별도 인증 문맥과 무작위 nonce로 재사용한다. 원본 Finnhub 출처는 게시자 주장일 뿐이며
명시 라이선스·조정 규칙·수정 이력·당시 구성은 미확인이다. provider/strategy eligible=false.
원본 취득만으로 독립 확인 구간을 개봉하거나 새 전략을 검증하지 않는다.

작은 선행 관측 영수증은 로컬 claude-data-research/20261003-public-hf-source-probe-cdn에 보존했다.
실제 전체 취득 결과는 아직 없다. 결과는 작업 완료 뒤 추가하며 선행 관측을 덮어쓰지 않는다.
