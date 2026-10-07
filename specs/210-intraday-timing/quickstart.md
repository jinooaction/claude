# 재현 절차

짧은 합성: `uv run pytest tests/unit/test_intraday_timing.py -q`.
린트: `uv run ruff check src tests`.
전체 원격: 기존 고정 requirements의 pytest XML, timing62/receipt56/bridge40/CLI29 무생략과 린트 확인.
장외 반영 뒤 기존 intraday-paper-status 워크플로 한 번과 원래JSON artifact 시각/크기/SHA를 대조한다.
배포 전 timing 없는 영수증을 시각 확인 완료로 주장하지 않는다.
