# 단타 실행기 검증

키 값은 채팅·인수·저장소에 넣지 않는다. `collect --help`, `paper --help`, `run --help`
로 명령 계약을 확인한다. 실제 계정 환경이 없으면 접근 실패를 정상적으로 표시한다.
자료를 받은 뒤 collect 결과 디렉터리를 기존 Spec177 연구 탐침 또는 paper에 넣는다.
`run`은 지속 실행용이며 운영 서비스에 자동 설치되는 명령은 아니다.

```sh
uv run python scripts/intraday_runtime.py status --state data/intraday-paper.db
uv run pytest tests/unit/test_intraday_data.py tests/unit/test_intraday_runtime.py tests/integration/test_intraday_runtime_cli.py
```

진단 모의 손익은 실제 체결도, 합격한 전진 관찰도 아니다. 계정·자료 검증 전 실제 운용
성공으로 표시하지 않는다. 실주문 경로는 아직 별도 구현/승격 관문으로 남는다.
