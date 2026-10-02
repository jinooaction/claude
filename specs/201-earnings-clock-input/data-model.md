# Data model

- `source-manifest.json`: 고정 공급자 개정, Parquet SHA-256, 동부 날짜 범위,
  종목/CIK/계보 제외 선언, 고정 목록의 공개 날짜. 30개 목록은 거래 허용 목록이 아니다.
- `acceptance`: accession, CIK, form, 공급자가 주장하는 `stated_at`, 당시 동부
  오프셋, 공급자 원천. 2014년 당일 실제 공개·현재 로컬 관측을 뜻하지 않는다.
- `earnings`: 같은 accession/CIK의 `Item 2.02`, 공급자가 주장하는
  `knowledge_date`, 추정 여부, 정정 여부, 본문 유무.
- `mirror`: 현재 확보한 본문 137개의 accession/CIK/filing date. 그 본문을
  2014년에 읽었다는 뜻이 아니다. 보고서는 사용한 JSON 집합의 지문을 남긴다.
- `event`: 위 세 출처를 구분해서 결합한 연구 기록. `historical_asof_proven`,
  `strategy_admitted`, `live_eligible`는 모두 거짓으로 고정한다.
  `universe_known_at_acceptance`는 고정 기업 목록의 공개 근거가 접수 날짜보다
  앞서는지만 뜻하며, 그 시점의 실제 지수 구성이나 개별 공시 공개를 증명하지 않는다.
