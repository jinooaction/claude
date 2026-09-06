# 단타 실행기 검증

키 값은 채팅·인수·저장소에 넣지 않는다. `collect --help`, `paper --help`, `run --help`
로 명령 계약을 확인한다. 실제 계정 환경이 없으면 접근 실패를 정상적으로 표시한다.
자료를 받은 뒤 collect 결과 디렉터리를 기존 Spec177 연구 탐침 또는 paper에 넣는다.
`run`은 수동 진단 실행용이다. 후속 서버 연결은 별도 `service` 단회를 매분
호출하는 `auto-invest-intraday-paper.timer`로 설치한다.

```sh
uv run python scripts/intraday_runtime.py status --state data/intraday-paper.db
uv run pytest tests/unit/test_intraday_data.py tests/unit/test_intraday_runtime.py tests/integration/test_intraday_runtime_cli.py
```

진단 모의 손익은 실제 체결도, 합격한 전진 관찰도 아니다. 계정·자료 검증 전 실제 운용
성공으로 표시하지 않는다. 실주문 경로는 아직 별도 구현/승격 관문으로 남는다.

서버 설치는 기존 배포의 `sync-units` 경로를 사용한다. 변경된 helper가 설치되기 전
첫 배포가 구버전 sync를 사용했다면 새 배포의 유닛 동기화를 한 번 더 실행해야 한다.
상태는 `Intraday paper service status (read-only)` workflow로 확인한다.
정상 휴장은 WAIT_SESSION이며 원본 저장과 timer 활성은 별도 증거다.
되돌림: 단타 전용 timer를 비활성화하고 진행 중 단회 종료를 기다린다. 데이터는 보존한다.
