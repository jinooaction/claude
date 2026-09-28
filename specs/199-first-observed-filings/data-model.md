# 자료 계약

- Scope: schema_version=1, 고정 CIK 배열, form 배열, 한도. 추가 필드·중복·잘못된 CIK 거부.
- Blob: 원본 수신 바이트, SHA256 파일명. 기존 파일은 읽어 지문 확인하며 절대 재작성하지 않는다.
- Observation: UUID, CIK, accession, source_kind(listing/primary), URL, blob_sha256,
  requested_at/received_at/verified_at UTC, source_claims(접수일 등). 시각 순서와 URL/CIK 일치 필수.
- Run: 고유run_id, source_commit, config_sha256, started/ended UTC, observations 목록,
  failures 목록, coverage(관측/실패/한도생략), previous_run_sha256, circuit 상태.
  수집기 failures는 회사·목록/본문 구분·접수번호·고정오류코드를 남기며 예외원문/헤더는 제외한다.
  failed는 재시도 중 실패도 포함한 실패기록 수다. skipped는 받은 최근 목록에서
  본문 한도로 제외한 개수이며, 목록을 받지 못했거나 과거 추가목록을 읽지 않은 범위는
  전체성 unknown이다. 본문 이름/CIK/서식 검사는 최소 동일성 검사이고 실적 의미 검토가 아니다.
- Commit marker: 원문/관측/manifest 검증을 마친 뒤의 finalized_at. 조회 가능 시각은
  관측verified_at과finalized_at 중 늦은 값이다. 원격 게시 시각/다른 소비자 수신은 별도이며 자동 추정하지 않는다.
- Query: 기준UTC 전에 검증 완료된 원문 버전만 반환. 관측되지 않은 범위/수집만 완료된 상태를 함께 표시.
- Export: 명시적으로 선택한 primary 원문을195 입력용 파일로 복사하되 사건 의미/종목 연결은 자동 생성하지 않는다.

저장 중 실패한 임시 파일은 완료run이 아니다. 완료manifest가 연결하지 않는 blob/영수증은 조회에서 제외한다.
한 run은 임시 파일에서 원문/영수증을 검증하고 manifest를 마지막에 게시한다.
구현은 각 대상 디렉터리의 임시 파일을 fsync한 뒤 배타적 hard-link로 게시하며,
manifest와 finalized_at을 하나의 runs/<run_id>.json 완료 봉투로 마지막에 게시한다.
따라서 두 파일 사이의 중간 상태는 없다. 이전 연결은 완료 봉투 전체 바이트의SHA256이다.
검증 지문은 원격의 추가전용 기록과 함께 사용하며 전체 이력을 통째로 재작성한 공격을
지문만으로 인증한다고 주장하지 않는다. 수집/발행 실행은 단일 작성자로 직렬화한다.
중복run id는 거부한다. 이전run/원문 지문 불일치, symlink, 경로 이탈, 불완전manifest를 거부한다.
run 연결이 갈라지면 자동으로 유리한 경로를 고르지 않는다. 현재관측 성공은 과거 전체성 보장이 아니다.
새run 시작은 이전 완료run보다 이르지 않아야 한다. 속도·재시도·실행 한도는 monotonic 시간으로 검사한다.
완료run에 속하지 않는 파일을 날짜만 보고 조회하지 않는다. 원격발행 전 기존파일의 변경/삭제0건을 확인한다.
복구artifact는90일 보존하며 실제 원격branch에 게시되기 전에는 영구저장 완료라고 표시하지 않는다.
195 export의 영수증 참조는 별도 metadata로 남긴다.195의 시각 필드에주입하지 않으며,
같은 원문을 새195문서로import할 때 기존문서ID와 겹치지 않는 명시적ID를 사용한다.
