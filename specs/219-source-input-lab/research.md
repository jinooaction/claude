# 판단 근거
- 결정: 218의 전체 저장소 원본 확인을 먼저 비실행 lab으로 구현. 216 Docker의 독립 이미지와 합치기 전 입력 변조 차단을 검증한다.
- 근거: 원래 Git/loader/native 출처가 고정되지 않은 상태에서 실제 후보를 이미지로 옮기면 218 계약을 위반한다. 새 단일 초기 commit의 고정 내용만 생성하여 Git 명령 실행 전 전체 .git 기대 바이트를 비교한다.
- 대안: mutable production checkout 검사나 실제 .git 복제는 비밀/역사 반입과 설정 실행 위험 때문에 제외. Git 없는 HEAD 모조 응답도 제외.
- 공식 근거: [Git 환경/설정](https://git-scm.com/docs/git), [ls-files 인덱스 표기](https://git-scm.com/docs/git-ls-files), [cat-file 원래 객체](https://git-scm.com/docs/git-cat-file). 인덱스 상태만으로 작업 파일 원본 일치를 증명하지 않는다.
- GitHub runner의 /usr/bin/git 파일 지문을 관측하지만 공급망 인증으로 간주하지 않는다. 전이/native·이미지 내부 실행은 미평가다.
- 기존 읽은 경로: scripts/intraday_runtime_isolation_lab.py, specs/218-source-installation-contract/contracts/source-installation.md, execution/intraday_registration.py 및 forward.py(기존 계약 유지).
- 연구 전략은 T013 미완료, 정식 전진 T014 미완료이며 이 lab은 둘을 대신하지 않는다.

