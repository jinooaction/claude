# Research: Live Canary Gateway And Profit Evidence

## Decision 1 - Production 전용 Ed25519 서명

- **Decision**: production 환경 secret에 Ed25519 개인키를 두고 서버에는 root 소유 공개키만 설치한다.
- **Rationale**: 현재 저장소 SSH 키는 미리보기에도 쓰이므로 gateway에 주문 명령만 추가하면 환경 승인을 우회한다.
- **Alternatives considered**: 같은 SSH 키를 그대로 허용(권한 분리 실패), 공유 HMAC(서버·GitHub 양쪽 비밀 배포 필요), OIDC 원격 검증(네트워크·검증 복잡도 큼).

## Decision 2 - 짧은 수명·일회성 서명 payload

- **Decision**: 저장소, workflow, run id, commit, capital, expiry, nonce 전체를 서명하고 서버가 nonce를 한 번만 소비한다.
- **Rationale**: 자본 변조와 과거 승인 재사용을 동시에 차단한다.
- **Alternatives considered**: capital만 서명(재사용 가능), run id만 서명(commit·자본 변조 가능).

## Decision 3 - 기존 성과 엔진을 첫 수익 단일 정의로 사용

- **Decision**: `performance --mode live --snapshot`의 fills·실현·미실현·총손익을 그대로 소비한다.
- **Rationale**: 헌법 X의 백테스트·캐너리·라이브 동일 손익 정의를 보존한다.
- **Alternatives considered**: KIS 평가금액 차이 직접 계산(입출금·현금흐름 오염), sidecar 문자열 합산(정의 중복).

## Decision 4 - 최초 수익 달성은 누적 보존

- **Decision**: 현재 손익과 최초 달성 증거를 분리하고 prior sidecar의 최초 달성을 계속 보존한다.
- **Rationale**: 양수 뒤 음수로 바뀌어도 “첫 실제 수익을 한 번 관측했는가”라는 목표 사실은 사라지지 않는다.
- **Alternatives considered**: 최신 손익만 저장(완료 증거 소실), audit DB만 조회(원격 접근 없이는 다음 세션 검증 어려움).

## Decision 5 - 이벤트와 예약을 함께 사용

- **Decision**: live-canary 완료 즉시 관측하고 평일 장중 후속 예약으로 지연 체결·가격 변화를 다시 측정한다.
- **Rationale**: 지정가는 즉시 체결되지 않을 수 있고 최초 run 직후 손익은 거의 0일 수 있다.
- **Alternatives considered**: 하루 한 번(상태 지연), production job 내부만 측정(후속 체결·수익 미감지).
