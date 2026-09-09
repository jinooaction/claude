# 자료 모델

- KIS IntradayProgram은 같은 계좌 인증으로 생성한 StrictQuoteFeed와 구독 인증 함수를
  가진다. 운용 장부 잠금 획득 후 구독을 시작하고 운용 종료 전에 연결을 닫는다.
  종료된 시세 작업은 캐시 내용과 무관하게 진입을 막는다. 일반 IntradayProgram의
  기존 외부 관측 조립은 유지되며 KIS 구성은 외부 시세 콜백 없이 구독을 소유한다.

- KISExecutionObserver는 주문 권한과 같은 계좌·키·증권사 연결을 고정하고 기존 인증
  캐시를 사용한다. 비밀값은 공개 결과에 없으며 관측 시작부터 인증·계좌 조회 완료까지
  기존30초 제한을 적용한다. 인증 갱신은 같은 권한 객체에 반영한다. 계좌 읽기 성공과
  실행 현금/순자산 검증은 별도이며 기존 미검증 판정은 그대로 보존한다.

- IntradayProgram은 조립된 기존 엔진·연구 선택·봉 수집 함수를 보관하고 run()으로
  기존 지속 운용기를 호출한다. 구성은 검증된 내부 의존성을 명시적으로 받아야 하며
  자격 검사 생략이나 async 검사 함수를 허용하지 않는다. 자격 공급자 자체는 별도 구현이다.
  실제 후보/소스 지문·계좌/라우터/권한의 같은 DB·브로커·확정 준비 한도를 검사한다.
  실행 중 계좌·자본·지문 변경은 고정 오류로 차단한다. 기존 라우터 마지막 검사는 보존한다.

- ResearchSelection은 재계산 결과의 후보(부족/불합격이면 없음), 공급자, 실행 코드 커밋,
  자료 지문·연구 결과 지문·현재 실행 지문·판정·실제 세션 수/부족분을 묶는다.
  KIS 이외 공급자는 자동 변환하지 않으며 execution_identity=None을 유지한다.
  public()은 항상 live_eligible=false이며 실제 자격/전진 실적을 발급하지 않는다.
  원본 사전등록 바이트를 한 번 복사해 연구와 후보 구성에서 같은 내용을 사용한다.

- ExecutionObserver는 신뢰하는 프로그램 내부 비동기 계좌 읽기 함수와 동기 시세 캐시를
  기존 Observation으로 변환한다. 전체 페이지·계좌 범위·현금 합산·NAV 검증은 bool true,
  unverified_assets는 빈 dict여야 한다. execution_cash/nav는 USD 숫자 문자열이고
  구매가능 금액·사용자 승인으로 대체하지 않는다. 이 모델은 증명 발급기가 아니다.
- 계좌 조회 시작·완료와 수집 전체는30초 이내여야 하며 호출도30초에 취소한다.
  기존 보유·매도 가능 수량·열린 주문 식별자는 보존하고 임의 정규화로 누락하지 않는다.
  시세 발생시각은 그대로 유지한다. 오래된 유효 시세는 계좌 기반 취소를 막지 않지만
  엔진의 가격 사용 직전 신선도 검사를 통과시키지 않는다. 미래 시세·수신시각은 거절한다.

- SourceQuote는 수신시각과 발생시각을 분리하며, 26필드의 종목·구독키·시장·가격과
  한국/현지 원문 날짜·시간을 보존한다. 실행용 snapshot은 현재 발생시각 나이 0~30초만 반환한다.
- BuyingPower는 symbol, exchange, limit_price, foreign_orderable_amount,
  foreign_orderable_qty, started_at, completed_at을 묶는다. 음수·소수 수량은 거절한다.
- 상태 파일은 schema=184, run_id, phase, updated_at, last_result만 저장한다.
  인증값·계좌번호 없음. 상태는 원자 교체, 프로세스는 별도 파일 잠금으로 소유한다.
- stop 파일은 현재 run_id에 묶인다. 과거 중지 요청으로 새 실행을 중단시키지 않는다.
- external_holdings는 기존 기준표 로더의 정규화된 종목→양의 정수 수량을 복사한 읽기 전용 매핑.
  실행 엔진의 일별 기준과 주문 결과에는 정렬된 JSON의 SHA-256 해시만 추가한다.
  공용 체결 장부와 합산 대조하며 단타 소유에는 포함하지 않는다.
- 실행 엔진 제어 기록은 전략 접두사의 control 식별자에 STOP_REQUESTED/STOP_COMPLETED
  사건을 추가한다. 완료보다 뒤에 있는 요청은 재시작에서도 정리를 계속하게 한다.
- 실주문 운용 상태는 공용 DB 경로에 종속된 상태 폴더와 별도 수명주기 잠금을 사용한다.
  봉 수집 결과, 관리 결과, 중지 의도, 정리 완료를 구분하고 계좌 비밀값을 저장하지 않는다.
# 보관 자료의 연구 연결

ArchiveReview는 실제 session_count, required_sessions(756), missing_sessions,
missing_calendar_sessions, incomplete_archive_count, provider, synthetic,
dataset_fingerprint, 기존177 decision으로 구성한다. observation_type은
HISTORICAL_RESEARCH이며 live_eligible=false, orders_submitted=0이다.
합성 여부·부분 시장 수정 정책을 원본에서 보존하고 합성 또는 누락 자료를 연구 합격으로
바꾸지 않는다. source.json의 archives에는 날짜별 원본/manifest 지문을 남긴다.
