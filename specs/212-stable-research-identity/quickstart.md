# 확인 경로

Mac에서는 새 합성 반례와 작은 기존 archive/selection/registration 시험만 수행한다.
`uv run pytest -q tests/unit/test_intraday_research_identity.py tests/unit/test_intraday_selection.py tests/unit/test_intraday_registration.py`
전체 검사는 기존 고정 요구파일을 사용하는 GitHub stable-research-identity-checks에서 수행하며 실제 가격 재생/미개봉495세션 개봉은 없다. 기존198 workflow는 가격재생을 포함하므로 새 검사를 연결하지 않는다.
`uv run ruff check src tests`, 하네스14/14, HANDOFF 사실, PR본문과 원래XML을 확인한다.
새 기능의 실제 서버 반영은 정상 배포 감사로 확인하되 통과전략/생산체결 완료로 확대하지 않는다.
