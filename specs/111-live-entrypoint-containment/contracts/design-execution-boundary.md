# Contract: Design-to-Execution Boundary

## Purpose

이 계약은 자연어 룰 설계 기능과 실거래 실행 기능 사이의 강제 경계를 정의한다. 설계 경로는 후보를 만들고 증거를 기록할 수 있지만, 라이브 워커를 시작하거나 주문을 제출하거나 실거래 설정을 바꿀 수 없다.

## Scope

적용 대상:

- `.github/workflows/operator-design.yml`
- `scripts/operator_design.sh`
- `auto-invest design`
- `src/auto_invest/design/*`
- `src/auto_invest/safety/command_registry.py`의 `design` 정책

적용하지 않는 대상:

- 기존 전진 검증 워크플로
- 캐너리 승격 게이트
- 자본 사다리
- 별도 실거래 리밸런싱 실행 권한

## Allowed Effects

설계 경로는 다음만 수행할 수 있다.

1. 운영자 의도를 불투명 데이터로 받는다.
2. 필요한 읽기 전용 계좌 문맥을 조회한다.
3. LLM을 정해진 룰 설계 판단 지점에서 호출한다.
4. 후보 룰을 생성한다.
5. 정적 검증을 수행한다.
6. 백테스트와 모의 검증을 실제 실행하거나, 실행 불가 상태를 `WAIT`/`FAIL`로 기록한다.
7. 후보 TOML, JSON, Markdown 검증 보고서를 저장한다.
8. 기존 append-only audit에 설계 요청·완료·거부를 기록한다.
9. 기존 후보·승격 시스템이 읽을 수 있는 proposal evidence를 출력한다.

## Forbidden Effects

설계 경로는 다음을 절대 수행하지 않는다.

- `auto-invest run` 시작
- `start_live_worker` 호출
- `rebalance-once --mode live` 호출
- KIS 주문·취소 API 호출
- `AUTO_INVEST_MODE=live` 변경
- `automation/*.request`의 `armed` 변경
- systemd live worker 시작·재시작
- 자본 사다리 승격·재사이징
- live 전략 교체
- whitelist/caps/loss budget 확대
- 헌법 또는 kernel manifest 변경
- 자연어 intent의 셸 평가

## Workflow Trigger Contract

`operator-design.yml`은 명시적 운영자 수동 실행만 허용한다.

```yaml
on:
  workflow_dispatch:
```

다음은 금지한다.

- `schedule`
- `push`에 의한 자동 설계
- `auto_ok: true` 기본값
- schedule 또는 dispatch를 운영자 live 승인으로 간주하는 로직

## Intent Transport Contract

안전한 예시:

```bash
printf '%s' "$INTENT" > /tmp/design-intent.txt
base64 < /tmp/design-intent.txt > /tmp/design-intent.b64
ssh ... 'bash -s' < scripts/operator_design.sh
```

또는 remote script가 stdin에서 원문을 읽는다.

금지 예시:

```bash
ssh host "bash -s -- '${INTENT}'"
```

다음 입력이 모두 원문 데이터로 전달돼야 한다.

```text
작은따옴표: John's portfolio
큰따옴표: "low risk"
명령 형태: $(touch /tmp/should-not-exist)
세미콜론: alpha; beta
역따옴표: `uname -a`
다중 줄
한글·이모지
```

## Verification Contract

### Static stage

- TOML 파싱
- Pydantic 모델 검증
- whitelist 일치
- order type 일치
- 안전 한도 상한
- 후보 지문 생성

### Backtest stage

PASS 조건:

- 실제 백테스트 함수가 호출됨
- 후보 지문이 결과에 바인딩됨
- 결과 파일 또는 run id가 있음
- 사전 선언된 최소 기준을 충족함

다음은 PASS가 아니다.

- 모듈 import 성공
- 함수 객체 존재
- “향후 활성화 예정”
- skipped
- stub
- fixture가 아닌 빈 성공값

### Paper/simulation stage

PASS 조건:

- 실제 모의 실행 또는 forward validation이 수행됨
- 브로커 주문은 호출되지 않음
- 후보 지문과 결과가 연결됨
- 필수 실행 기간·관측 기준을 충족함

실행하지 못하면 `WAIT`, 실패하면 `FAIL`이다.

### Aggregate

```text
STATIC=PASS AND BACKTEST=PASS AND PAPER=PASS
=> VERIFIED, ok=true

ANY FAIL
=> BLOCKED, ok=false

OTHERWISE
=> WAIT_DYNAMIC_VALIDATION, ok=false
```

## CLI Output Contract

설계 명령 성공 출력은 최소 다음을 포함한다.

```json
{
  "authority": "PROPOSAL_ONLY",
  "candidate_id": "...",
  "candidate_fingerprint": "...",
  "rules_path": "...",
  "verification": {
    "ok": false,
    "overall_status": "WAIT_DYNAMIC_VALIDATION",
    "static": {"status": "PASS"},
    "backtest": {"status": "WAIT"},
    "paper": {"status": "WAIT"}
  },
  "next_action": "submit_to_existing_validation_pipeline"
}
```

사람이 읽는 출력에는 다음 의미가 분명해야 한다.

> 룰 후보를 만들었습니다. 라이브 워커는 시작하지 않았고 실제 주문은 0건입니다.

## Command Registry Contract

```text
name: design
level: A2 / PROPOSAL
autonomous_allowed: true
can_place_order: false
can_change_live_config: false
can_scale_capital: false
can_reassign_strategy: false
```

## Audit Compatibility Contract

- 과거 이벤트 row는 변경·삭제하지 않는다.
- 새 설계 실행은 `RULE_DESIGN_DEPLOYED`를 기록하지 않는다.
- `RULE_DESIGN_COMPLETED`는 후보 생성 완료를 뜻한다.
- dynamic verification이 불완전하면 완료 payload 또는 별도 결과에 `PROPOSAL_ONLY`와 단계 상태를 기록한다.
- 이벤트 모델 변경이 필요하면 K4 감사 경계 변경으로 별도 검토한다. 이번 스펙의 기본 계획은 기존 payload를 재사용해 K4 터치를 피하는 것이다.

## Regression Guard Contract

테스트는 다음을 보장해야 한다.

1. production design code에서 `start_live_worker` 호출 0건
2. operator-design workflow에 `schedule` 0건
3. shell helper의 자동 `OK` 주입 0건
4. intent shell interpolation 0건
5. command policy live/order capability 0건
6. dynamic validation stub success 0건
7. live sentinel diff 0건

## Failure Behavior

- 후보 생성 실패: 명령 실패, live side effect 0
- 정적 검증 실패: 후보 거부, live side effect 0
- 동적 검증 미가용: proposal 저장 가능, `ok=false`, live side effect 0
- SSH 실패: workflow 실패 또는 명확한 setup state, live side effect 0
- malformed intent payload: 실행 거부, live side effect 0
- unknown exception: 감사 가능한 오류, live side effect 0

## Rollback Contract

어떤 회귀가 발생해도 다음은 롤백하지 않는다.

- 예약 실행 제거
- 자동 `OK` 제거
- 직접 라이브 시작 제거

후보 생성 기능만 선택적으로 복구한다. 안전 경계를 되돌리는 것은 롤백이 아니라 별도 돈 경로 변경이다.
