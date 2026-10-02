# Actual offline audit evidence (2026-10-02)

고정 개정 `096a24de11c29748f4270d13493b9ea49d03accd`에서 받은
`acceptance.parquet` SHA-256 `6a61769554ec5032596cb75e1c603ec847d75605740f780bcbb8033ca48f3000`,
`earnings_8k/part-00000.parquet` SHA-256
`ef1beab3a08d13a068f34dbeb817e38984793667d45b295596e515b5204070c5`.
`quickstart.md` 명령의 출력은 761016바이트, SHA-256
`269dc7bd8bbf9f0c2b1aa796cf1fc9fd0db0a164535ca2a3eaa2515f1970de44`.
사용한 로컬 본문 JSON 집합 지문은
`8d3102428c902aa652cc56297aefbe7b0fc894d4125026e22f38292239f128b7`.

- 30개 기업의 미국 동부 2013-08-23~2020-03-06: 8-K/8-K-A 접수 3321개,
  `Item 2.02` 사건 831개. 모든 831개는 accession/CIK 접수 기록에 연결됨.
- 현재 확보된 공시 본문 137개는 137개 모두 accession/CIK가 일치함. 이 중
  7개는 본문 `filing date`와 접수 시각의 미국 동부 날짜가 다름.
- 831개 중 기업 목록 공개 근거 2014-02-24 이전/당일 사건 67개는 후보 수에서
  제외한다. 추정 시각 2개, 정정본 2개, 기업 계보 미확인(`DD`, `UTX`) 42개도
  해당되는 사건을 제외한다. 중복 제외를 반영한 후보 집계 723개:
  XNYS 달력 기준 장전 476, 장중 26, 장후 220, 휴장일 1. 공급자의 세션
  분류와 다른 두 건은 추정 시각 사건이다. 역사 구간의 item/exhibit 본문은 모두 비어 있음.
- 주소를 선언한 SEC 자동 조회는 HTTP 403. SEC 원본 직접 수집 성공으로
  말하지 않는다.

모든 결과의 `historical_asof_proven`, `strategy_admitted`, `live_eligible`는 거짓.
이는 T013 전략 통과가 아니다. 다음 단계는 과거 본문의 당시 공개 시점과
독립 가격/체결 자료를 증명하거나, 앞으로의 서버 관측 사건으로 전진 평가하는 것이다.
