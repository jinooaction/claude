# Offline audit contract

입력 두 Parquet의 SHA-256과 공급자 개정은 `source-manifest.json`에 고정한다.
명령은 accession/CIK 중복·누락, 본문 연결 실패, 원본 변조를 거절해야 한다.
성공 결과는 기존 출력 경로를 덮어쓰지 않고 JSON 파일 하나를 만든다.

`source_claimed_acceptance_*`는 공급자 원천의 SEC 접수 시각 주장이다.
`publisher_claimed_knowledge_utc`는 공개 공급자의 별도 주장이다.
둘의 일치는 공개 초나 과거 본문 버전을 증명하지 않는다. 장전/장중/장후/휴장일은
XNYS 달력과 접수 시각 기준의 분류일 뿐 해당 세션에 거래 가능했다는 뜻이 아니다.
`historical_asof_proven=false`, `strategy_admitted=false`, `live_eligible=false`를
모든 사건과 최상위 결과에서 유지한다.
