# Research: 환경 전 범위와 실행 조건
2026-10-15. 아래는 공식 문서와 고정 main9e 코드의 설계 조사이며 실제 서버 환경 확인이 아니다.

## Decision / Rationale / Alternatives
선택: 기반 실행파일·stdlib/native를 포함한 정확 OCI 이미지와 별도 runtime config/host 상태를 참조 형태로 삼는다.
이유: 214 폴더 밖 기반을 빠뜨리지 않고 설치 내용과 시작 설정을 별도 지문으로 기록할 수 있다.
대안: 복사 venv만 고정하면 기반 Python/home/외부 표준라이브러리가 남는다.
main 배포 중단·문서SHA예외·자동 재서명은 기존 운영/정확 등록 경계를 약화하므로 쓰지 않는다.
아직 이미지 생성·컨테이너 설치·후보 기동 또는 이 선택의 actual 서버 지원을 확인한 것은 없다.

## 1차 자료와 한계
- [Python3.11 명령줄](https://docs.python.org/3.11/using/cmdline.html): -I는 -E/-P/-s를 포함한다. -S는 자동 site 처리를 막는 별도 옵션이다.
- [Python3.11 site](https://docs.python.org/3.11/library/site.html): 설치 경로의 .pth 실행문과 sitecustomize가 기동에 관여하며 명시적 site.main/addsitedir 호출은 별도 고려가 필요하다.
- [Python3.11 venv](https://docs.python.org/3.11/library/venv.html), [검색경로](https://docs.python.org/3.11/library/sys_path_init.html): venv는 기반 Python 설치 위에서 동작하며 base prefix/stdlib·확장모듈이 따로 있다. Python3.11의 -S 기동과 prefix는 실제 목표 버전에서 검증해야 한다.
- [OCI image1.1.0 descriptor](https://github.com/opencontainers/image-spec/blob/v1.1.0/descriptor.md): digest는 지목한 바이트의 내용 지문이며 생성자 신뢰를 자동 증명하지 않는다.
- [OCI image1.1.0 conversion](https://github.com/opencontainers/image-spec/blob/v1.1.0/conversion.md): 이미지 기본 설정 외 입력이 runtime 설정을 덮거나 결합할 수 있다.
- [OCI runtime1.2.1 config](https://github.com/opencontainers/runtime-spec/blob/v1.2.1/config.md): root.readonly와 추가 mount·hook 설정은 구분해야 한다.
- [OCI runtime1.2.1 Linux](https://github.com/opencontainers/runtime-spec/blob/v1.2.1/config-linux.md): 커널 namespace 등 host 기반과 실제 구성은 이미지 바이트만으로 같다고 할 수 없다.

추론: 같은 image digest도 다른 mount·args·env·hooks·host와 기동되면 같은 고정 실행 환경이라는 결론을 낼 수 없다.
전체 설치물/기동/지속 불변/신뢰 연결을 각각 원래 증거로 묶는 계약이 필요하다. 공식 문서는 실제 서버 측 충족의 증거가 아니다.

## 기존 실제 호출부
src/auto_invest/execution/intraday_identity.py의 SOURCE_PATHS/source_identity는117개 소스·정적 입력을 묶는다.
intraday_qualification.py의 prepare_qualification은 모듈 ROOT에서 정확 현재 GitHEAD로 독립 연구를 선택하고 기존 등록/60세션·비용·계좌를 검증한다.
intraday_registration.py의 verify_registration은 기존 서버HMAC·정확 selection/preregistration 불일치를 거절한다.
deploy/auto-invest-intraday-paper.service는 /opt/auto-invest를 cwd/Python/소스로 쓰며 main 배포 경로와 같다.
따라서 이 경로를 후보의 고정 코드 경로로 겸용하지 않는 설계가 필요하다. ProtectSystem=strict만으로 다른 배포 주체의 쓰기를 막았다고 추론하지 않는다.
기존 collect_attested_kis/운영자 attest 옵션/forward 검증은 이미 있다. 진단의 PROOF_ABSENT는 이를 새로 만들어야 한다는 뜻이 아니다.

## 실제 입력의 미확인
서버 플랫폼/OCI 런타임/권한·마운트/기본 Python/설치물/독립 신뢰 입력/후보 전략·등록 모두 미평가다.
그 확인 전 자동 설치·기동·등록·권한 변경을 수행하는 fallback은 없다. 실제 통과 전략도 없다.
조사 검토의 열두 반례는 계약의 예상 결과이며 실행 통과 수치로 집계하지 않는다.
