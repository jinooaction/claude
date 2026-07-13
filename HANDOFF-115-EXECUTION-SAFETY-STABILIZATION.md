# HANDOFF-115 — 실행 안전성 안정화 프로그램

## 한 줄 결론

현재 저장소의 가장 큰 위험은 투자 전략의 부족보다 **실거래 실행 권한과 계좌 상태가 여러 경로에 분산돼 있다는 점**이다. 다음 자동 후보인 운영자 보고 개선보다 실행 안전성을 우선하며, 첫 구현 단위는 `specs/111-live-entrypoint-containment`로 고정한다.

## 운영자 지시 해석

이번 운영자 지시는 다음 범위를 승인한다.

- 실행 안전성 문제를 해결하기 위한 코드, 테스트, 문서, 워크플로 수정 착수
- 관련 브랜치와 풀 리퀘스트 생성 및 검증
- 더 안전한 방향으로 실거래 진입점을 축소하거나 비활성화

이번 지시는 다음 행위를 승인하지 않는다.

- `armed: true` 변경
- `AUTO_INVEST_MODE=live` 전환
- 실제 주문 제출
- 계좌 자본 증액 또는 자본 사다리 승격
- 허용 종목이나 포지션 한도 확대
- 운영 서버의 `.env` 또는 실거래 센티넬 직접 변경

즉, **안전화 구현은 진행하되 실제 돈을 움직이는 실행은 하지 않는다.**

## 기준 상태

- 기준 `main`: `e9f9f98ea5787780a26c3833189b17b5b39cb7d5` — PR #508 머지
- 확인 시점: 2026-07-13 KST
- 열린 풀 리퀘스트: 없음
- 기존 활성 스펙 포인터: `specs/110-agent-harness-regression-liveness-contract`
- 새 작업 브랜치: `Codex/111-live-entrypoint-containment`
- 주요 저장소 선언 상태:
  - 돈 경로: `PREVIEW_ONLY`
  - 마이크로 GTAA 센티넬: `automation/rebalance-micro-gtaa.request`의 `armed: false`
  - 기존 포트폴리오 센티넬: `automation/rebalance-live.request`의 `armed: false`

위 상태는 저장소 기준이다. 실제 서버 프로세스, GitHub Actions 비밀값, KIS 계좌의 실시간 상태는 별도 확인이 필요하다.

## 왜 기존 다음 후보보다 이 작업이 우선인가

기존 자율 작업 큐는 `candidate-operator-report-liveness-contract`를 다음 후보로 선택했다. 보고 품질은 중요하지만, 현재 확인된 위험은 보고 문제보다 손실 가능성이 훨씬 크다.

우선순위 판단 기준은 다음과 같다.

1. 잘못되면 실제 돈이 움직이는가
2. 한 번의 장애가 중복 주문이나 한도 초과로 이어질 수 있는가
3. 감사 로그만으로 복구되지 않는 상태 불일치가 생길 수 있는가
4. 여러 자동화가 같은 계좌를 동시에 제어할 수 있는가
5. 모르는 상태에서 신규 매수를 계속할 수 있는가

이 기준으로 보면 실행 안전성 안정화가 최우선이다.

## 확인된 핵심 문제

### P0-1. `operator-design`이 증거 승격 경로를 우회해 라이브 워커를 시작할 수 있다

**확인한 파일**

- `.github/workflows/operator-design.yml`
- `scripts/operator_design.sh`
- `src/auto_invest/design/verifier.py`
- `src/auto_invest/design/deploy.py`
- `src/auto_invest/cli.py`
- `src/auto_invest/safety/command_registry.py`

**확인된 사실**

- `operator-design.yml`에는 매주 월요일 예약 실행이 있다.
- 수동 실행의 `auto_ok` 기본값은 `true`이고 예약 실행도 `AUTO_OK=1`로 처리된다.
- `operator_design.sh`는 `AUTO_OK=1`이면 표준 입력으로 `OK`를 넣는다.
- `design/verifier.py`는 백테스트와 하루 모의 운용을 실제로 수행하지 않으면서 정적 검증 통과 시 `ok=True`를 반환한다.
- `design/deploy.py::start_live_worker`는 `auto-invest run`을 분리 프로세스로 시작한다.
- `auto-invest run`은 `--dry-run`이 없고 자본이 양수면 라이브 워커 경로다.
- 명령 안전 등록부는 `design`을 `BOUNDED_LIVE`로 분류하고 실주문과 실거래 설정 변경 가능 명령으로 표시한다.

**실패 모드**

정적 형식 검증만 통과한 LLM 생성 룰이 예약 실행 또는 기본 `auto_ok=true` 경로로 별도 라이브 워커를 시작할 수 있다. 이는 현재의 돈 경로 준비도, 실거래 센티넬, 전진 검증, 자본 사다리와 독립적인 평행 실거래 경로다.

**결론**

스펙 111에서 가장 먼저 차단한다.

---

### P0-2. 주문 `POST`가 자동 재시도되어 중복 주문 가능성이 있다

**확인한 파일**

- `src/auto_invest/broker/client.py`
- `src/auto_invest/broker/overseas.py`

**확인된 사실**

- `ResilientClient`는 HTTP 메서드와 무관하게 전송 오류와 5xx를 재시도한다.
- `place_order`도 같은 공통 클라이언트로 `POST`를 보낸다.
- 요청에 브로커가 보장하는 멱등 키나 고객 주문 식별자는 보이지 않는다.

**실패 모드**

브로커가 주문을 접수했지만 응답이 유실되면 동일 주문이 다시 제출될 수 있다. 내부에는 마지막 주문번호만 남고 실제 계좌에는 복수 주문이 존재할 수 있다.

**후속 스펙 후보**

`112-order-submission-uncertainty-recovery`

---

### P0-3. 여러 주문이 같은 전체 노출 스냅숏으로 한도를 각각 통과할 수 있다

**확인한 파일**

- `src/auto_invest/risk/gates.py`
- `src/auto_invest/execution/rebalancer.py`
- `src/auto_invest/execution/order_router.py`

**확인된 사실**

- 전체 노출 게이트는 `현재 노출 + 이번 주문`을 검사한다.
- 리밸런서는 주문 묶음 시작 시 전체 노출을 한 번 계산한다.
- 이후 각 주문에 같은 `current_global_exposure_usd`를 전달한다.
- 열린 주문의 예약 노출은 보유 포지션 기반 노출에 포함되지 않는다.

**실패 모드**

각 주문은 한도 이내지만 주문 묶음 합계는 전체 노출 한도를 넘을 수 있다. 동시에 실행되는 두 리밸런싱도 같은 문제를 만들 수 있다.

**후속 스펙 후보**

`114-account-exposure-reservation`

---

### P0-4. 체결 원장과 포지션 캐시 갱신이 원자적이지 않다

**확인한 파일**

- `src/auto_invest/persistence/db.py`
- `src/auto_invest/execution/fill_sync.py`
- `src/auto_invest/persistence/positions.py`

**확인된 사실**

- SQLite 연결은 자동 커밋 방식이다.
- 체결 반영은 감사 기록, `fills` 삽입, `current_positions` 갱신 순서로 분리돼 있다.
- `fills`는 `INSERT OR IGNORE`지만 포지션 갱신은 삽입 성공 여부와 별개로 진행될 수 있다.
- 매도 수량이 기존 보유보다 큰 경우 음수 포지션을 막는 불변식이 없다.

**실패 모드**

중간 장애 또는 중복 재처리 시 체결과 포지션 캐시가 서로 다른 사실을 말할 수 있다. 잘못된 포지션은 노출 게이트와 손실 계산까지 오염시킨다.

**후속 스펙 후보**

`113-atomic-fill-ledger`

---

### P1-1. 안전 계산에 필요한 데이터가 없어도 신규 거래가 계속될 수 있다

**확인한 파일**

- `src/auto_invest/worker/loop.py`
- `src/auto_invest/execution/fill_sync.py`
- `src/auto_invest/reconciliation/runner.py`
- `src/auto_invest/risk/circuit_breaker.py`

**확인된 사실**

- 체결 동기화 실패는 오류를 기록하고 워커 틱을 계속한다.
- 순자산 조회 실패는 직전 값을 유지하고 거래를 계속한다.
- 정합성 검사에서 브로커 조회 실패는 `INCONCLUSIVE`이며 중단하지 않는다.
- 일부 보유 종목의 시세가 없으면 미실현 손익을 0으로 처리한다.

**판단**

보조 분석 데이터 실패는 격리해도 되지만, 체결·보유·순자산·손실 상태가 불명확하면 신규 매수는 중단해야 한다.

**후속 스펙 후보**

`115-degraded-execution-state`

---

### P1-2. 실거래 권한이 여러 워크플로와 프로세스에 분산돼 있다

**확인한 경로**

- `.github/workflows/operator-design.yml`
- `.github/workflows/go-live-canary.yml`
- `.github/workflows/rebalance-live-canary.yml`
- `.github/workflows/rebalance-micro-gtaa-canary.yml`
- `src/auto_invest/design/deploy.py`
- `src/auto_invest/execution/rebalancer.py`
- `src/auto_invest/worker/loop.py`

**판단**

워크플로마다 자본, 센티넬, 현금, 손실, 세션, SSH, 결과 판정 로직이 따로 있다. GitHub Actions가 애플리케이션과 별개의 두 번째 실행 엔진이 됐다.

**후속 스펙 후보**

`116-single-execution-authority`

---

### P1-3. 안전 경계 판정이 경로와 요약 문자열에 의존한다

**확인한 파일**

- `src/auto_invest/safety/boundary.py`
- `src/auto_invest/safety/autonomy.py`
- `.specify/memory/kernel.toml`
- `src/auto_invest/safety/command_registry.py`

**확인된 사실**

- 안전 경계는 보호 경로와 키워드로 탐지한다.
- 실제 자금 위험을 크게 바꾸는 일부 배포 TOML과 센티넬 설정은 코드 경계 목록 밖에 있다.
- 안전 판정 코드와 헌법도 같은 저장소가 스스로 수정할 수 있다.

**판단**

경로 기반 검사는 보조 장치로 유지하되, 이전 설정과 새 설정의 의미 차이를 판정하는 정책과 저장소 외부 승인 경계가 필요하다.

---

### P2. 문서와 현재 코드의 진실이 갈라져 있다

**확인한 파일**

- `README.md`
- `HANDOFF.md`
- 현재 `src/auto_invest/design/`, `judgment/`, `tuner/`, `analytics/`

README는 여전히 LLM을 호출하지 않고 스펙 004·005가 미구현이라고 설명하지만 현재 코드는 훨씬 앞서 있다. 이 차이는 새 세션이 현재 권위 있는 돈 경로를 잘못 판단하게 만든다.

## 프로그램 전체 불변식

모든 후속 구현은 아래를 지켜야 한다.

1. 실거래 센티넬은 `armed: false`를 유지한다.
2. 실제 주문이나 서버 실거래 전환을 테스트하지 않는다.
3. 허용 종목, 포지션 한도, 손실 예산을 확대하지 않는다.
4. 매도·취소·정합성 복구 경로는 불필요하게 막지 않는다.
5. 신규 매수 권한은 상태 신뢰도가 낮을수록 줄어들어야 한다.
6. 브로커 쓰기 권한은 최종적으로 하나의 실행 권한 모듈에만 남긴다.
7. 워크플로는 정책을 구현하지 않고 검증된 Python 명령을 호출하는 얇은 껍데기가 된다.
8. 모든 변경은 실패 주입 테스트와 복구 테스트를 포함한다.
9. 돈 경로 변경과 실제 돈 실행을 구분한다. 코드를 안전하게 바꾸는 것은 허용되지만 실거래 실행은 별도 승인이다.

## 고정 실행 순서

### 1단계 — 스펙 111: 라이브 진입점 봉쇄

목표:

- `operator-design` 예약 자동 실행 제거
- `auto_ok=true` 기본 및 자동 `OK` 주입 제거
- 설계 명령을 제안·증거 생성 전용으로 축소
- 동적 검증이 실제로 실행되지 않으면 실패 처리
- 자연어 입력의 셸 삽입 제거
- 명령 안전 등록부를 실제 권한에 맞게 `PROPOSAL`로 낮춤

### 2단계 — 주문 제출 불확실성 복구

목표:

- 주문 `POST` 자동 재시도 제거
- `SUBMISSION_UNKNOWN` 상태 추가
- 주문·체결 조회를 통한 확인 후 재시도
- 불명확 상태에서 신규 매수 차단

### 3단계 — 원자적 체결 원장

목표:

- 체결, 감사, 상태 전이, 포지션 캐시를 하나의 트랜잭션으로 처리
- 체결 삽입 성공 여부에 따른 캐시 갱신
- 음수 포지션 금지
- 시작 시 원장과 캐시 검증 및 재구축

### 4단계 — 계좌 단위 노출 예약

목표:

- 보유와 열린 주문을 합친 예약 노출
- 주문 묶음 전체 사전 검증
- 계좌별 실행 잠금
- 동시 워커·동시 리밸런싱 방지

### 5단계 — 저하 상태와 단일 실행 권한

목표:

- `HEALTHY`, `DEGRADED_SELL_ONLY`, `HALTED` 상태기계
- 체결·보유·순자산 신선도 계약
- 모든 실거래 경로를 하나의 `ExecutionAuthority`로 통합
- GitHub Actions의 정책 로직을 Python으로 이동

## 코덱스가 지금 바로 할 일

1. `Codex/111-live-entrypoint-containment` 브랜치를 이어받는다.
2. 다음 파일을 순서대로 읽는다.
   - `AGENTS.md`
   - 이 문서
   - `specs/111-live-entrypoint-containment/spec.md`
   - `specs/111-live-entrypoint-containment/plan.md`
   - `specs/111-live-entrypoint-containment/tasks.md`
   - `.github/workflows/operator-design.yml`
   - `scripts/operator_design.sh`
   - `src/auto_invest/design/verifier.py`
   - `src/auto_invest/design/deploy.py`
   - `src/auto_invest/cli.py`의 `design` 명령
   - `src/auto_invest/safety/command_registry.py`
3. 현재 동작을 고정하는 실패 테스트를 먼저 추가한다.
4. 스펙 111 범위만 구현한다. 주문 재시도, 체결 원장, 노출 예약은 같은 PR에 섞지 않는다.
5. `automation/*.request`, `.env`, 배포 포트폴리오, 헌법, 커널 목록은 수정하지 않는다.
6. 전체 검증 후 풀 리퀘스트를 준비 상태로 바꾸고 자동 머지 규칙을 따른다.
7. 머지 뒤 실제 서버가 아니라 저장소·워크플로 기준으로만 안전 상태를 보고한다. 실서버 확인이 필요하면 미확인으로 남긴다.

## 스펙 111 완료 기준

다음 조건이 모두 충족돼야 한다.

- `operator-design.yml`의 예약 실행이 없다.
- 수동 실행 기본값으로 라이브가 시작되지 않는다.
- 자연어 설계 입력이 원격 셸 문자열에 직접 삽입되지 않는다.
- `operator_design.sh`가 `OK`를 자동 주입하지 않는다.
- `design` 명령이 `start_live_worker`를 호출하지 않는다.
- `VerifyResult.ok=True`는 실제 백테스트와 모의 운용 증거가 모두 있을 때만 가능하다.
- 검증 엔진이 미구현·불가·예외 상태면 `ok=False`다.
- 생성된 룰과 검증 결과는 후보 산출물로 남길 수 있다.
- 명령 안전 등록부에서 `design`은 실주문·실거래 설정 변경 권한이 없는 `PROPOSAL`이다.
- 직접 라이브 시작 경로가 남아 있지 않음을 정적 검사 테스트가 증명한다.
- 기존 주요 실거래 센티넬의 내용은 바뀌지 않는다.
- 관련 테스트, 전체 테스트, 린트, 하네스, HANDOFF 검증, PR 품질 관문이 통과한다.

## 필수 검증

```bash
uv run pytest tests/unit/test_design_verifier.py \
  tests/unit/test_design_deploy.py \
  tests/integration/test_design_cli.py \
  tests/unit/test_safety_command_registry.py

uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
python3 scripts/check_pr_quality_gate.py /tmp/pr-body-111.md
```

워크플로 문법과 위험 동작 부재도 별도로 확인한다.

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

path = Path('.github/workflows/operator-design.yml')
data = yaml.safe_load(path.read_text(encoding='utf-8'))
assert 'schedule' not in (data.get('on') or {})
PY

rg -n "AUTO_OK|start_live_worker|auto_ok|schedule:" \
  .github/workflows/operator-design.yml \
  scripts/operator_design.sh \
  src/auto_invest/design \
  src/auto_invest/cli.py
```

`PyYAML`이 개발 의존성에 없다면 저장소의 기존 YAML 검증 방법을 사용하고, 새 런타임 의존성을 추가하지 않는다.

## 풀 리퀘스트 분할 원칙

- 스펙 111에는 라이브 진입점 봉쇄만 포함한다.
- 주문 재시도와 주문 상태기계는 별도 PR이다.
- 체결 원장과 포지션 캐시는 별도 PR이다.
- 노출 예약과 계좌 잠금은 별도 PR이다.
- 저하 상태와 단일 실행 권한은 앞 단계 완료 후 진행한다.

각 PR은 독립적으로 안전성을 높이고, 중간 상태에서도 기존보다 위험해지지 않아야 한다.

## 남은 미확인 사항

다음은 저장소 코드만으로 확인하지 못했다.

- 운영 서버에서 현재 실행 중인 `auto-invest` 프로세스 수
- systemd와 분리 프로세스로 시작된 오래된 라이브 워커 존재 여부
- GitHub Actions의 현재 비밀값과 Environment 보호 규칙
- KIS 계좌의 현재 열린 주문과 실제 보유 상태
- `operator-design` 최근 예약 실행 여부와 결과

스펙 111은 위 상태를 추측하지 않고, 코드상 평행 진입점을 제거하는 데 집중한다.

## 최종 보고 형식

코덱스는 완료 시 다음 순서로 보고한다.

1. 핵심 결론
2. 제거한 실거래 진입점
3. 남긴 설계 기능과 대체 승격 경로
4. 테스트와 하네스 결과
5. 안전 경계와 돈 경로 영향
6. 실행하지 않은 실제 돈 검증
7. 다음 스펙 후보와 우선순위

“안전해졌다”라고만 말하지 말고, **어떤 호출 경로가 사라졌고 어떤 테스트가 그 부재를 증명하는지**를 적는다.
