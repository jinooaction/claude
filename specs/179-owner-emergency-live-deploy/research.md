# Research: 오너 단회 장중 긴급 배포

## 결정 1: 일반 차단을 없애지 않고 별도 단회 예외로 만든다

- **Decision**: 기존 장중 차단을 기본값으로 유지하고, namespace 소유자 또는 헌법과 기본 브랜치 workflow에 정확히 고정 등록된 시스템 오너가 현재 `main` 커밋을 최대 15분 동안 한 번만 승인하는 경로를 별도로 둔다.
- **Rationale**: `--force`나 환경 변수는 다음 실행에도 남거나 다른 커밋에 재사용될 수 있다. 특정 커밋·실행·시간에 묶으면 긴급함은 해결하면서 영구 우회 경로를 만들지 않는다.
- **Alternatives considered**: 장중 차단 완전 제거, 범용 `--force`, 운영자가 서버에 직접 접속해 수동 배포. 모두 재사용·오입력·감사 누락 위험 때문에 기각했다.

## 결정 2: GitHub 오너 승인과 서버 루트 재검증을 분리한다

- **Decision**: GitHub 워크플로가 `repository_owner` 또는 소스에 고정된 헌법 등록 시스템 오너, 확인 문구, 현재 `main` SHA, 이유를 검증한다. 고정 SSH gateway와 루트 helper가 짧은 요청 파일을 만들고, 배포 실행기가 파일 보안·시간·SHA·단회성을 다시 검사한다.
- **Rationale**: GitHub는 오너 신원을 가장 잘 알고, 서버는 실제 파일 권한과 배포 대상을 가장 잘 안다. 어느 한쪽만 믿지 않으면 전달 중 오류와 오래된 요청을 차단할 수 있다.
- **Alternatives considered**: 채팅 문구만 신뢰, 서버 환경 변수만 사용, 임의 SSH 인자 실행. 기계적 증명이나 명령 제한이 부족해 기각했다.

## 결정 3: 주문 정지는 파일 존재와 잠금을 함께 쓴다

- **Decision**: 루트 helper가 고정 상태 경로에 배포 유지보수 파일을 만들고 배타 잠금을 잡는다. GitHub 라이브 helper, 서버 timer helper, Python 최종 중개사 쓰기가 파일 존재를 각각 검사한다.
- **Rationale**: 파일 잠금은 동시 긴급 배포를 막고, 파일 존재 검사는 복구 실패 뒤 helper 프로세스가 끝나도 주문 정지를 유지한다. 세 경계의 독립 검사는 예약과 배포가 경쟁하는 순간을 막는다.
- **Alternatives considered**: worker만 정지, systemd timer만 정지, 메모리 플래그. 이미 시작된 주문이나 다른 출처를 막지 못해 기각했다.

## 결정 4: 미체결 주문 0건을 생산 변경 전에 증명한다

- **Decision**: 기존 KIS read-only smoke를 정확한 대상 커밋으로 실행하고 성공과 `open_unfilled=0`을 모두 요구한다.
- **Rationale**: 미체결 주문이 있으면 worker 교체 중 취소·체결·대사 책임이 불명확해진다. 기존 smoke는 비밀 경계와 거래소 해석을 이미 검증한다.
- **Alternatives considered**: 로컬 DB만 조회, 주문을 자동 취소, 보유 포지션을 청산. 중개사 실제 상태를 놓치거나 새 돈 경로를 만들므로 기각했다.

## 결정 5: 배포 실행기가 승인 감사를 직접 남긴다

- **Decision**: 검증된 요청을 배포 실행기가 `DEPLOY_EMERGENCY_AUTHORIZED`로 기록한 뒤 같은 상관관계 식별자로 `DEPLOY_STARTED`를 기록한다. DB에 같은 요청 ID가 있으면 재사용으로 거부한다.
- **Rationale**: shell 로그만으로는 헌법 IV의 단일 추가 전용 장부가 아니다. 실행기가 기록해야 승인과 실제 배포가 정확히 결합된다.
- **Alternatives considered**: GitHub 로그만 남김, 별도 JSON 로그, 파일 삭제만으로 단회성 보장. 중앙 감사와 장기 재사용 방어가 약해 기각했다.

## 결정 6: 성공 또는 확인된 복구 전에는 주문 잠금을 풀지 않는다

- **Decision**: 긴급 helper는 배포 서비스 성공 시에만 잠금을 제거한다. 실행 실패라도 실행기가 이전 버전 복구를 확인해 정상 종료할 수 있으며, 복구까지 실패하면 잠금 파일을 남긴다.
- **Rationale**: 단순 프로세스 종료 trap으로 파일을 지우면 가장 위험한 실패 순간에 주문이 다시 열린다.
- **Alternatives considered**: 항상 cleanup trap, 시간 만료 자동 해제. 복구 상태와 무관하게 주문을 재개할 수 있어 기각했다.

## 결정 7: 첫 배포 부트스트랩은 기존 고정 경계 안에서 한다

- **Decision**: merge 후 기존 push 배포가 `sync-units`로 root helper를 갱신한다. helper는 정확한 승인 target을 격리 checkout하고 그 target의 기존 배포 상태기계를 응용 프로그램 사용자로 실행하되, 상태기계가 조작하는 저장소·DB·설정·환경·systemd 감독자·건강 창은 기존 고정 production 값만 사용한다.
- **Rationale**: run `33671389870`은 helper와 KIS smoke는 새 코드였지만 `auto-invest-deploy.service`가 아직 설치된 구버전 Python 배포 실행기를 호출해 `DEPLOY_STARTED` 전에 멈췄다. 새 계약을 이해해야 새 계약을 배포할 수 있는 순환 의존을 exact-target 실행으로 끊되, 실제 pull·sync·migrate·restart·rollback·감사는 기존 상태기계에 남긴다.
- **Alternatives considered**: production repo를 helper가 직접 checkout/reset하거나 임의 shell을 실행하는 방식은 기존 롤백·감사 경계를 우회한다. 구버전 서비스 재호출은 실제 장애를 반복한다.

## 결정 8: 시작 전 HALTED만 새 단회 요청이 엄격히 인계한다

- **Decision**: 이전 interlock이 root 소유 정규 파일이고 닫힌 HALTED 스키마이며 배타 잠금을 얻을 수 있고, 장부상 이전 request에 유일한 승인 1건과 시작 0건이 있을 때만 다음 정확한 등록 오너 요청이 같은 잠금을 인계한다.
- **Rationale**: 시작 전 부트스트랩 실패는 production 변경이 없으므로 새 검증된 시도가 복구할 수 있다. 반대로 `DEPLOY_STARTED` 뒤의 상태는 pull·migration·worker 변경 가능성이 있어 자동 인계하면 안 된다.
- **Alternatives considered**: 잠금 파일을 무조건 삭제하는 복구는 실행 중 배포와 주문을 겹치게 할 수 있고, 시간 만료만으로 푸는 방식은 장부의 실제 변경 상태를 증명하지 못한다.

## 결정 9: terminal rollback orphan은 파일·장부·생산 HEAD가 모두 일치할 때만 복구한다

- **Decision**: 요청 파일과 QUIESCED interlock이 함께 남았더라도 root 소유·0640·닫힌 스키마·동일 신원·배타 잠금, 정확한 승인/시작/실패/선택적 커널 변경/롤백 사건 수, 최신 롤백, production HEAD와 롤백 기준 일치를 모두 증명한 뒤 중개사 쓰기 잠금 아래에서만 이전 요청을 제거한다.
- **Rationale**: run `33673819722`은 기존 상태기계가 롤백을 완료했지만 shell EXIT trap이 main의 지역변수 소멸 뒤 실행돼 정리만 실패했다. 롤백 완료와 생산 기준 일치는 자동 복구할 수 있는 충분조건이지만, 둘 중 하나라도 없으면 주문 정지를 유지해야 한다.
- **Alternatives considered**: SSH에서 수동으로 파일을 삭제하거나 시간 만료로 해제하면 실행 중·부분 롤백·다른 생산 HEAD를 구분하지 못하므로 기각했다.

## 결정 10: 배포 config dry-run은 고정 env_path를 loader에 직접 전달한다

- **Decision**: DeployRunner가 이미 검증한 고정 `env_path`를 `dry_run_config`에도 전달한다. root helper는 `.env`를 source·echo·export하지 않는다.
- **Rationale**: systemd unit은 EnvironmentFile을 프로세스에 주입하지만 exact-target bootstrap은 의도적으로 별도 app-user 프로세스다. config loader는 이미 dotenv 읽기와 비밀값 등록·가림을 제공하므로 같은 경계를 재사용하는 것이 가장 작고 안전하다.
- **Alternatives considered**: shell에서 `.env`를 source하거나 명령행 환경으로 펼치면 파싱 차이와 비밀값 노출 표면이 늘어나므로 기각했다.
