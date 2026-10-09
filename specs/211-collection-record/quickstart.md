# 재현 방법

Mac에서는 합성 파일만 사용해 `uv run pytest -q tests/unit/test_intraday_collection_record.py tests/unit/test_intraday_timing.py tests/unit/test_intraday_diagnostic_receipt.py`를 실행한다. 비밀 키·실제 가격 파일·계좌·큰 원본을 읽지 않는다.
전체 검사는 기존 intraday-paper-status GitHub Actions에서 고정 archive requirements와 pytest XML/린트를 확인한다. 신규 반례와 기존65/56/40/29는 건너뛰지 않는다.
하네스 strict·HANDOFF 사실·PR본문 품질·운용6파일 차이0을 확인한다. 정상 예약 반영 뒤 기존 읽기 전용 원래 safe JSON을 검증한다. 이미 실행된 진단은 재시작하지 않는다.
