# 자료 모델

- BrokerExecution.reported_order_quantity: 엄격한 조회에서 읽은 원래 주문 수량.
  누락은None, 제공된 잘못된 수량/체결량보다 작은 수량/같은 주문의 변경은 거절한다.
- ExecutionCostAssessment.orders_json: 미체결을 포함한 모든 조회 주문의 원래 수량,
  실제 체결 수량과 장부 의도의 원래 신호. interval_digest에도 포함한다.
  model_fill_quantity_verified는 다음 봉의 정수주 모델 수량과 모든 주문을 대조한
  부분 결과이며 quantity_issues에 차이/누락을 보존한다. 실행 승인과 구분한다.

- BrokerExecution.reported_order_date: 엄격한 누적 조회 파서가 보존한 원문 달력 날짜.
  선택적 date이며 ordered_at_utc는 계속None이다. 원래 행끼리 날짜가 다르면 같은 주문
  번호라도 합치지 않는다. reported_order_trade_dates_match는 단일 주문에 대응하는
  보고 행의 매매일 일치이며, 날짜 누락은False다. 등록일 조회의 전체 범위 증명은 아니다.

- 관측 구간의 side/average_fill_price/reported_fees: 같은 인증 실행 조회와 단일
  종목/방향/주문 보고서 대조에서 얻은 값. 비용 지문의 원본 조회/수수료에 결합한다.
  next_bar_price_bound_verified/next_bar_fee_bound_verified는 원래 신호 직후 봉 시가를
  기준으로 연구 spread+slippage와 commission 한도를 검사한 부분 결과다. 가격 방향과
  수수료 기준 대금은 독립 검사하며, cost_issues에 누락/한도 초과를 기록한다.
  기본 비용 모델도 interval_digest에 포함한다. 출처 인증/전체 실행 동등성은 별도다.

- intraday_execution_claims.payload.signal_bar_end/decision_kind: 실제 주문의 원래 신호 봉
  종료 시각과 SIGNAL/STRATEGY_EXIT/DRAIN 구분. 전략 청산은 원래 사건에도 시각을 저장해
  부분 체결·취소·재시작 후 새 주문에 그대로 전달한다. 과거 시각 없는 사건은 추정하지 않는다.
  비용 검사는 같은 스냅샷의 주문 식별자/전략/종목/방향/수량/지정가와 일치하는 의도만 연결한다.
- interval_model_json.next_bar_timing_verified: 모든 전송 전~수신 완료 닫힌 구간이
  [원래 신호 봉 종료, 종료+5분) 안에 있음을 확인한 결과. 거래량/시장 출처와 별도이며
  강제 청산·과거 의도 누락·범위 밖 구간은 시간 증거로 승격하지 않는다.

- collection_proof: 서버 수집기 코드 지문, 정규화된5종목 봉 지문, 수집 시작/완료 UTC,
  schema/scope와 서버 키 서명. 모의 사건의 해시에 포함하고 독립 재생에도 그대로 전달한다.
  모든 완결 세션의 모든 봉에 유효한 증명이 있을 때만 서버 수집 출처 확인이 참이다.
  그 결과는 ExecutionQualification.interval_model_json의 출처 항목으로 전달하며
  source_attestation_basis=TRUSTED_SERVER_COLLECTOR로 신뢰 근거를 구분한다.

- FillPayload.broker_response_received_at_utc: 실제 GET이 끝난 뒤 잡은 로컬 UTC 시각.
  논리적 observed_at_utc 및 executed_at_utc와 별개이며 기존 행에는 없을 수 있다.
  비용 스냅샷의 fill_audits를 모든 fills와 체결번호/수량/가격/주문/전략으로 대조한 경우만
  가장 늦은 수신 시각으로 구간 상한을 좁힌다. 일부 누락/불일치는 현재 GET 상한을 쓴다.
- ExecutionQualification.interval_model_json: 동일 독립 재생의 완결 세션 봉에 대한
  구간 계산 결과. registered_forward_replay_verified는 시장 원본 인증을 뜻하지 않는다.

- settled_cash_calculation: CALCULATED/UNSUPPORTED/INVALID와 범위, 내부 cash 또는
  실패 reason. CALCULATED도 full_account_verified=false이며 공개 결과에는 cash가 없다.
- ExecutionCostAssessment.intervals_json: 전송 전 상태 시각과 양수 체결 조회 응답 수신
  시각·주문번호·종목·누적 체결 수량. 별도 구간 지문으로 묶으며 생성 실패 시 빈 구간이다.
  assess_interval_volume은 제공된 완결 봉에 대한 보수적인 구간 수량 검사 결과만 반환한다.
  원본 봉의 계좌/연구 출처 인증과 전체 실행 동등성/운영 승격을 제공하지 않는다.

- ExecutionCostAssessment는 동일 계좌/전략/실행 설정/기간의 원본 대조 계산 지문,
  개별 산술 조건, 오류, 미제공 모델 증명을 불변 값으로 보유한다. 공개 값에 원본 금액이나
  계좌 번호는 없다. 날짜 연결/실제 체결 시각/모델 거래량 증명은 현재 미제공이며
  execution_parity_verified는 false다. 운영 승인 참조가 일치해도 이를 true로 바꾸지 않는다.

- KIS 프로그램의 quote_feed는 단일 계좌 시세 연결의 전략5종목 전용 뷰다.
  관측 변환기는 같은 연결의 전체 평가 뷰를 읽는다. 물리 웹소켓은 하나다.
  거래소 탐색의 REST Quote는 구독 주소 결정에만 사용한다. 가격은 원본 발생시각이
  있는 SourceQuote만 반환하며 종료 시 비운다. baseline 지문이 구독 대상도 묶는다.

- AccountHistory는 계좌 해시, 관측 배치 순번, 시작/종료 시각, COMPLETE/FAILED,
  인증 제외 응답 데이터, 조회 조건, 실행 장부 전후 건수/최종 순번, 이전/현재 해시를 저장한다.
  순번은 로컬 관측 순서일 뿐 증권사 거래의 연속 번호가 아니다. 첫 관측을 보존하지만
  검증된 시작 순현금으로 자동 승격하지 않는다. 실행 장부의 계좌 소속도 별도 확인 대상이다.

- 시작 구성의 runtime_digest는 실제 장부와 중지 경로, 허용목록, 위험 한도, 기존 보유
  기준표를 정규화해 묶는다. 서버 운영 승인과 매 진입 검사에서 같은 구성을 요구한다.
  first fill-sync 이전 인증 갱신을 통해 라우터와 주문 권한의 토큰을 일치시킨다.

- ExecutionQualification은 내부 재계산으로 선택한 ResearchSelection, 계좌 해시,
  확정 범위 내 자본, 등록 원본 지문, 완결 관찰일 수를 보관한다. 생성과 실행 승인은
  별개다. 호출마다 현재 소스 지문과 별도 서버 운영 승인 파일을 검사한다. 승인 파일의
  검토 지문은 운영자가 어떤 자료를 검토했는지 가리키며 실제 체결 동등성 검사를 대체하지 않는다.

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
  기존 Observation으로 변환한다. 전체 페이지·계좌 범위·현금 합산 검증은 bool true,
  unverified_assets는 빈 dict여야 한다. execution_cash/nav는 USD 숫자 문자열이고
  구매가능 금액·사용자 승인으로 대체하지 않는다. 이 모델은 증명 발급기가 아니다.
  기본 verified_report 경로는 nav_verified=true를 요구한다. 명시적인
  net_cash_and_listed_equities 경로는 부채/미결제 등을 포함한 순현금 net_cash와
  전체 보유×가격을 더해 nav를 만든다. 보고 nav와 nav_verified는 사용하지 않는다.
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

CostInputComparison은 status, scope=SUPPLIED_BROKER_REPORTS, 대응 주문/조회 주문/
명세 행 수, 고정 issues, report_totals_match를 가진다. 실제 체결이 있는 조회 주문의
ID를 로컬 주문과 대조하며 명세 합계는 종목/방향별 수량/거래금액이다. 같은 명세에 여러
주문이 합쳐져도 per_order_fees_verified는 false다. 계좌 현금·정식 체결 자격·조회 기간의
완전성·DB 계좌 소속을 증명하지 않으며 실제 입력의 승인 대신 사용하지 않는다.

SettlementAudit는 status(MATCH/MISMATCH/NO_TRANSACTIONS), 행/일치/불일치/통화 수,
arithmetic_verified, 비공개 불일치 행 위치와 currency_totals를 가진다. 통화별 합계는
gross_buy/gross_sell/domestic_fee/foreign_fee/net_settlement이며 순정산은 매도 정산액
합계에서 매수 정산액 합계를 뺀 값이다. 빈 명세/한 행이라도 불일치하면 합계는 None이다.
공개 출력은 판정/건수만 포함하며 계좌 현금·정식 체결 비용 검증은 계속 별도다.

새 FILL 감사는 timestamp_basis(OBSERVED/PROVIDED_EXECUTION/UNSPECIFIED)와
observed_at_utc를 기록한다. UNSPECIFIED는 기존 생성기의 기본값이며 기존 저장된 JSON에
필드가 없는 경우도 미확인이다. OBSERVED의 executed_at_utc는 장부 기록 호환용 관측 시각이다.
PROVIDED_EXECUTION도 입력 시각의 출처 구분이며 별도 실제 체결 증명으로 자동 승격하지 않는다.
기존 fills/감사 행은 변경하지 않고 새 체결에만 출처를 추가한다.

TransactionReport는 등록일 구간, 요청 시장, 수집 시작/완료 시각, 페이지 수,
원본 거래 행(source_rows), 정규화한 거래 행과 페이지별 요약 행을 보존한다. 거래 행은 trad_dt/sttl_dt,
pdno/crcy_cd/sll_buy_dvsn_cd, ccld_qty/tr_frcr_amt2/frcr_excc_amt_1/
dmst_frcr_fee1/frcr_fee1이며 금액/수량은 정확한 소수 문자열이다. 각 페이지의 요약은
중복될 수 있어 합산하지 않는다. pagination_complete는 요청 범위의 페이지 끝을 뜻하며
계좌 전체·현금·개별 체결 비용의 검증을 뜻하지 않는다. 공개 보고서는 행/페이지 수만 낸다.

StrategyExitIntent는 기존 intraday_execution_events의 STRATEGY_EXIT_REQUESTED 사건이다.
claim_id는 실행 지문 접두사+종목+해당 보유 회차 첫 매수 f.seq에 묶이고 payload는
symbol/buy_fill_seq/limit이다. 보유가0이 된 이후 다음 매수는 새 회차이므로 과거 의도가
적용되지 않는다. 원본 사건은 갱신/삭제하지 않는다. 현재 회차 중복·잘못된 값은 거절하며
사용자 중지/마감/손실 정리는 별도 기존 경로를 쓴다.

CashLedger는 내부 공급자의 USD 순현금 opening/closing 스냅샷과 원본 events다.
각 스냅샷은 원본 sequence, 시간대 포함 at, net_cash를 갖는다. 사건은 고유 id,
원본 sequence/at/currency/kind와 net_cash_delta/net_cash_after를 보존한다.
명세 정산에 포함된 비용을 추가 FEE로 중복 생성하지 않는다. 이 값의 산술 일치는
원본 계좌 범위 인증이 아니며 검증 플래그를 발급하지 않는다.

ArchiveReview는 실제 session_count, required_sessions(756), missing_sessions,
missing_calendar_sessions, incomplete_archive_count, provider, synthetic,
dataset_fingerprint, 기존177 decision으로 구성한다. observation_type은
HISTORICAL_RESEARCH이며 live_eligible=false, orders_submitted=0이다.
합성 여부·부분 시장 수정 정책을 원본에서 보존하고 합성 또는 누락 자료를 연구 합격으로
바꾸지 않는다. source.json의 archives에는 날짜별 원본/manifest 지문을 남긴다.
