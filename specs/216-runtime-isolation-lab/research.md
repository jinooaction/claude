# Research
- 결정: create→inspect→start. create는 시작하지 않으므로 불일치를 created 상태에서 거절한다. run 뒤 검사는 대체하지 못한다.
  [Docker create](https://docs.docker.com/reference/cli/docker/container/create/), [inspect](https://docs.docker.com/reference/cli/docker/inspect/).
- 결정: 기반 manifest와 빌드 image ID를 분리한다. 로컬 빌드 RepoDigests 부재는 정상일 수 있다.
  [Engine API 정의](https://github.com/moby/moby/blob/v28.3.3/docs/api/v1.51.yaml).
- 결정: -I/-S/-B의 플래그·경로·주입 양성 대조군을 확인한다. -S는 자동 site만 막으며 명시적 site.main()/임의 import를 금지하지 않는다.
  [Python3.11 명령줄](https://docs.python.org/3.11/using/cmdline.html), [site](https://docs.python.org/3.11/library/site.html).
- 결정: 일반 경로 host bind0. ro bind에도 호스트 변경이 보이는 부정 실험을 둔다.
  [bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
- network none에도 loopback은 남으므로 외부 연결 차단 설정만 주장한다.
  [none network](https://docs.docker.com/engine/network/drivers/none/).
- 입력: 공식 Docker Hub library/python 3.11.14-slim-bookworm의 linux/amd64 digest. 이미지 취득/실행은 GitHub만 한다.
  [metadata](https://hub.docker.com/v2/repositories/library/python/tags/3.11.14-slim-bookworm).
- 대안 제외: venv 버전 비교 반복, 전체 source/stdlib 인증 선언, 실제 server 설치·권한 변경.
- 독립 runtime_contract_review 역할은 공식 문서만 읽어 자료형·image ID·주입 대조군·bind 한계를 확인했다. 실행 시험으로 집계하지 않는다.
- 원래 초기 lab116873549306의 INSPECT_CONFIG_ENV 뒤 Docker의 --env 우선 병합을 확인했다. 중복 이름 거절 뒤 순서 없는 정확 내용 비교를 선택했다.
  [공식 Engine 병합](https://github.com/moby/moby/blob/v28.3.3/daemon/commit.go#L36-L58), [CLI 환경 구성](https://github.com/docker/cli/blob/v28.3.3/cli/command/container/opts.go#L458-L462).
