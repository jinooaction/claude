# 자료 구조

`CircuitState` 버전 1의 고정 범위는 `HF_RAW_PILOT_V1`이다. `catalogue`와 `raw` 각각
`failures`(0–3 정수), `blocked_until`(UTC 또는 null)을 가진다. 상태 파일은 비밀과 URL을
담지 않으며 4KiB 이하이고 완료된 실행에서만 다음 실행에 복원한다.

`HistoryProof`는 버전 1, 현재 `run_attempt`, `previous`(없음 또는 `id`/`status`/`updated_at`)
으로 구성한다. 실제 조회 성공 후 고정 workflow의 가장 최근 이전 실행만 사용한다.
이 증명은 연구 입력이며 실거래 권한 문서가 아니다.

`manifest.json`은 취득 결과 코드, 고정 출처, 파일별 bytes/SHA-256/rows, UTC 시각,
`returns_evaluated=false`, `historical_universe_verified=false`, `source_parity_verified=false`,
`live_eligible=false`, `orders_submitted=0`를 가진다. 공개 목록도 이력 전체의 종목 구성을
증명하지 않는다. 모든 파일이 검증된 경우에만 원본 취득 결과를 `COMPLETE`로 표시한다.

장기 보관은 새 폴더의 `source/`에 검증된 파일/manifest를 두고 마지막에 `retention.json`을
쓴다. 보관 영수증 버전1/범위 `HF_ARCHIVE_V1`은 UTC `archived_at`, `source_commit`,
`input_manifest_sha256`, `retained_manifest_sha256`, 원본 `files` 영수증과 연구 경계를 가진다.
입력 manifest의 바이트 지문과 정규화한 보관 manifest의 지문을 구별한다.
`RETAINED`는 보관 무결성만 의미하며 실제 HTTP/인증/전략 자격은 원격 증거가 필요하다.
