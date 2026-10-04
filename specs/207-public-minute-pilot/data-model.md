# Data Model

`SourceFile(month,path,size,sha256)` 두 항목은 코드 상수로 고정한다.
저장소 ggaddam/OHLCV-1m, revision ef1551b11d8ee3e35c7521cf36deee155b43e77d.
2014-01:256575689 / 55925f7870effd4cad312f365133a7f405915d88130038791f28b6f6e5142871.
2019-12:257874677 / 6f7a8b521cd70c41ebf5296d9ee1920f8c41ccd6e376626e18798438471c3e1e.

`report.json`: schema/source revision, 다운로드 완료 파일 지문/크기, 품질별 개수,
뉴욕 월 경계, 종목별 정규장 행/관측 세션/완전 세션/기대 분 누락,
`full_source_verified`, `quality_accepted`, `archive_complete`, `strategy_eligible=false`,
`provider_eligible=false`, `orders_submitted=0`, `returns_examined=false`.
가격 행/가격 요약/성과/요청 서명 URL/개인 연락처를 넣지 않는다.

`archive-index.json`: 각 암호문 이름/크기/지문, nonce, 고정 원본의 지문/크기,
AES-GCM 인증 문맥. 암호화 키는 포함하지 않는다.
`claim.json`: 검토 Git SHA와 최초 실행 식별자. release의 존재가 동일 검토 코드 재취득을 차단한다.
취득 완료 뒤 암호화/업로드 실패는 archive_complete=false이며 취득 성공과 구별한다.
