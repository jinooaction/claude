# Research: 오너 단회 장중 긴급 배포

## 결정 1: 일반 차단을 없애지 않고 별도 단회 예외로 만든다

- **Decision**: 기존 장중 차단을 기본값으로 유지하고, 저장소 오너가 정확한 현재 `main` 커밋을 최대 15분 동안 한 번만 승인하는 경로를 별도로 둔다.
- **Rationale**: `--force`나 환경 변수는 다음 실행에도 남거나 다른 커밋에 재사용될 수 있다. 특정 커밋·실행·시간에 묶으면 긴급함은 해결하면서 영구 우회 경로를 만들지 않는다.
- **Alternatives considered**: 장중 차단 완전 제거, 범용 `--force`, 운영자가 서버에 직접 접속해 수동 배포. 모두 재사용·오입력·감사 누락 위험 때문에 기각했다.

## 결정 2: GitHub 오너 승인과 서버 루트 재검증을 분리한다

- **Decision**: GitHub 워크플로가 `repository_owner`, 확인 문구, 현재 `main` SHA, 이유를 검증한다. 고정 SSH gateway와 루트 helper가 짧은 요청 파일을 만들고, 배포 실행기가 파일 보안·시간·SHA·단회성을 다시 검사한다.
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

- **Decision**: merge 후 기존 push 배포가 `sync-units`와 배포 서비스의 사전 helper 갱신을 수행한 뒤 정상 장중 차단되는 것을 이용한다. 그 다음 오너가 새 workflow 입력으로 고정 `emergency-deploy` 명령을 호출한다.
- **Rationale**: 현재 서버가 아직 새 gateway를 모르는 순환 의존성을 임의 SSH로 깨지 않고, 이미 허용된 고정 `start-deploy`가 새 helper를 설치하게 한다.
- **Alternatives considered**: 임의 원격 shell, 장 마감 대기, 수동 root 설치. 경계 우회 또는 사용자 요구 미충족이라 기각했다.
