# 원격 연구 취득 계약

`uv run python scripts/hf_research_ingest.py --history HISTORY.json --previous-state STATE.json --output NEW_DIR`

- history는 GitHub 이력 조회 단계에서 생성한다. 이전 실행이 없다면 previous-state는 없어도 된다.
- 키 입력은 자료 단계의 `HF_DATA_API_KEY`뿐이다. CLI 인수/파일/로그로 전달하지 않는다.
- 작업은 수동 호출만 가능하고 URL/종목/실거래 입력은 없다.
- 종료 코드: 0=두 원본 검증 완료, 3=접근 불가·키 부재·부분 취득·차단, 2=저장/계약 거부.
- 항상 결과 코드만 출력한다. 응답/헤더/예외/키/이메일을 출력하지 않는다.
- `circuit-state.json`은 별도 작은 artifact에 보존하며 원본은 검증 완료 파일과 manifest만
  업로드한다. 미완료 `.partial` 파일은 실패 시 제거하고 취소 시에도 업로드 대상에서 제외한다.
- 단순 목록 성공은 두 종목 원본 취득, 과거 종목 구성, 전략 수익성, KIS 호환성을 뜻하지 않는다.
