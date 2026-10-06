# 검증 절차

1. Mac의짧은합성: `uv run pytest tests/unit/test_intraday_diagnostic_receipt.py -q`.
2. 원격PR의전체pytest/린트/XML에서새반례무생략을확인한다.
3. 정확검토코드확인뒤기존intraday-paper-status.yml을해당ref로한번읽기전용실행한다.
4. 실제artifact metadata/ZIP전체SHA/JSONSHA/관측·생산SHA와모의범위를대조한다. 가린로그숫자를보충하지않는다.
5. 최신본문품질·merge가능상태를확인해merge방식병합한다. 서버반영은별도관측한다.
