# 실행 순서

연구 명령 구현 완료. 실제30파일 검증과 전체회귀를 통과하기 전 출시 완료로 보지 않는다.
1.30원본지문과2014-03-01~2020-03-06범위의193형식CSV manifest를준비한다.
2. contracts/preregistration.json완성·검토·커밋후지문을고정한다.
3. uv run pytest tests/unit/test_sparse_opening_research.py tests/integration/test_sparse_opening_research_cli.py
4. uv run python scripts/sparse_opening_research.py replay --manifest PATH --output NEW_DIR
5. uv run python scripts/sparse_opening_research.py verify --result NEW_DIR
6. 전체pytest/ruff/하네스/인계검사후출시한다. 실제주문명령은없다.
