# HANDOFF-115 — 실행 안전성 안정화 프로그램

## 한 줄 결론

현재 저장소의 가장 큰 위험은 투자 전략의 부족보다 **실거래 실행 권한과 계좌 상태가 여러 경로에 분산돼 있다는 점**이었다. `specs/111-live-entrypoint-containment`, `specs/112-order-submission-uncertainty-recovery`, `specs/113-atomic-fill-ledger`, `specs/114-account-exposure-reservation`, `specs/115-degraded-execution-state`, `specs/116-single-execution-authority`, `specs/117-submission-unknown-broker-lookup`은 main에 들어갔다. 저장소 코드 기준 실행 안전성 안정화 프로그램의 111~117 단계는 완료됐고, 남은 것은 실제 서버·KIS 계좌 운영 상태 확인이다.

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

- 기준 `main`: `8fd6b90b7c0003104065b88ba0149e0002254953` — PR #521 스펙 117 `SUBMISSION_UNKNOWN` broker lookup 복구 머지
- 확인 시점: 2026-07-13 KST
- 열린 풀 리퀘스트: handoff 갱신 전 없음
- 기존 활성 스펙 포인터: `specs/117-submission-unknown-broker-lookup`
- 최근 완료 브랜치: `codex/117-submission-unknown-broker-lookup`
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

`116-single-execution-authority` — PR #519에서 저장소 코드 기준 닫힘

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
- `SUBMISSION_UNKNOWN` 상태와 `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트 추가
- 명시적 KIS 업무 거부와 접수 여부 불명확 실패 분리
- 운영 알림과 읽기 전용 요약에 불명확 상태 노출
- 주문·체결 조회를 통한 자동 확인 후 재시도와 불명확 상태 신규 매수 차단은 후속 복구·저하 상태 스펙으로 남김

### 3단계 — 원자적 체결 원장

목표:

- 체결, 감사, 상태 전이, 포지션 캐시를 하나의 트랜잭션으로 처리
- 체결 삽입 성공 여부에 따른 캐시 갱신
- 중복 `kis_fill_id`가 포지션 캐시를 다시 움직이지 않게 함
- 음수 포지션 DB 제약과 시작 시 원장·캐시 검증은 외부 보유 청산 의미를 확인한 뒤 후속으로 분리

### 4단계 — 계좌 단위 노출 예약

목표:

- 보유와 열린 BUY 주문을 합친 예약 노출 — 스펙 114에서 완료
- 주문 묶음 안의 앞선 BUY 예약 반영 — 스펙 114에서 완료
- 계좌별 실행 잠금 — 단일 실행 권한 단계로 이월
- 동시 워커·동시 리밸런싱 방지 — 단일 실행 권한 단계로 이월

### 5단계 — 저하 상태와 단일 실행 권한

목표:

- `HEALTHY`, `DEGRADED_SELL_ONLY`, `HALTED` 상태기계 — 스펙 115에서 완료
- 체결·보유·순자산·손실 신선도 계약 — 스펙 115에서 신규 BUY 차단으로 완료
- 모든 실거래 경로를 하나의 `ExecutionAuthority`로 통합 — 스펙 116 완료
- GitHub Actions의 정책 로직을 Python으로 이동

## 코덱스가 지금 바로 할 일

1. `origin/main` 최신이 `8b0cfac` 이후인지 확인한다. 저장소 코드 기준 111~116 실행 안전성 단계는 완료됐다.
2. 다음 파일을 순서대로 읽는다.
   - `AGENTS.md`
   - 이 문서
   - `specs/115-degraded-execution-state/spec.md`
   - `specs/115-degraded-execution-state/plan.md`
   - `specs/115-degraded-execution-state/tasks.md`
   - `src/auto_invest/execution/execution_state.py`
   - `src/auto_invest/execution/order_router.py`
   - `src/auto_invest/worker/loop.py`
   - `src/auto_invest/execution/rebalancer.py`
3. 후속으로 진행한다면 `SUBMISSION_UNKNOWN` broker lookup 복구 또는 실제 서버·KIS 계좌 운영 상태 전수 확인을 별도 범위로 잡는다.
4. `SUBMISSION_UNKNOWN` 자동 broker lookup 복구는 단일 authority와 섞을지 별도 복구 PR로 분리할지 먼저 판단한다.
5. `automation/*.request`, `.env`, 배포 포트폴리오, 헌법, 커널 목록은 수정하지 않는다.
6. 전체 검증 후 풀 리퀘스트를 준비 상태로 바꾸고 자동 머지 규칙을 따른다.
7. 머지 뒤 실제 서버나 KIS 계좌 상태를 추측하지 말고 저장소 기준 안전 상태와 미확인 영역을 분리해 보고한다.

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

## 스펙 111 구현 결과

현재 PR #509에서 저장소 기준 평행 실거래 진입점은 후보 생성 전용 경로로 축소됐다.

제거·축소한 경로:

- `.github/workflows/operator-design.yml`
  - 예약 실행을 제거했다.
  - `auto_ok` 입력과 기본 true 의미를 제거했다.
  - 자연어 intent 원문을 원격 셸 인자로 넣지 않고 `INTENT_B64` 데이터로 전달한다.
  - Summary는 `PROPOSAL_ONLY`와 실거래 프로세스 시작 없음만 보고한다.
  - 실행 로그와 Summary에는 intent 원문 대신 길이와 SHA-256 지문만 남긴다.
- `.github/workflows/trigger-design.yml`
  - `.trigger/design-now.txt` push 자동 실행을 제거했다.
  - 수동 실행만 남기고 동일하게 `INTENT_B64`로 intent를 전달한다.
  - `.verify/last_design.md`에는 intent 원문 대신 길이와 SHA-256 지문만 남긴다.
- `scripts/operator_design.sh`
  - 자동 `OK` 주입과 live 상태 확인을 제거했다.
  - 콘솔 인자, 표준입력, `INTENT_B64`를 후보 생성용 데이터로만 읽는다.
  - helper 콘솔 출력도 intent 원문 대신 길이만 보고한다.
- `src/auto_invest/cli.py`
  - `design` 명령에서 `prompt_operator_ok()`, `start_live_worker()`,
    `RULE_DESIGN_DEPLOYED` emission을 제거했다.
  - 정적 검증 통과 후보는 `config/rules_auto_<timestamp>.toml`과
    `config/rules_auto_<timestamp>.proposal.json`으로 남긴다.
  - 출력은 후보 파일, 검증 보고서, 후보 지문, 단계별 검증 상태와
    `PROPOSAL_ONLY`를 명시한다.
- `src/auto_invest/design/verifier.py`
  - `VerificationStageResult`와 fail-closed aggregate 결과를 도입했다.
  - 동적 백테스트·paper 증거가 없으면 `WAIT_DYNAMIC_VALIDATION`, `ok=False`다.
  - 실제 stage 증거가 모두 같은 후보 지문에 묶인 경우에만 `ok=True`다.
- `src/auto_invest/design/deploy.py`
  - 후보 파일과 proposal JSON 저장만 남겼다.
  - 과거 live-start 함수명은 즉시 `LiveActivationBoundaryError`를 내는 호환 껍데기다.
- `src/auto_invest/safety/command_registry.py`
  - `design`을 `A2 / proposal`로 낮추고 주문·live config·자본·재지정 권한을 모두 false로 맞췄다.

남긴 기능과 대체 경로:

- 자연어 설계, KIS 읽기 전용 계좌 문맥, Claude 호출, 정적 검증, 후보 TOML 저장은 유지한다.
- 후보의 다음 경로는 `candidate → backtest → paper/forward → canary → approved live`다.
- 과거 `RULE_DESIGN_DEPLOYED` 이벤트와 `design --check` 읽기 전용 요약은 역사 호환으로 남긴다.

검증 증거:

- focused design 주변 테스트: `70 passed`
- 전체 테스트: `2599 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- 보호 파일 해시: live sentinels, 헌법, kernel manifest, caps, whitelist 모두 작업 전과 동일

남은 미확인 사항:

- 실제 운영 서버에 과거 design-driven 프로세스가 남아 있는지는 확인하지 않았다.
- GitHub Actions 비밀값과 Environment 보호 규칙은 저장소 변경만으로 확인하지 않았다.
- KIS 계좌의 현재 열린 주문과 실제 보유 상태는 조회하지 않았다.

## 스펙 112 완료 기준

다음 조건이 모두 충족돼야 한다.

- 신규 주문 제출 `POST /uapi/overseas-stock/v1/trading/order`는 전송 오류나 5xx에서 자동 재시도하지 않는다.
- 읽기 전용 요청의 기존 재시도 동작은 유지된다.
- 전송 오류, 5xx, 비정상 응답처럼 접수 여부가 불명확한 주문 제출 실패는 `SUBMISSION_UNKNOWN`으로 남는다.
- `SUBMISSION_UNKNOWN`은 `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트와 같은 correlation id로 연결된다.
- 명시적 KIS 업무 거부는 기존 `REJECTED_BY_BROKER`와 `ORDER_REJECTED_BY_BROKER`로 남는다.
- 운영 알림은 불명확 제출을 브로커 거부로 표현하지 않고, 주문·체결 조회 전 자동 재시도 금지를 말한다.
- 실제 주문, 취소, 실거래 전환, 자본·whitelist·caps·loss budget·live sentinel·헌법·kernel 변경이 없다.
- 관련 테스트, 전체 테스트, 린트, 하네스, HANDOFF 검증, PR 품질 관문이 통과한다.

## 스펙 112 구현 결과

현재 `Codex/112-order-submission-uncertainty-recovery` 브랜치는 주문 제출 불확실성을 저장소 코드 기준으로 명시 상태로 보존한다.

구현한 내용:

- `src/auto_invest/broker/client.py`
  - `ResilientClient.request(..., retry_transient=False)` 요청별 정책을 추가했다.
  - 기본값은 기존과 같아 읽기 전용 `GET`의 5xx·전송 오류 재시도는 유지된다.
  - no-retry 요청도 rate limiter와 circuit breaker preflight를 통과하며, transient 실패는 breaker failure로 기록된다.
- `src/auto_invest/broker/overseas.py`
  - 신규 주문 제출 `place_order`의 KIS `POST /trading/order` 호출에 `retry_transient=False`를 적용했다.
  - 성공 주문번호 파싱과 마스킹된 진단 생성은 유지했다.
- `src/auto_invest/execution/order_router.py`
  - HTTP 5xx, 전송 오류, 주문번호 없는 불명확 응답을 `SUBMISSION_UNKNOWN`으로 분류한다.
  - `INTENT -> SUBMISSION_UNKNOWN` 상태 전이와 `ORDER_SUBMISSION_UNKNOWN` 감사 이벤트를 남긴다.
  - `rt_cd != 0` 같은 KIS 업무 거부는 기존 `REJECTED_BY_BROKER`로 유지한다.
  - `SUBMISSION_UNKNOWN`에는 `kis_order_id`를 설정하지 않는다.
- `src/auto_invest/persistence/audit.py`
  - `OrderSubmissionUnknownPayload`를 추가했다.
  - payload에는 broker code, masked diagnostics, operator next action이 들어간다.
- `src/auto_invest/notifications/audit_tail.py`
  - 기본 알림 이벤트에 `ORDER_SUBMISSION_UNKNOWN`을 포함했다.
  - 알림 문구는 "접수 여부 불명확"과 "주문/체결 조회 전 자동 재시도 금지"를 말한다.
- `src/auto_invest/cli.py`
  - 읽기 전용 오류 카운트에 `ORDER_SUBMISSION_UNKNOWN`을 포함했다.

검증 증거:

- focused broker/order/audit/notification tests: `62 passed`
- 전체 테스트: `2607 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- 보호 범위: `automation/*.request`, live portfolio configs, whitelist/caps, loss budget, 헌법, kernel manifest 변경 없음

남은 미확인·후속 사항:

- 실제 KIS 계좌의 열린 주문, 보유, 서버 프로세스는 조회하지 않았다.
- `SUBMISSION_UNKNOWN`을 자동으로 broker order/execution lookup으로 해소하는 복구 경로는 아직 없다.
- 불명확 상태에서 신규 매수를 계좌 단위로 자동 차단하는 저하 상태기계는 스펙 115에서 닫혔다.
- 이 문단 작성 당시 다음 실행 안전성 수동 후보였던 `113-atomic-fill-ledger`는 #513에서 닫혔다.

## 스펙 113 완료 기준

다음 조건이 모두 충족돼야 한다.

- 체결 계획 적용은 `BEGIN IMMEDIATE` 트랜잭션 안에서 실행된다.
- 새 `fills` row 삽입, `FILL` 감사 이벤트, `current_positions` 갱신, 주문 상태 전이는 함께 커밋되거나 함께 롤백된다.
- `fills.kis_fill_id` 중복으로 row가 삽입되지 않으면 `FILL` 감사 이벤트와 포지션 캐시 갱신도 실행하지 않는다.
- `fills_applied`와 `qty_applied`는 실제 삽입된 체결만 센다.
- 기존 정상 체결, 부분 체결, 거래소 스윕, 브로커 조회 실패 격리 동작은 유지된다.
- 실제 주문, 취소, 실거래 전환, 자본·whitelist·caps·loss budget·live sentinel·헌법·kernel 변경이 없다.
- 관련 테스트, 전체 테스트, 린트, 하네스, HANDOFF 검증, PR 품질 관문이 통과한다.

## 스펙 113 구현 결과

현재 `Codex/113-atomic-fill-ledger` 브랜치는 체결 원장 적용을 저장소 코드 기준으로 원자화한다.

구현한 내용:

- `src/auto_invest/execution/fill_sync.py`
  - `apply_fill_plan`이 빈 계획이 아니면 `BEGIN IMMEDIATE` 트랜잭션으로 체결·감사·포지션·상태 전이를 묶는다.
  - `_apply_fill`은 `fills` 삽입을 먼저 시도하고, `rowcount == 0`이면 `FILL` 감사와 포지션 캐시 갱신을 건너뛴다.
  - `fills_applied`와 `qty_applied`는 실제 삽입된 체결 row만 센다.
  - 체결 적용 중 예외가 발생하면 트랜잭션을 롤백한다.
- `tests/integration/test_fill_sync.py`
  - 이미 존재하는 `kis_fill_id`가 다시 계획돼도 포지션과 감사가 움직이지 않는 회귀 테스트를 추가했다.
  - 포지션 캐시 갱신 실패를 주입해 `fills`, `FILL` 감사, 포지션, 주문 상태가 모두 롤백되는지 검증했다.
- `specs/113-atomic-fill-ledger/`
  - 스펙, 계획, 연구, 데이터 모델, 계약, quickstart, 체크리스트, 작업표를 추가했다.

검증 증거:

- 구현 전 focused test: `tests/integration/test_fill_sync.py`에서 중복 체결과 롤백 테스트 2건 실패 확인
- focused fill sync: `uv run pytest tests/integration/test_fill_sync.py -q` → `9 passed`
- worker fill sync: `uv run pytest tests/integration/test_worker_fill_sync.py -q` → `3 passed`
- 관련 포지션·감사·성과 테스트: `63 passed`
- 전체 테스트: `2609 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- 보호 범위: live sentinel, capital, whitelist/caps, loss budget, 헌법, kernel manifest 변경 없음

남은 미확인·후속 사항:

- 실제 KIS 계좌의 열린 주문, 보유, 서버 프로세스는 조회하지 않았다.
- 외부 보유 청산 경로 때문에 음수 포지션 DB 제약은 이번 PR에 넣지 않았다.
- 시작 시 원장·캐시 자동 검증 및 재구축은 후속 체결 건강성 작업으로 남겼다.
- 이 문단 작성 당시 다음 실행 안전성 수동 후보였던 `114-account-exposure-reservation`은 #515에서 닫혔다.

## 스펙 114 구현 결과

PR #515에서 저장소 기준 계좌 노출 예약 계산을 보수화했다.

구현한 내용:

- `src/auto_invest/execution/exposure_reservation.py`
  - `INTENT`, `SUBMITTED`, `PARTIALLY_FILLED`, `SUBMISSION_UNKNOWN` BUY 주문을 열린 예약 노출로 합산한다.
  - 현재 게이트 평가 중인 correlation id는 제외해 현재 주문을 두 번 세지 않는다.
  - 가격을 알 수 없는 열린 BUY는 보수적으로 신규 BUY를 막는 방향으로 처리한다.
- `src/auto_invest/execution/order_router.py`
  - 기존 K1 gate 체인은 유지하고, per-symbol/global exposure 입력에 열린 BUY 예약 노출을 더한다.
  - `SUBMISSION_UNKNOWN`도 실제 접수 가능성을 배제할 수 없으므로 열린 BUY로 취급한다.
- `src/auto_invest/execution/rebalancer.py`
  - paper/test router처럼 durable `orders` row가 없는 경로에서도 한 실행 안의 성공한 BUY notional을 다음 BUY의 exposure 입력에 반영한다.
  - 열린 SELL 또는 방금 제출된 SELL은 fill 전까지 노출 감소로 쓰지 않는다.
- `tests/integration/test_order_router.py`
  - 기존 열린 `SUBMITTED`와 `SUBMISSION_UNKNOWN` BUY가 새 BUY의 global cap을 소모하는 회귀 테스트를 추가했다.
- `tests/integration/test_spec_032_live_rebalancer.py`
  - 한 리밸런싱 안에서 첫 BUY가 통과한 뒤 두 번째 BUY가 stale global snapshot으로 같이 통과하던 결함을 회귀 테스트로 고정했다.
- `specs/114-account-exposure-reservation/`
  - 스펙, 계획, 연구, 데이터 모델, 계약, quickstart, 체크리스트, 작업표를 추가했다.

검증 증거:

- 구현 전 focused regression:
  - 열린 BUY 예약 테스트는 기존 코드가 `SUBMITTED`로 통과해 실패
  - 리밸런싱 묶음 테스트는 두 BUY가 모두 `PAPER_FILLED`로 통과해 실패
- 구현 후 focused regression: `2 passed`
- 라우터·리밸런서 focused suite: `28 passed`
- 인접 risk/paper/lifecycle 테스트: `43 passed`
- 전체 테스트: `2612 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- post-merge workflow: deploy `29250744546`, released-work `29250744535`, autonomous-work `29250744399` success
- 보호 범위: live sentinel, capital, whitelist/caps 값, loss budget, 헌법, kernel manifest, 비밀값 변경 없음

남은 미확인·후속 사항:

- 실제 KIS 계좌의 열린 주문, 보유, 서버 프로세스는 조회하지 않았다.
- cross-process 계좌 잠금과 단일 `ExecutionAuthority`는 스펙 116에서 닫혔다.
- 체결·보유·순자산·손실 신선도가 불명확할 때 신규 BUY를 자동 차단하는 저하 상태기계는 스펙 115에서 닫혔다.
- 남은 저장소 후속 후보는 `SUBMISSION_UNKNOWN` broker order/execution lookup 복구다.

## 스펙 115 구현 결과

PR #517에서 저장소 기준 저하 상태 신규 BUY 차단을 구현했다.

구현한 내용:

- `src/auto_invest/execution/execution_state.py`
  - `HEALTHY`, `DEGRADED_SELL_ONLY`, `HALTED` 상태와 stable reason code를 정의했다.
  - `SUBMISSION_UNKNOWN` BUY와 최신 `INCONCLUSIVE` reconciliation을 persisted blocker로 평가한다.
  - `execution_state_gate`는 degraded 상태의 BUY를 `ORDER_REJECTED_BY_GATE`로 거부하고 SELL은 통과시킨다.
- `src/auto_invest/execution/order_router.py`
  - 기존 gate chain 안에 `execution_state_gate`를 추가했다.
  - provider가 없으면 DB persisted blocker만 평가하고, Worker는 runtime blocker provider를 주입한다.
- `src/auto_invest/worker/loop.py`
  - live fill sync 실패, NAV refresh 실패, circuit breaker mark 결측을 runtime blocker로 저장한다.
  - 다음 성공 관측에서 각 blocker를 해제한다.
  - 이 blocker들은 신규 BUY에만 작동하고 기존 halt, whitelist, K1 cap, SELL 경로는 유지된다.
- `tests/unit/test_execution_state.py`
  - `SUBMISSION_UNKNOWN` BUY와 최신 `INCONCLUSIVE` reconciliation이 degraded 상태를 만드는지 검증한다.
  - `SUBMISSION_UNKNOWN` SELL은 새 노출이 아니므로 degraded blocker가 아님을 검증한다.
- `tests/integration/test_order_router.py`
  - degraded 상태 BUY가 broker 주문 endpoint 호출 전 `execution_state_gate`에서 거부되는지 검증한다.
  - degraded 상태 SELL은 정상 제출될 수 있음을 검증한다.
- `tests/integration/test_worker_fill_sync.py`
  - open order가 있는 live fill sync 실패 후 같은 tick의 신규 BUY가 broker submission 전 차단되는지 검증한다.
- `tests/integration/test_worker_capital_tracking.py`
  - capital tracking NAV 조회 실패 후 신규 BUY가 차단되는지 검증한다.
- `tests/integration/test_circuit_breaker_worker.py`
  - 손실 평가에 필요한 mark가 없으면 circuit breaker가 halt하지 않아도 신규 BUY가 보류되는지 검증한다.
- `specs/115-degraded-execution-state/`
  - 스펙, 계획, 연구, 데이터 모델, 계약, quickstart, 체크리스트, 작업표를 추가했다.
  - `completed_candidate_id: candidate-degraded-execution-state`
  - `next_candidate_id: candidate-single-execution-authority`

검증 증거:

- 구현 전 focused regression: `auto_invest.execution.execution_state` 부재로 신규 보호 경로 없음 확인
- 구현 후 focused regression: `8 passed`
- 인접 router/fill sync/capital/circuit breaker/lifecycle/paper/risk suite: `88 passed`
- 전체 테스트: `2621 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- post-merge workflow: deploy `29254832101`, released-work `29254832106`, autonomous-work `29254832523` success
- 보호 범위: live sentinel, capital, whitelist/caps 값, loss budget, 헌법, kernel manifest, 비밀값 변경 없음

남은 미확인·후속 사항:

- 실제 KIS 계좌의 열린 주문, 보유, 서버 프로세스는 조회하지 않았다.
- `SUBMISSION_UNKNOWN` 자동 broker order/execution lookup 복구는 아직 없다.
- cross-process 계좌 잠금과 단일 `ExecutionAuthority`는 스펙 116에서 닫혔다.
- 실제 서버 프로세스와 KIS 계좌 상태는 저장소 코드 작업과 별도로 전수 확인해야 한다.

## 스펙 116 구현 결과

스펙 116은 PR #519로 main에 들어갔다.

변경 요약:

- `src/auto_invest/execution/authority.py`가 live broker write의 단일 권한이 됐다.
- `place_order`와 `cancel_order` 직접 호출은 `ExecutionAuthority` 내부로만 제한했다.
- `src/auto_invest/persistence/migrations/0004_execution_authority_locks.sql`가 계좌별 잠금 테이블을 추가했다.
- `OrderRouter.submit_order`는 live일 때 authority lock을 잡은 뒤 열린 BUY 예약, 저하 상태 gate, K1 cap gate, broker submission을 평가한다.
- Worker lifecycle TTL cancel/requote cancel도 같은 authority를 사용한다.
- 잠금 busy 상태는 broker endpoint에 닿지 않고 `ORDER_REJECTED_BY_GATE`의 `execution_authority_lock`으로 남긴다.
- paper mode와 `rebalance-once --dry-run`은 broker write와 authority lock을 만들지 않는다.

검증 증거:

- 구현 전 focused regression: `ExecutionAuthority` 부재로 실패
- 구현 후 focused regression: `7 passed`
- 인접 authority/router/lifecycle/rebalancer suite: `50 passed`
- 전체 테스트: `2626 passed, 4 skipped`
- 린트: `uv run ruff check src tests` 통과
- 형식: `git diff --check` 통과
- HANDOFF 사실 검증: `uv run python scripts/check_handoff_facts.py` 통과
- strict 하네스: `uv run python scripts/agent_harness_probe.py --strict` 통과
- post-merge workflow: deploy `29256471036`, released-work `29256471028`, autonomous-work `29256471114` success
- 보호 범위: live sentinel, capital, whitelist/caps 값, loss budget, 헌법, kernel manifest, 비밀값 변경 없음

## 필수 검증

```bash
uv run pytest tests/unit/test_execution_authority.py tests/unit/test_live_order_path.py tests/integration/test_order_router.py tests/integration/test_worker_order_lifecycle.py tests/integration/test_spec_032_live_rebalancer.py
uv run pytest tests/unit/test_execution_state.py tests/integration/test_worker_fill_sync.py tests/integration/test_worker_capital_tracking.py tests/integration/test_circuit_breaker_worker.py

uv run pytest
uv run ruff check src tests
git diff --check
uv run python scripts/check_handoff_facts.py
uv run python scripts/agent_harness_probe.py --strict
python3 scripts/check_pr_quality_gate.py /tmp/pr-body-116.md
```

위험 동작 부재도 별도로 확인한다.

```bash
rg -n "ExecutionAuthority|execution_authority_lock|candidate-single-execution-authority" src tests specs/116-single-execution-authority
git diff --name-only | rg 'automation/.*\\.request|deploy/.*portfolio|whitelist|caps|constitution|kernel' && exit 1 || true
```

## 풀 리퀘스트 분할 원칙

- 스펙 111에는 라이브 진입점 봉쇄만 포함한다.
- 주문 재시도와 주문 상태기계는 별도 PR이다.
- 체결 원장과 포지션 캐시는 별도 PR이다.
- 노출 예약과 계좌 잠금은 별도 PR이다.
- 저하 상태와 단일 실행 권한은 별도 PR로 닫혔다. 스펙 115는 저하 상태, 스펙 116은 단일 실행 권한과 계좌별 broker-write 잠금을 닫았다.

각 PR은 독립적으로 안전성을 높이고, 중간 상태에서도 기존보다 위험해지지 않아야 한다.

## 남은 미확인 사항

다음은 저장소 코드만으로 확인하지 못했다.

- 운영 서버에서 현재 실행 중인 `auto-invest` 프로세스 수
- systemd와 분리 프로세스로 시작된 오래된 라이브 워커 존재 여부
- GitHub Actions의 현재 비밀값과 Environment 보호 규칙
- KIS 계좌의 현재 열린 주문과 실제 보유 상태
- `operator-design` 최근 예약 실행 여부와 결과

각 실행 안전성 스펙은 위 상태를 추측하지 않고, 저장소 코드상 확인 가능한 안전 불변식만 닫는다.

## 최종 보고 형식

코덱스는 완료 시 다음 순서로 보고한다.

1. 핵심 결론
2. 닫은 실행 안전성 위험
3. 일부러 남긴 후속 위험과 대체 경로
4. 테스트와 하네스 결과
5. 안전 경계와 돈 경로 영향
6. 실행하지 않은 실제 돈 검증
7. 다음 스펙 후보와 우선순위

“안전해졌다”라고만 말하지 말고, **어떤 실패 모드가 사라졌고 어떤 테스트가 그 부재를 증명하는지**를 적는다.
