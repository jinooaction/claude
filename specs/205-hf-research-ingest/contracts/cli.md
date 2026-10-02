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

## 오프라인 장기 보관

`uv run python scripts/hf_research_retain.py --source VERIFIED_ARTIFACT_DIR --output NEW_ARCHIVE_DIR`

- 입력은 수집 작업에서 받은 목록·두 원본·manifest다. 저장 결과 `COMPLETE`와 코드 지문을 요구한다.
- 출력의 부모 폴더는 미리 존재해야 하며 모든 경로는 실제 절대 경로를 사용한다.
  심볼릭 링크와 기존 출력 폴더는 거부한다. 기존 자료/보관본은 덮어쓰지 않는다.
- 파일을 `NEW_ARCHIVE_DIR/source/`에 복사·지문 재검증·저장 동기화한다.
  `retention.json`을 마지막에 쓰며 실패 시 이번에 만든 새 폴더만 정리한다.
- 영수증은 보관 시각·코드 지문·입력/보관 manifest 지문·원본 영수증과 연구 경계를 가진다.
  수집 시각과 파일 지문은 바꾸지 않는다. 보관 manifest는 검증된 JSON을 정규화한 사본이다.
- 종료 0은 `RETAINED`, 종료 2는 `RETENTION_REFUSED`다. 예외·경로·키·연락처는 출력하지 않는다.
- 네트워크나 비밀 환경을 사용하지 않는다. 무결성은 인증 취득이나 전략/실거래 적격의 증거가 아니다.
  실제 취득 완료는 해당 원격 실행과 원본을 별도로 대조한다.
