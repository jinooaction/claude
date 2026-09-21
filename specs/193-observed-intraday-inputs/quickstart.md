# 검증 순서

구현된 연구 입력 도구의 검사 순서다. 전체 회귀·출시 상태는 results.md를 확인한다.
1. `uv run pytest tests/unit/test_observed_intraday_inputs.py tests/integration/test_observed_intraday_cli.py`
2. 실제 RTX/DD Raw를 지문 확인 후1분 CSV로 변환하고 source/adjustment/식별 미확인을 manifest에 보존한다.
3. `uv run python scripts/observed_intraday_probe.py --manifest <manifest.json> --output <new-report.json>`
4. 독립 달력 검사와1515일/1125·1323완전일/761·288누락분을 대조한다.
5. 전체pytest/ruff, 하네스, 인계 사실 검사 후 PR을 준비한다.

보고서가 성공해도 가격 연결 미확인과 전략 미검증을 유지한다.
