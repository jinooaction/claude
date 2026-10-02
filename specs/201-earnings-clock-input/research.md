# Source decisions and limitations

- SEC 공식 개발자 안내는 자동 요청의 `User-Agent`에 연락처 이메일을 선언하도록
  권한다. 사용자 제공 주소를 이 요청 헤더에만 사용했다. 결과는 여전히 HTTP 403이다.
  연락처 주소는 본 저장소/출력에 저장하지 않는다.
- 공개 공급자 `ZipLime/sec-8k-events`의 고정 Parquet 두 개를 대안으로 쓴다.
  공급자 문서는 접수 시각을 SEC 자료에서 가져왔다고 설명하지만 이는 공급자
  주장이다. 원본을 나중에 내려받았다는 사실은 과거 공개/관측의 증명이 아니다.
- 기존 2014Q1 원문 감사의 30개 기업·137개 원문으로 accession/CIK를 독립 대조한다.
  증명 범위는 식별자 일치다. 본문 버전의 당시 공개나 별첨의 완전성은 미확인이다.
- 30개 기업은 2013-10-31 DIA 보유 목록으로, SEC에 제출된 2014-02-24
  투자설명서의 33쪽 표로 확인했다. 이 표가 공개되기 전 사건에 해당 목록을
  사용하면 미래 정보 오류가 되므로 원자료와 후보 집계를 분리한다. 공개 후에도
  고정 연구 집단이지 매일 변하는 DJIA 지수 구성이라고 주장하지 않는다.
- `DD`, `UTX`는 기업 변경으로 현재 종목 가격과 옛 기업 CIK의 일대일 연결을
  주장하지 않는다. 가격 성과 검증 전에 두 기업을 제외한다.

공식 자료: https://www.sec.gov/about/webmaster-frequently-asked-questions ,
https://www.sec.gov/about/developer-resources . 공개 공급자:
https://huggingface.co/datasets/ZipLime/sec-8k-events ,
https://huggingface.co/datasets/ZipLime/sec-8k-events/blob/main/PIPELINE.md .
