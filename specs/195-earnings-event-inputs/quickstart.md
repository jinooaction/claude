# Quickstart

1. 원문을 저장소 밖에 보존하고 documents의 원본 지문과 원문에서 확인한 사건 주장·인용을 작성한다.
2. `uv run python scripts/earnings_event_inputs.py import --input INPUT.json --output NEW_DIRECTORY`
3. `uv run python scripts/earnings_event_inputs.py query --bundle NEW_DIRECTORY --as-of 2014-01-24T00:00:00Z --output OLD_QUERY.json`
4. 현재 가져온 파일은 과거 조회에 0건이어야 한다. import 완료 이후 조회에서는 예정/실제 두 종류가 보여야 한다.
5. `uv run pytest tests/unit/test_earnings_event_inputs.py tests/integration/test_earnings_event_inputs_cli.py`

실제 원문 파일은 194 조사에서 확보한 자료를 쓴다. 외부 원문을 fixture로 커밋하지 않는다.
query 결과를 매매 신호로 연결하거나 과거 성과 검증에 소급해서 쓰지 않는다.
