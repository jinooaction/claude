# Research: Autonomous Promotion Actions

## 결정 1: 기존 live canary를 직접 무장하지 않는다

**Decision**: promotion action 루프는 `rebalance-live.request`, live config, 자본 사다리 sentinel을 수정하지 않는다. 대신 canary 제출 큐와 hardened canary 실행 사이드카를 만든다.

**Rationale**: 헌법 VI와 X는 `Backtest -> Canary -> Full`, 자본 사다리, 재지정 게이트를 안전 경계로 둔다. 새 후보를 실거래 경로에 넣는 자동화는 가치가 크지만, 실주문 권한을 새 워크플로에 중복 부여하면 안전 경계가 흐려진다.

**Alternatives considered**:

- `rebalance-live.request`를 자동 수정: 더 빠르지만 실제 주문 sentinel을 건드려 등급 4 실행 경계에 가까워진다.
- 기존 `reassign-on-tournament.yml`에 후보 주입: 경로는 적지만 기존 champion/challenger 의미를 흐린다.

## 결정 2: promotion 전용 registry/submission 상태 파일을 둔다

**Decision**: `automation/promotion-forward-registry.json`과 `automation/promotion-canary-submissions.json`을 tracked 상태 파일로 두되, 실행 워크플로는 직전 `autonomous-promotion-actions` 사이드카의 `next` 상태를 우선 읽고 tracked 파일은 fallback으로 쓴다.

**Rationale**: 사이드카만으로도 즉시 자동 실행은 가능하지만, 다음 세션이 어떤 후보를 이미 등록했는지 안정적으로 재현하려면 main에 남는 상태도 필요하다. 실행은 sidecar 우선으로 지연을 줄이고, tracked PR은 감사 가능한 장기 기록으로 남긴다.

**Alternatives considered**:

- 사이드카 브랜치만 사용: main 기록이 없어 다음 세션 인계와 리뷰가 약해진다.
- DB에 저장: 로컬/서버 DB 상태가 갈라지고, PR 리뷰 가능성이 낮다.

## 결정 3: action 루프와 실행 워크플로를 분리한다

**Decision**: `autonomous-promotion-actions.yml`은 후보를 등록/제출 상태로 변환하고, `promotion-forward-tracks.yml`와 `promotion-canary-submissions.yml`이 실제 paper/canary 검증을 수행한다.

**Rationale**: 의사결정과 실행을 분리하면 순수 코어 테스트가 쉽고, paper/canary 실행 실패가 등록 상태를 오염시키지 않는다.

**Alternatives considered**:

- 하나의 workflow에서 등록과 실행을 모두 수행: 단순하지만 실패 재시도와 감사 로그가 섞인다.

## 결정 4: 경로 검증은 whitelist 방식으로 좁힌다

**Decision**: portfolio는 `deploy/*.toml`, promotion DB/halt는 `data/promotion_*`, canary bands는 `config/*.toml`만 허용한다.

**Rationale**: 후보가 제공하는 설정은 자동 실행 입력이다. 상대경로 traversal, live halt, live sentinel, 임의 config 쓰기는 사전에 차단해야 한다.

**Alternatives considered**:

- 파일 존재 여부만 확인: 악의적이거나 잘못된 경로가 live 파일을 가리킬 수 있다.
- 모든 repo 상대경로 허용: 편하지만 자동화 안전 경계가 약하다.
