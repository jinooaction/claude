# 자료 구조

입력은 schema_version=1, profile, artifacts, index, event. 추가·중복 키는 거부한다.

- artifacts: response/metadata/warcinfo 각 `{path, sha256}`. gzip 단일 WARC 멤버, 원본·해제 각각 10 MiB 제한.
- index: `{url, timestamp, digest}`. http/https·자격증명 없음, 14자리 UTC, SHA1 base32. 응답과 URL·시각·본문 지문 일치 필수.
- profile: `cc-nutch16-post-response-v1`. 수집 소프트웨어 표기 일치 필수, 정확한 배포 커밋 인증은 아님.
- event: `{issuer_cik, kind, event_date, report_period_end, evidence_quotes}`. 회사 10자리, reported/scheduled, ISO 날짜, 기간 null 허용, 비어 있지 않은 인용문. 회사 연결은 검토자의 주장이다.
- 보고서: 현재 검사 구간, 원본·본문 지문, 연결 기록, 사건 인용, 공급자 조건부 관측 구간, 잘림 표시, 미확인 사항, strategy_admitted=false/live_eligible=false.

WARC 응답은 Content-Length/Type/Date/Record-ID/Target-URI/Warcinfo-ID 및 본문·블록 SHA1 필수. metadata는 Concurrent-To로 응답을 가리키며 URL·Date·Warcinfo-ID가 일치한다. warcinfo Record-ID는 앞 두 기록의 Warcinfo-ID와 같다.
fetchTimeMs는 0 이상 정수로 보존하고 상한에 더하지 않는다. 이번 명령은 증거 검사 보고서이며 기존195 과거 조회는 바꾸지 않는다.
