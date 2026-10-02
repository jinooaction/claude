# 확인 순서

1. 관련 모의 검사: `uv run pytest tests/unit/test_hf_research_ingest.py`.
2. `uv run ruff check src tests scripts/hf_research_ingest.py`와 하네스/HANDOFF 사실 검사를 수행한다.
3. 전체 pytest는 GitHub의 연구 회귀 작업에서 수행한다. 맥북 화면과 큰 로컬 검사를 사용하지 않는다.
4. main에 수집 작업이 출시된 뒤 수동 실행한다. 현재 HF 키가 없으므로 공개 목록 결과와
   `MISSING_KEY`를 구별한다. 인증 파일이 없어도 목록 요청 실패를 숨기지 않는다.
5. 기존 무료 계정에서 발급한 키는 GitHub Actions의 `HF_DATA_API_KEY` 비밀 저장소에 넣는다.
   키를 채팅·커밋·CLI 인수로 보내지 않는다. 이후 새 수동 실행에서 실제 원본 지문을 검증한다.
6. 실패/취소 재실행은 이전 기록과 900초 차단을 확인한다. 같은 실행의 rerun은 거부된다.

기존 계정은 [공식 계정 페이지](https://hfdatalibrary.com/pages/account)에서 확인한다.
이메일 확인과 기관·국가·역할을 완료하고 무료 API 키를 얻는다.
[GitHub 비밀 등록](https://github.com/jinooaction/claude/settings/secrets/actions/new)에서
Name은`HF_DATA_API_KEY`, Secret은 실제 키로 등록한다. 새 가입이나 유료 구독은 필요 없다.
현재 키 등록은 미완료다. 공식 공개 목록의 별도 실제200/1391종목 확인을
main 작업 실행 또는 실제 인증 자료 취득으로 대체하지 않는다.

인증 두 원본의 원격 실행을 확인하면 `hf-research-<실행번호>-<시도번호>` 산출물을
별도 연구 폴더로 복구한 뒤 다음 명령으로 장기 보관한다. 출력 부모 폴더는 기존 연구
저장소이며 출력 자체는 새 폴더여야 한다. `data/` 또는 저장소 밖 폴더를 사용하고 가격
원본을 Git에 커밋하지 않는다.

```sh
uv run python scripts/hf_research_retain.py \
  --source /absolute/path/to/verified-artifact \
  --output /absolute/path/to/research-archive/new-source
```

종료 0과 `retention.json`의 입력/보관 manifest 지문을 실제 산출물에 대조한다.
원본의 출처·취득 실행 증거도 별도로 확인한다. 모의 자료에서 명령이 통과한 것만으로
실제 원본 확보를 완료 처리하지 않는다. 저장 실패/부분 자료는 종료 2이며 기존 자료를 보존한다.

되돌림은 수동 작업 실행 중단이다. 기존 원본/로그/거래 기능은 그대로 남으며 자동 수집 예약을
새로 만들지 않는다. 실제 두 파일 취득과 영구 보관은 증거를 확인한 뒤 별도로 완료 표시한다.
