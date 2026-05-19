# Research: Paper-Trading Daemon (spec 009)

**Phase**: 0 (Outline & Research)
**Date**: 2026-05-19
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

이 문서는 plan.md의 기술적 결정을 뒷받침하는 근거를 모은다. 각 결정은 코드베이스 조사·spec 명확화·constitution 제약을 바탕으로 한다.

---

## R-P1. 단일 차단 지점은 OrderRouter의 broker 호출 한 줄

**Decision**: paper 모드 분기는 `src/auto_invest/execution/order_router.py:347-355` 의 `place_order(self.broker, ...)` 호출 직전에 단 한 곳만 둔다.

**Rationale**:
- `grep -rln "place_order\|broker.order"` 결과, broker 주문 호출은 OrderRouter.submit_order() 한 곳에서만 일어남. 다른 모듈은 OrderRouter를 통하지 않고는 KIS 주문 API에 도달할 수 없음.
- OrderRouter는 게이트 체인(whitelist→halt→per_trade_cap→per_symbol_cap→global_exposure) 통과 직후, broker 호출 직전 위치를 갖는다. 이 위치에 분기를 두면 FR-005(게이트 동등성)와 FR-006(시뮬 fill 기록)을 동시에 만족.
- 분기 위치를 OrderRouter보다 위(예: worker.tick)로 올리면 게이트를 paper 모드에서도 평가하는지가 불명확해짐 → FR-014 위반 위험.
- 분기 위치를 broker 내부로 내리면 ResilientClient 본체가 paper-aware해야 함 → 변경 표면이 넓어지고 K7(외부 API 견고성)에 영향.

**Alternatives considered**:
- (a) broker 객체를 PaperBroker로 교체 (외부에서 inject) — 거부: broker는 ResilientClient + Auth header 조립을 책임지는 객체, 인터페이스가 넓어 PaperBroker가 모방해야 할 표면이 크고 회귀 위험.
- (b) `place_order` 함수에 `dry_run` 파라미터 — 거부: 호출 사이트마다 명시적으로 넘겨야 해서 누락 위험 (FR-013).
- (c) OrderRouter에 mode flag 보관, 호출 직전 1줄 분기 (채택) — 호출 사이트 1곳, 누락 불가능.

**Implication**: 단위 테스트 한 줄(`"paper 모드에서 place_order 호출 = 절대 일어나지 않음"`)이 회귀 가드가 됨. monkeypatch로 broker.post를 raise하도록 설정하고 paper 모드 worker를 100 tick 돌려서 검증.

---

## R-P2. K4 페이로드는 4종 추가 (additive)

**Decision**: `persistence/audit.py`에 4개 페이로드 클래스 추가. 기존 17종(R-P11에 열거)은 무수정.

추가할 페이로드:
- `PaperRunStartedPayload` — paper-run 데몬 시작. `pid`, `config_path`, `ruleset_sha256`, `started_at_utc`.
- `PaperRunStoppedPayload` — paper-run 데몬 종료. `reason` (`normal_shutdown`/`signal_received`/`mutex_conflict`/`crash`).
- `OrderPaperFilledPayload` — 시뮬 체결. `rule_id`, `symbol`, `side`, `qty`, `simulated_fill_price_usd`, `quote_source` (`ask`/`bid`/`last`), `correlation_id`.
- `PaperRunRejectedPayload` — paper-run·live mutex 거부. `attempted_mode` (`paper`/`live`), `conflicting_event_id`, `conflicting_session_started_at`.

**Rationale**:
- FR-011: paper와 live 이벤트가 audit_log에서 명확히 구분되어야 paper-report가 paper만 집계 가능. 페이로드 클래스 이름 = 이벤트 타입 분리.
- spec 008에서도 K4 additive 추가가 IX.D 자율 머지 채널에 해당했음 (CLAUDE.md). 같은 패턴 적용.
- 4종은 P1(데몬 lifecycle 2종) + P1(시뮬 체결) + P2(mutex) 시나리오에 1:1 매핑. 더 적으면 정보 손실, 더 많으면 plan.md scope 위반.

**Alternatives considered**:
- (a) `OrderSubmittedPayload`에 `paper: bool` 플래그 추가 — 거부: 기존 페이로드 수정 = K4 contract 변경 = forensic grep 깨짐.
- (b) 별도 paper_audit_log 테이블 신설 — 거부: spec.md Assumptions의 "동일 SQLite DB 공유" 결정 위반.

**Implication**: migration SQL 파일은 추가하지 않음 (audit_log 테이블 스키마 무변경, payload는 JSON 컬럼). K4 파일 변경 = `persistence/audit.py` 1개. PR 본문에 그 commit hash를 명시한다.

---

## R-P3. 가상 포지션은 audit 이벤트 누적의 derived view

**Decision**: 별도 `paper_positions` 테이블을 만들지 않는다. `paper/virtual_positions.py`가 audit_log의 `OrderPaperFilledPayload` 이벤트를 시간순 누적해 가상 포지션을 derived view로 계산.

**Rationale**:
- FR-008은 "live positions에 직접 쓰면 안 됨"을 요구하지만 별도 테이블을 강제하지는 않음. derived view는 SC-006(live row 무수정)을 100% 만족.
- audit_log는 append-only (constitution IV) → 가상 포지션도 derived면 자동으로 reproducible.
- paper-report는 어차피 audit_log를 SQL aggregation으로 집계 — 가상 포지션도 같은 패스에 포함되어 200ms 예산 안에 들어옴 (R-P5에서 검증).
- 별도 테이블이면 paper-run crash 시 가상 포지션·audit_log 불일치 가능 → derived는 source-of-truth 1개로 본질적 일관성.

**Alternatives considered**:
- (a) `paper_positions` 별도 테이블 — 거부: dual-write 일관성 문제, K4 partial 추가가 K1·K_meta 흉내내는 confusion 유발.
- (b) 가상 포지션 메모리 캐시만 (재시작 시 분실) — 거부: SC-002 일주일 연속 실행 중 데몬 재시작 시 누적 PnL 끊김.

**Implication**: `virtual_positions.py`에는 `recompute_virtual_positions(conn, since: datetime | None)` 같은 순수 함수 1개만 둔다. 캐시 없음.

---

## R-P4. 상호 배타 — audit-log 기반 lightweight mutex

**Decision**: paper-run·live-run의 상호 배타는 시작 시 audit_log를 1번 쿼리해서 확인. SQLite advisory lock·파일 lock 사용하지 않음.

알고리즘:
```
1. SELECT MAX(id) FROM audit_log WHERE event_type IN ('worker_started', 'paper_run_started')
2. 그 id 이후로 같은 worker의 stop 이벤트가 있는지 확인
3. 없으면 → 다른 모드가 실행 중 → PaperRunRejectedPayload 기록, exit code 70
4. 있으면 → PaperRunStartedPayload 기록 후 정상 진행
```

**Rationale**:
- SC-007은 "거부됨 + audit row 기록 + non-zero exit code"만 요구. 강한 atomicity는 불필요.
- 운영자가 사람 손으로 두 명령을 동시 실행할 가능성은 극히 낮음 (race window ~100ms). systemd 자동 재시작이 둘 다 동시에 띄울 가능성도 본 스펙 범위 밖.
- 파일 lock(`fcntl.flock`)이나 SQLite advisory lock은 OS·파일시스템 의존성 추가. audit-log 1쿼리는 의존성 0.
- mutex check 자체가 audit row를 남겨 forensic 가시성 향상 (운영자가 "어제 paper-run 왜 안 떴지?"를 grep로 확인 가능).

**Alternatives considered**:
- (a) SQLite advisory lock — 거부: 같은 DB 파일에 여러 connection이 lock을 공유하는 동작이 OS·sqlite 버전마다 미묘. 검증 비용 큼.
- (b) 파일 lock (`/var/run/auto-invest.pid`) — 거부: Vultr 인스턴스 외 환경에서 권한 문제 가능, 그리고 비정상 종료 시 stale lock 청소가 필요해짐.
- (c) audit-log 기반 (채택) — 운영자 환경 가정과 정확히 일치.

**Implication**: race window가 ~100ms 존재함을 plan.md에 명시. systemd 통합 시 단일 unit으로 어느 모드 1개만 띄우게 강제하면 race가 사실상 0. 본 스펙은 그 systemd 통합을 비범위로 둠.

---

## R-P5. paper-report SQL aggregation 200ms 예산

**Decision**: paper-report는 audit_log를 단일 transaction 안에서 6개 SELECT로 집계. 모든 쿼리는 `(event_type, created_at)` 또는 `(rule_id, event_type)` 인덱스가 있을 때 ~ms급.

쿼리 모양 (개략):
```sql
-- 1. 룰별 시그널 수
SELECT rule_id, COUNT(*) FROM audit_log
  WHERE event_type = 'order_intent' AND created_at >= ? AND created_at < ?
  GROUP BY rule_id;

-- 2. 룰별 시뮬 체결 + 누적 PnL (가상 포지션)
SELECT rule_id, symbol, side, qty, simulated_fill_price_usd, created_at
  FROM audit_log
  WHERE event_type = 'order_paper_filled' AND created_at >= ? AND created_at < ?
  ORDER BY created_at;
-- → Python 메모리에서 종목별 평균 단가·실현 PnL 계산

-- 3. 게이트별 차단 수
SELECT json_extract(payload, '$.gate'), COUNT(*) FROM audit_log
  WHERE event_type = 'order_rejected_by_gate' AND created_at >= ? AND created_at < ?
  GROUP BY 1;

-- 4. 외부 API 오류 수
SELECT COUNT(*) FROM audit_log
  WHERE event_type IN ('order_rejected_by_broker', 'error') AND created_at >= ? AND created_at < ?;

-- 5. 한 번도 trigger 안 된 룰: paper-run 동안 적재된 룰 목록과 (1)의 결과 diff
SELECT DISTINCT json_each.value FROM audit_log, json_each(payload, '$.rule_ids')
  WHERE event_type = 'rule_load' AND created_at >= ? ORDER BY created_at DESC LIMIT 1;

-- 6. trigger 빈도 상위: (1)의 결과를 COUNT 내림차순.
```

**Rationale**:
- SC-003: 200ms 예산. 일주일 ~10만 row 가정.
- 기존 audit_log 인덱스 `idx_audit_event_type_created_at`는 spec 002에서 추가됨 (migrations/0002_token_usage.sql 또는 그 이전). 본 스펙에서 신규 인덱스 추가 없음.
- Python에서 가상 포지션 계산은 ~수천 fill row 대상 → 단순 dict accumulation, 수 ms.

**Alternatives considered**:
- (a) 가상 포지션을 매 tick마다 별도 테이블에 누적 — 거부: R-P3에서 derived view로 결정.
- (b) 단일 거대 JOIN 쿼리 — 거부: 가독성·디버깅 비용 큼. 6개 작은 쿼리가 더 명료.

**Implication**: 측정 가능한 성능 회귀는 pytest 통합 테스트에서 일주일치 합성 데이터(10만 row)로 검증 — SC-003.

---

## R-P6. quote 가격 선택: 매수 ask / 매도 bid / 폴백 last

**Decision**: paper 분기에서 시뮬 fill 가격은 다음 순서로 선택:
1. `side == BUY` → quote.ask_price_usd (있으면)
2. `side == SELL` → quote.bid_price_usd (있으면)
3. 위 둘이 없으면 quote.last_price_usd
4. last_price_usd도 없으면 시뮬 체결 거부 (`PaperRunRejectedPayload` with `reason="no_quote_field"`)

**Rationale**:
- FR-007 명시.
- KIS quote 응답은 보통 ask·bid·last를 다 포함하지만 일부 외화 종목·thinly traded ETF는 한쪽이 0/null일 수 있음.
- 폴백 last는 보수적 추정 — 매수 시 실제로는 ask로 체결될 가능성이 높으므로 시뮬 PnL은 약간 낙관적 (last < ask). 운영자는 paper-report에서 quote_source 필드로 fallback 비율을 확인 가능.

**Alternatives considered**:
- (a) ask/bid 항상 — 폴백 없음. quote 결측 시 데몬 crash. 거부: SC-002 일주일 연속 실행 위반 위험.
- (b) 항상 last — 거부: 시뮬 PnL이 실제 체결과 더 멀어져 신뢰성 하락.

**Implication**: `OrderPaperFilledPayload.quote_source` 필드로 어떤 가격을 썼는지 audit. paper-report는 quote_source 분포를 부속 통계로 제공 (튜닝 피드백 섹션).

---

## R-P7. WorkerSettings paper_mode 플래그 vs 신규 PaperWorker 클래스

**Decision**: `WorkerSettings`에 `paper_mode: bool = False`를 추가하고, `Worker` 클래스가 그 플래그를 OrderRouter 생성 시 전달. 신규 PaperWorker 클래스를 만들지 않는다.

**Rationale**:
- FR-014 "paper 전용 룰 평가 분기 금지"를 코드 구조로 강제. 별도 클래스면 분기 가능성이 커짐.
- Worker는 이미 70여 줄, 분기 1개 추가는 가독성 손실 미미.
- `record_start`/`record_stop`만 paper 모드면 다른 페이로드 사용 — 이 외 tick·reconciliation 등 모든 코드 패스 동일.

**Alternatives considered**:
- (a) `class PaperWorker(Worker)` 상속 — 거부: 메서드 override 표면이 넓어져 회귀 위험.
- (b) Worker를 두 개로 fork — 거부: live 코드와 paper 코드 분기가 즉시 발생.

**Implication**: `WorkerSettings`는 spec 008에서도 손댔던 dataclass — 추가는 default 값 포함이므로 backward-compatible. 기존 호출 사이트 무수정.

---

## R-P8. CLI 표면: 새 서브커맨드 vs `run --paper`

**Decision**: 새 서브커맨드 `paper-run`·`paper-report`를 둔다 (`run --paper`가 아닌).

**Rationale**:
- 운영자가 명령을 한눈에 구분 — `auto-invest run`은 실주문, `auto-invest paper-run`은 시뮬. 오타·습관에 의한 실주문 위험 감소.
- spec 008의 `backtest` 서브커맨드도 같은 패턴.
- typer 데코레이터로 추가 비용 0.

**Alternatives considered**:
- (a) `run --paper` 플래그 — 거부: 운영자가 `run`을 입력 후 `--paper`를 잊으면 실주문. 안전 비용 > 명령어 개수 비용.

**Implication**: `run --dry-run`은 기존대로 smoke test로 남긴다 (spec.md Assumptions). paper-run과 dry-run은 다른 명령이며 다른 의도.

---

## R-P9. mutex 거부 시 exit code

**Decision**: paper-run mutex 거부 → exit code 70 (EX_SOFTWARE 또는 custom). live-run mutex 거부도 동일.

**Rationale**:
- 0(정상), 1(일반 오류), 2(인자 오류)와 구분되는 70대로 mutex 거부 표시. systemd가 재시작 정책에서 구분 가능.
- POSIX `sysexits.h`의 EX_TEMPFAIL(75)도 후보지만 70(EX_SOFTWARE)이 "내부 일관성 오류"에 가장 가까움.

**Alternatives considered**: 1(generic) — 거부: 다른 오류와 섞임.

**Implication**: contracts/paper-run-cli.md에 exit code 표 명시.

---

## R-P10. 시뮬 체결 시점의 quote 신선도

**Decision**: paper 분기에서 시뮬 fill 가격은 OrderRouter.submit_order의 `quote_price_usd` 파라미터를 그대로 사용한다. 분기 직전에 quote를 다시 조회하지 않는다.

**Rationale**:
- worker.tick이 이미 신선한 quote를 가져와 OrderRouter에 넘김. 추가 조회는 KIS rate limit 낭비.
- FR-007의 ask·bid·last 폴백은 별도 메서드(`fetch_quote_full`)가 필요할 수 있지만, 본 스펙에서는 worker.tick의 quote 페치 로직을 확장해 ask/bid를 함께 들고 OrderRouter로 전달하는 방식을 채택 (data-model.md에서 정의).

**Alternatives considered**:
- (a) OrderRouter 내부에서 quote 재조회 — 거부: rate limit·일관성·테스트 난이도 모두 증가.

**Implication**: `OrderRequest`에 ask·bid 추가 또는 worker.tick에서 별도 `QuoteSnapshot` dataclass를 OrderRouter에 전달. data-model.md에서 결정.

---

## R-P11. 기존 audit 페이로드 목록 (변경 없음 검증용)

확인된 기존 페이로드 (audit.py grep 결과, R-P2의 "기존 무수정" 약속의 baseline):

WorkerStarted, WorkerStopped, SecretsLoaded, RuleLoad, OrderIntent, OrderSubmitted, OrderRejectedByGate, OrderRejectedByBroker, Fill, Cancel, Error, ReconciliationOk, ReconciliationMismatch, HaltSet, HaltCleared, StrategyPaused, StrategyPromoted, DataQualityIssue, LlmCall, PriceTableLoaded, DeployBlockedKernelTouch, DeployStarted, DeployCompleted, DeployFailed.

이 24종은 본 스펙에서 단 1개도 수정하지 않는다. 4종(R-P2)만 추가.

**Implication**: spec 008의 K4 additive 추가가 audit Union을 확장한 패턴을 그대로 따른다. PR diff에서 audit.py의 변경 라인은 +N 만, 기존 클래스 본문은 0줄 변경.

---

## Open Questions (post-research)

없음. R-P1~R-P11이 spec.md의 모든 FR·SC·Edge Case를 커버. Phase 1(data-model·contracts·quickstart)로 진행 가능.

검증: `grep -i "NEEDS CLARIFICATION" specs/009-paper-trading-daemon/*.md` → 결과 0건이어야 함.
