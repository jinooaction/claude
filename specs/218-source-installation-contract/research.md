# Research: 기존 구현과 추가 연결의 경계

## 확인한 원래 코드 — 기준 main69eb5f99
`src/auto_invest/execution/intraday_identity.py`: ROOT는 모듈 parents[3]이며 source_identity는
SOURCE_PATHS의 새 바이트/일반파일/단일 hardlink/내부 symlink/읽는 도중 변경을 검사한다.
전체 Git tree·lock·설치물·clean/detached를 검증하는 함수가 아니다.
`intraday_registration.py` register는 같은 방식의 ROOT에서 git rev-parse HEAD를 읽는다.
verify_registration은 서버 HMAC와 후보·제공자·연구/자료·정확 code_commit·사전등록 지문을 비교한다.
`intraday_qualification.py` prepare_qualification도 ROOT의 HEAD로 독립 연구를 선택한다.
이 함수들 자체가 shallow/외부 object 저장소/전체 dirty 상태를 검증한다고 주장하지 않는다.
215/216 계약과 새 독립 조사 역할의 읽기 결과를 맞췄다. 실제 등록·키 조회·후보 import·재생은 없다.

## 결정과 대안
1. **선택**: 원래 commit/tree, 기존 실행 소스 지문, 전체 파일 SHA, lock/install 입력, 설치 결과, 이미지 식별자를 병렬로 보존한다.
   **이유**: Git 식별자·바이트 지문·출처 인증은 서로 다른 역할이다. **제외**: tree 일치로 code_commit을 대체.
2. **선택**: 후보 ROOT 안에서 닫힌 독립 저장소, detached·clean과 전체 추적 파일 재비교.
   **이유**: 외부 main 갱신/인덱스 은폐/필터 변환을 별도로 차단해야 한다. **제외**: 운영 .git 통째 복사 또는 파일 archive만으로 저장소 충족.
3. **선택**: 후속 초기 합성은 자체 생성한 단일 초기 커밋 전체만 반입한다.
   **이유**: 실제 이력에는 현재 tree 밖의 비밀도 있을 수 있다. **제외**: 실제 이력의 비밀 미확인 상태에서 full clone을 안전하다고 간주.
4. **선택**: 설치 입력의 정확 바이트와 전체 전이 관계·플랫폼을 별도 고정한다.
   **이유**: lock 이름/버전/설치 RECORD 자기 보고는 독립 원본 인증이 아니다. **제외**: 실행 시 인덱스 재조회로 누락 자동 보충.
5. **선택**: 이번은 문서 계약만 완결하고 다음 구현에서 GitHub 합성 반례를 실행한다.
   **이유**: Git 실행파일·기반 native 및 설치기 입력까지 고정해야 하므로216의 기동 성공을 그대로 확대할 수 없다.

## 공식 문서 — 2026-10-16 UTC 읽기
- [Git clone 2.43.0](https://git-scm.com/docs/git-clone/2.43.0): local clone의 hardlink/공유 객체 의존, depth/filter와 복제 설정을 확인했다.
- [Git archive 2.43.0](https://git-scm.com/docs/git-archive/2.43.0): 파일 아카이브는 저장소의 동일성·기존 HEAD 호출을 자동 충족시키지 않는다.
- [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/): 모든 의존성의 pin/hash와 입력 제한의 역할을 확인했다.
위 문서는 설계 근거이며 서버 설치 파일·패키지 진위·지원 환경의 실제 시험 결과가 아니다.
Git 문서는 공식 저장소 v2.43.0의 작은 원문/전체SHA를 보존했다. 직접 HTML 취득403을 반복하지 않았다.
pip는 웹 도구의 원래 본문 관측 JSON을 보존한다. HTML 원본을 직접 취득했다고 주장하지 않는다.

## 남은 실제 증거
actual 후보 ROOT/완전한 Git 도구·Python/stdlib/native/전이 설치물/플랫폼·mount/지속 불변/독립 신뢰 입력은 미평가다.
등록·전진·권한에 연결하는 소비자0. 원래216의9시나리오/63합성 및 고정11자산을 재실행/변경하지 않는다.
