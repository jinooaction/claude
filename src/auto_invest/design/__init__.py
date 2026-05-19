"""자동 룰 설계자 (spec 010).

운영자가 자연어 한 줄로 의도를 적으면 시스템이 룰을 자동 생성·정적 검증·
paper-run으로 검증한 뒤 운영자 OK 후 라이브 시작.

서브모듈은 후속 태스크에서 추가:
  - mutex (T010): design 명령 동시 실행 방지
  - prompt (T011): Claude system+user prompt 조립
  - validator (T012): 생성된 TOML 정적 검증
  - claude_client (T013): anthropic SDK 호출 + token usage 기록
  - verifier (T014): 백테스트 stub + paper-run 트리거
  - state (T015): design session 상태 머신
  - deploy (T024): 운영자 OK + 라이브 자동 시작
"""
