# Pilot contract

고정 주소 외 입력 URL을 받지 않는다. huggingface.co→us.aws.cdn.hf.co의 HTTPS만 허용,
userinfo/포트/다른 호스트/5회 이상 이동을 거절한다. 익명 요청, 환경 프록시/쿠키 미사용.
Content-Length/전체 크기/전체SHA256/Parquet을 확인한다. 403/404/지문 오류는 반복하지 않는다.
429/5xx/전송 장애만 총3시도, 2/4초 후 재시도. 각 응답은 제한 크기로 스트리밍,
1초 요청 간격, 전체15분 제한. 실패 시 일부 파일을 원본 확보로 인정하지 않는다.

schema는 timestamp TIMESTAMPTZ/open/high/low/close/volume DOUBLE/ticker VARCHAR.
정수분·시간대·뉴욕 고정 월·NULL/비정상/음수/기하·거래량 정수·종목시각중복을 검사한다.
정규장 밖 원본은 삭제하지 않는다. quality_accepted는 정규장 행이 있고 구조/가격/중복 오류가 없다는 뜻이다.
월 전체 완전성은 별도 regular_coverage_complete와 종목별 누락으로 보고하며 혼동하지 않는다.
정규장 완전성은 원본 전종목과 XNYS 실제 달력으로 보고한다.
현재 운용5ETF SPY/QQQ/IWM/TLT/GLD의 부재/완전 세션도 별도로 표시한다.
해당 원본에서 종목이 없는 것은 현재 KIS 허용목록과 동등하다는 뜻이 아니다.

실제 수집 job은 내부 owner+검토변수 PUBLIC_MINUTE_SOURCE_SHA==정확PRHEAD를 확인한다.
시도 전 research-207-public-minute-<SHA> release를 추가 생성한다. 이미 있으면 즉시 차단한다.
성공/실패 후 안전 보고서를 release에 추가한다. 원본은 별도 AES-GCM로 암호화하여 보관한다.
기존 자산 덮어쓰기/삭제/동일 코드 자동 재개 없음. 새로운 시도는 원인 해결·새 검토 소스가 필요하다.
보고서와 암호문은 실제 파일별 지문을 다시 대조해야 archive_complete로 인정한다.

검사 통과, 원본 확보, 암호화 완료, GitHub 업로드 확인은 네 단계다.
원본 합격은 미래 전략/제공자 승격을 허용하지 않는다. 최소36시도/최종495세션/운용117파일 유지.
