"""자동 룰 설계자.

운영자가 자연어 한 줄로 의도를 적으면 시스템이 룰 후보를 생성하고 검증
상태를 기록한다. spec 111 이후 design 경로는 PROPOSAL_ONLY이며 실거래
프로세스를 시작하지 않는다.

서브모듈은 후속 태스크에서 추가:
  - mutex (T010): design 명령 동시 실행 방지
  - prompt (T011): Claude system+user prompt 조립
  - validator (T012): 생성된 TOML 정적 검증
  - claude_client (T013): anthropic SDK 호출 + token usage 기록
  - verifier: 정적 검증 + 동적 증거 fail-closed 상태 산출
  - state (T015): design session 상태 머신
  - deploy: 후보 파일 저장 + legacy live-start 경계 오류
"""
