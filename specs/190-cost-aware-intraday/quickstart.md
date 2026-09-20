# 검증 순서

아래 명령은 구현 예정 계약이다. 아직 실행 가능한 CLI라고 주장하지 않는다.

1. `cost_aware_intraday_probe.py develop --bars-dir DIR --manifest FILE --preregistration FILE --output-dir NEW_DIR`
   개발 전용 입력으로만6후보 평가. 출력이 존재하면 거부한다.
2. 독립 검사로 개발 입력·선택·장부 재구성. 전부 탈락하면 해당 가설을 종료한다.
3. `cost_aware_intraday_probe.py confirm --development DIR --development-bars-dir DIR --development-manifest FILE --bars-dir HOLDOUT --manifest FILE --preregistration FILE --output-dir NEW_DIR`
   개발 지문을 검증한 뒤에만 확인 파일을 연다. 기간별 결과 확인 후 다시 선택하지 않는다.
4. `cost_aware_intraday_evidence_gate.py`로 원본부터 독립 재생/장부 대사를 확인한다.

테스트: `uv run pytest tests/unit/test_cost_aware_intraday.py tests/integration/test_cost_aware_intraday_cli.py`.
출시 전 전체 pytest/ruff·하네스·HANDOFF 검사 필수.
