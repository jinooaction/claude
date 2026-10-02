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
성공으로 표시하지 않는다. KIS 실주문 구현과 운영자 명령은182/184에 있고 실제
실거래 자격·승격 관문은 별도다. 이 진단 보고서가 그 준비 여부를 판정하지 않는다.

서버 설치는 기존 배포의 `sync-units` 경로를 사용한다. 변경된 helper가 설치되기 전
첫 배포가 구버전 sync를 사용했다면 새 배포의 유닛 동기화를 한 번 더 실행해야 한다.
상태는 `Intraday paper service status (read-only)` workflow로 확인한다.
정상 휴장은 WAIT_SESSION이며 원본 저장과 timer 활성은 별도 증거다.
되돌림: 단타 전용 timer를 비활성화하고 진행 중 단회 종료를 기다린다. 데이터는 보존한다.

service-status1.1은 scope=DIAGNOSTIC_PAPER_SERVICE,
program_readiness=NOT_ASSESSED다. blockers의 미평가는 이 경로가 검사하지 않았다는
뜻이다. 정확한 옛1.0은원본수정없이보기로변환하며source_schema_version=1.0을 표시한다.
상태표시 코드 변경도 기존FR013에 따라 새 진단 디렉터리를 고르므로 옛 장부를
이동/수정하거나 전진 자격을 이어받지 않는다. 전체181 T013~T016은 계속 미완료다.
