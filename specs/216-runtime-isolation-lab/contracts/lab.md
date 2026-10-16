# CLI 계약
`python scripts/intraday_runtime_isolation_lab.py --output <새 보고서 경로>`.
Linux/GITHUB_ACTIONS=true/RUNNER_OS=Linux 외에는 Docker를 찾거나 호출하기 전에 실패한다.
사용자 context/DOCKER_HOST를 쓰지 않고 고정 Unix socket·빈 임시 config만 쓴다.
출력은 합성 JSON 한 개, 오류는 LAB_FAILED 고정 코드다. 임의 환경·경로·명령 전문을 출력하지 않는다.
기존 report overwrite0. 임시 생성 container/image만 finally 정리하며 전체 prune0.
fixture에 .env/키/장부/실제 source0, Dockerfile은 고정 FROM+COPY만 사용한다.
일반 시작명령은 python -I -S -B /candidate/entry.py, user65532:65532/cwd /candidate/명시 환경만 허용한다.
검사 대상 필드는 필수이며 bool과 int를 동일시하지 않는다. 원래 Docker의 다른 필드는 존재할 수 있다.
Docker의 생략형 HostConfig.Mounts/Tmpfs에 한해 누락/null/정확한 빈 자료형을 허용하며 비어 있지 않은 값은 거절한다.
Linux 환경변수는 첫 =만 나누고 중복 이름을 먼저 거절한 뒤 정확한 이름·값을 비교한다. Docker 병합 목록 순서는 원래 증거에 보존하되 비교 대상에서 제외한다.
보고서 실제 파일은32KiB 이하이며 압축 전 직렬화 크기를 확인한다.
고정 site 양성·단일 임시 파일 ro bind 부정 대조군 외 임의 allow/bypass 옵션0.
actual_candidate_environment_installed/runtime_closure_verified/continuous_immutability_verified/registration_verified/live_eligible/promotion_allowed=false.
기반 진위/전체 native·전이의존성/host kernel·mount 교체/검사 후 관리자 변경/정확 Git ROOT·HEAD/실제 등록·수집은 미평가다.
