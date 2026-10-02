# Offline audit contract

입력 두 Parquet의 SHA-256과 공급자 개정은 `source-manifest.json`에 고정한다.
명령은 accession/CIK 중복·누락, 본문 연결 실패, 원본 변조를 거절해야 한다.
성공 결과는 기존 출력 경로를 덮어쓰지 않고 JSON 파일 하나를 만든다.

`source_claimed_acceptance_*`는 공급자 원천의 SEC 접수 시각 주장이다.
`publisher_claimed_knowledge_utc`는 공개 공급자의 별도 주장이다.
둘의 일치는 공개 초나 과거 본문 버전을 증명하지 않는다. 장전/장중/장후/휴장일은
XNYS 달력과 접수 시각 기준의 분류일 뿐 해당 세션에 거래 가능했다는 뜻이 아니다.
고정 기업 목록은 2014-02-24 SEC 제출 문서로 나중에 확인했다. 그 날짜 또는 이전
사건은 목록을 소급 적용한 후보 수에 포함하지 않는다. 이후 사건도 당시 지수 구성
증거가 아닌, 공개 뒤 고정한 기업 집단의 사건으로만 해석한다.
`historical_asof_proven=false`, `strategy_admitted=false`, `live_eligible=false`를
모든 사건과 최상위 결과에서 유지한다.
