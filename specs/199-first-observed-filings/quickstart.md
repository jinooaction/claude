# 검증 순서

1. 가짜HTTP와 시계로 성공/정정/실패/차단/시계역행/큰응답/잘못된URL을 검사한다.
2. 첫run·실패run·정정run 뒤 과거query와 원문 바이트 불변을 확인한다.
3. 임시파일/중복run/변조/저장충돌을 거부하는지 확인한다.
4. 원격에서 고정 회사 원문 수집을2회 실행하고 최초관측 기록과 양쪽run을 재검증한다.
5. 선택 원문을export하고195에서 검토된 주장으로import/query하는 연결을 확인한다.
6. PR 최신 커밋의 원격 전체pytest·ruff, 하네스·인계·PR품질을 통과시킨다.
7. 병합·정기수집 실제 첫 실행·추가전용 원격보존을 확인하고 인계한다.

로컬 Mac의 화면/입력 조작과 무거운 검사는 하지 않는다. 원격 접근이 실패하면
응답 증거를 남기며 차단을 우회하거나 완료로 처리하지 않는다.

## 기존195 도구 연결

`filing_observations.py export`의 출력은 source.bin과 metadata.json이다.
195 입력 documents에는 새 명시적 id, path=source.bin, 원문 sha256과 url을 넣는다.
수집 metadata는 별도 출처 기록으로 보존한다. observed_start/observed_end/verified_at을
195 입력에 복사하지 않는다.195 import가 현재 읽기·검토 완료시각을 기록한다.
events는 실제 원문을 검토한 주장·근거 인용으로 따로 작성하며8-K라는 이유만으로 만들지 않는다.
같은원문이라도 기존195묶음에 추가할 때 문서ID를 재사용하면 거부된다. 정정은 새문서ID와
새사건ID, 기존사건을 가리키는 supersedes를 사용한다. 과거조회는 기존버전을 유지한다.

자동 검사 `test_export_to_existing195_preserves_current_review_time_and_document_identity`는
이 연결을 합성원문으로 재현한다. 실제 SEC원문 검토, 수익성, 역사전체성, 거래자격의 증거는 아니다.
