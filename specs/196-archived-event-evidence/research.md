# 조사 결정

- 기존195의 로컬 시각을 과거로 바꾸지 않고 별도 증거 보고서로 출력한다.
- WARC 1.0, 응답200, Nutch 1.6 (CC)/CC WarcExport 1.0만 먼저 지원한다. 일반 Memento는 같은 의미로 해석하지 않는다.
- Common Crawl의 2014-02-20 공식 글 https://commoncrawl.org/blog/common-crawl-move-to-nutch 가 연결한 Aloisius/nutch cc의 44d8190ccf825cb985ecd366eff724494663fda8을 조사했다. Fetcher는 응답 후 시각을 저장하고 WarcExport가 이를 사용하며 WarcWriter는 GMT 초 단위로 표현한다.
- 다음 초를 조건부 수신 후 상한으로 계산한다. 수집 소요 시간의 추가는 중복 계산이다. 공개 코드와 실제 배포 커밋의 일치·공급자 시계는 가정으로 표시한다.
- readPlainContent는 Content-Length가 없으면 정상 작은 문서에도 length 표시를 붙일 수 있다. 표시를 보존하며 실제 원문 전체 완전성은 인증하지 않는다.
- 실물 근거는 `/Users/mason/Projects/claude-data-research/20260921-hf-raw/event-source-pilot-v1/issuer-source-pilot-v1/company-commoncrawl-v1/` 및 `crawler-timing-v1/`다. 지문·연결 검사는 끝났으나 자동 생산 입력으로 채택하지 않았다.
- 미확인 사건 처리 지연·전체 종목·기간 범위는 출력 한계로 명시한다. 정확한 최초 공개 초를 추가 필수조건으로 만들지 않는다.
