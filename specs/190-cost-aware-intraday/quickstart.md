# 검증 순서

개발 및 확인 CLI와 독립 재생 검사기를 구현했다. 실제 개발6후보는 모두 탈락했으므로
현재 실제 확인 실행은 자료를 열기 전에 거부하는 것이 정상이다.

1. `cost_aware_intraday_probe.py develop --bars-dir DIR --manifest FILE --preregistration FILE --output-dir NEW_DIR`
   개발 전용 입력으로만6후보 평가. 출력이 존재하면 거부한다.
2. 독립 검사로 개발 입력·선택·장부 재구성. 전부 탈락하면 해당 가설을 종료한다.
3. `cost_aware_intraday_probe.py confirm --development DIR --development-bars-dir DIR --development-manifest FILE --bars-dir HOLDOUT --manifest FILE --preregistration FILE --output-dir NEW_DIR`
   개발 지문을 검증한 뒤에만 확인 파일을 연다. 기간별 결과 확인 후 다시 선택하지 않는다.
4. `cost_aware_intraday_evidence_gate.py develop --evidence RESULT_DIR --bars-dir DIR --manifest FILE`
   원본부터 개발 결과와 장부를 다시 생성해 정확히 대조한다. confirm 검사는 위3번의
   개발 입력 인자와 `--evidence CONFIRM_RESULT_DIR`를 추가한다.

실제 실행은 `uv run python scripts/` 뒤에 해당 파일과 인자를 붙인다. 출력 경로는 항상
존재하지 않는 새 디렉터리여야 한다. 코드·계약 변경은 커밋해야 실행할 수 있다.
독립 검사는 현재 코드로 원본을 재생하여 기록된 결과를 재현하는 검사이며 별도 체결 모델로
시장 실행 동등성을 증명하는 검사는 아니다. 기록된 코드 커밋은 현재HEAD의 조상인지 확인한다.

테스트: `uv run pytest tests/unit/test_cost_aware_intraday.py tests/integration/test_cost_aware_intraday_cli.py`.
출시 전 전체 pytest/ruff·하네스·HANDOFF 검사 필수.
