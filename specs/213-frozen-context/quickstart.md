# 빠른 검증

실제 후보 환경이 없으므로 서버나 원래 계좌로 실행하지 않는다.
`uv run --no-sync pytest -q tests/unit/test_intraday_frozen_context.py`는 임시 합성 저장소/가상환경 모양의 작은 디렉터리만 사용한다.
`uv run --no-sync ruff check scripts/intraday_frozen_context.py tests/unit/test_intraday_frozen_context.py`.
전체 검사는 PR의 Frozen context regression에서 수행하고 정확 HEAD/XML/필수반례/린트를 확인한다.
PASS는 실제 Python환경 설치/전진/인증/60세션/실체결 증거가 아니며 실제 키를 사용하지 않는다.
