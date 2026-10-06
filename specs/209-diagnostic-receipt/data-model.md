# 자료 계약

입력: 기존명령stdout64KiB이하, timer/service_result/production_commit각1회와마지막진단JSON.
JSON중복키/비정상수·가린값은거절한다. 필수범위1.1/DIAGNOSTIC_PAPER_SERVICE/NOT_ASSESSED,
기존status·identity·시각/age≤180·모의count정수·실주문0·정식전진0·자격거짓을검증한다.
출력은명시허용필드만: 원래관측/수집시각·scope·생산/관측지문·모의status/count·flags·blocker/halt코드·보관날짜/상태.
source_schema1.0은레거시producer로거절한다. last_bar는없거나UTC정렬/관측전닫힌5분봉이다.
원래stdout전문/미지필드/가격/계좌/키는출력없음. 모의quantity를실제계좌잔고로표시하지않는다.
captured_at은GitHub runner시계로서버관측시각보다앞설수없다. 게시/브로커체결시각의증명은아니다.
artifact전체ZIPSHA·허용필드JSONSHA는별도이며원래stdout전문의지문은출력하지않는다. 로그/추가전용출력파일을덮어쓰지않는다.
데이터베이스가아직없는WAIT_SESSION에서는모의count/halt필드부재를그대로보존한다. 값을0으로추정하지않는다.
