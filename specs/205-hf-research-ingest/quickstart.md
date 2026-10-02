# 확인 순서

1. 관련 모의 검사: `uv run pytest tests/unit/test_hf_research_ingest.py`.
2. `uv run ruff check src tests scripts/hf_research_ingest.py`와 하네스/HANDOFF 사실 검사를 수행한다.
3. 전체 pytest는 GitHub의 연구 회귀 작업에서 수행한다. 맥북 화면과 큰 로컬 검사를 사용하지 않는다.
4. main에 수집 작업이 출시된 뒤 수동 실행한다. 현재 HF 키가 없으므로 공개 목록 결과와
   `MISSING_KEY`를 구별한다. 인증 파일이 없어도 목록 요청 실패를 숨기지 않는다.
5. 기존 무료 계정에서 발급한 키는 GitHub Actions의 `HF_DATA_API_KEY` 비밀 저장소에 넣는다.
   키를 채팅·커밋·CLI 인수로 보내지 않는다. 이후 새 수동 실행에서 실제 원본 지문을 검증한다.
6. 실패/취소 재실행은 이전 기록과 900초 차단을 확인한다. 같은 실행의 rerun은 거부된다.

되돌림은 수동 작업 실행 중단이다. 기존 원본/로그/거래 기능은 그대로 남으며 자동 수집 예약을
새로 만들지 않는다. 실제 두 파일 취득과 영구 보관은 증거를 확인한 뒤 별도로 완료 표시한다.
