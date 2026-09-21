# 실행
코드/계약 커밋 뒤 `uv run python scripts/noise_band_probe.py develop --bars-dir <개발폴더> --manifest <고정manifest> --output-dir <새폴더>`.
`uv run python scripts/noise_band_probe.py verify --bars-dir <동일폴더> --manifest <동일manifest> --evidence <결과폴더>`로 재계산한다.
다른 manifest는 가격 파일을 열기 전 거부한다. 덮어쓰기·confirm·주문 명령은 없다.
개발 통과는 자금/주문 허용이 아니다.
