# Quickstart

로컬에서는 합성 자료 반례만 검사한다:
`uv run pytest tests/unit/test_public_minute.py tests/integration/test_public_minute_pilot.py -q`.

실제 자료는 검토된 PR SHA를 PUBLIC_MINUTE_SOURCE_SHA 변수에 등록하고 PR의 원격
public-minute-pilot 실행을 확인한다. 같은 SHA의 release가 있으면 재시작하지 않는다.
report.json의 전체지문·품질·보관을 각각 확인하고 가격 원본은 출력/공개 업로드하지 않는다.
큰 파일/전체 회귀는 맥북에서 실행하지 않는다.

출처/조정/당시 구성은 미확인이다. 자료 취득 성공 뒤에도 신규 가설 사전등록·운용 연결·
독립 확인·같은 후보60세션·체결 동등성/실제 운영 증거가 별도로 필요하다.
SEC 연락정보와 HF 인증 키는 이 익명 수집의 입력이 아니다.
