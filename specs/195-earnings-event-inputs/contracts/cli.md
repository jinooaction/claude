# CLI contract

`uv run python scripts/earnings_event_inputs.py import --input INPUT.json --output NEW_DIRECTORY`

입력 상대 경로는 INPUT 부모 기준. 동일 바이트로 지문·인용문을 확인한다.
기존 디렉터리 거부. local_observation_only=true, source_authenticity_verified=false 고정.
현재 프로그램 시각으로만 영수증을 만들고 과거 시각 지정 옵션은 제공하지 않는다.
이전 묶음이 있으면 `--previous OLD_DIRECTORY`로 검증 후 기존 원문/버전을 포함한 새 묶음을 만든다.
기존 문서/id 중복 거부. 이전 묶음을 수정하지 않는다. 이전 묶음 SHA256을 기록한다.

`uv run python scripts/earnings_event_inputs.py query --bundle DIRECTORY --as-of UTC_TIME --output NEW.json`

지문·형식·전체 버전 연결 검사 후 기준 시점 이하인 버전만 출력한다.
관측되지 않은 미래 사건의 내용/개수/종류를 과거 조회 결과에 노출하지 않는다.
결과는 observation_available인 수동 분류 입력이다. source_authenticity_verified=false,
live_eligible=false, strategy_admitted=false, orders_submitted=0.
묶음 전체 지문은 감사 목적으로 출력하며 미래 데이터 추가 시 지문은 달라질 수 있다.
형식/원본/버전 이상은 종료 코드 2. 기존 출력은 보존한다.
