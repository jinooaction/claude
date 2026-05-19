# Feature Specification: 자동 룰 설계자 (Autonomous Rule Designer)

**Feature**: 010-auto-rule-designer
**Status**: Draft
**Date**: 2026-05-19

## Why

운영자(mason)의 최상위 목표는 **자율 수행**(constitution v3.0.0 IX.D). 그러나 spec 001~009는 "룰을 안전하게 실행하는 엔진 + 검증 도구"까지만 만들었고, **"어떤 룰로 거래할지" 자체는 운영자가 직접 `config/rules.toml`에 적어야 한다**. 이건 자율 수행의 정반대다.

운영자가 본질을 짚어준 결과 룰 설계 자체를 자동화하기로 결정했다. 이 스펙은 그 누락된 단계를 채운다 — 운영자가 자연어 한 줄로 의도만 적으면 시스템이 룰을 자동 생성하고, 자동 검증한다.

## What

운영자가 자연어 한 줄로 의도를 적어 주면 시스템이 다음을 한다:

1. KIS REST API로 운영자의 실제 계좌 잔고·기존 보유 종목을 자동 조회한다.
2. Claude API가 운영자 의도 + 계좌 상태를 받아서 `rules.toml`을 자동 생성한다.
3. 자동 검증한다 — 백테스트(spec 008) + 일주일 paper-run(spec 009).
4. 검증 통과 시 운영자에게 한글 요약 보고. 운영자가 "OK" 한 줄 답하면 자동 배포(`auto-invest run`).
5. 검증 실패 시 운영자에게 한글 보고 + Claude에게 룰 재설계 자동 시도 (최대 3회).

핵심 명령: `auto-invest design --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"`.

## User Stories

### P1 — 운영자가 한 줄 의도로 룰 자동 생성 + 검증

**As** 운영자 (자율 수행을 원함),
**I want** 자연어 한 줄로 투자 의도를 적으면 시스템이 룰을 자동 생성하고 검증해주기를,
**so that** 룰 설계라는 시간 소모적 의사결정을 시스템에 위임할 수 있다.

**Acceptance scenarios**:

1. **Given** 운영자가 `auto-invest design --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"` 실행,
   **When** 시스템이 KIS 잔고 조회 + Claude로 룰 생성 + 백테스트·paper-run 검증을 한 사이클 진행,
   **Then** 최종적으로 다음 셋 중 하나가 stdout/한글 보고로 나옴:
   - **검증 통과**: 생성된 룰 요약 + 백테스트 결과(수익률·최대 손실) + paper-run 통계 + "이 룰로 라이브 시작하시려면 'OK'를 답해주세요."
   - **검증 실패 + 재설계 진행 중**: "1회차 룰이 X 조건에서 실패. 재설계 시도 N/3 중..."
   - **3회 재설계 후도 실패**: "자동 룰 설계에 실패했습니다. 의도를 좀 더 구체적으로 다시 알려주세요." + 마지막 시도의 실패 사유.

2. **Given** 운영자가 의도를 모호하게 적음 ("위험 보통"의 정량 정의 없음),
   **When** 시스템이 Claude로 룰 생성을 시도,
   **Then** Claude가 합리적 기본값으로 해석(예: max_drawdown 5%, 종목당 비중 20%)하고 그 해석을 audit_log에 명시적으로 기록 + 한글 보고에 "위험 '보통'을 max_drawdown 5%로 해석했습니다."로 운영자에게 안내.

### P2 — 검증 통과 후 운영자 OK 한 줄로 라이브 시작

**As** 운영자,
**I want** 검증 결과를 보고 한 줄 "OK"만 답하면 시스템이 라이브 거래를 자동으로 시작하기를,
**so that** 룰 적용을 위해 별도 명령을 외울 필요 없다.

**Acceptance scenarios**:

1. **Given** P1에서 검증 통과 보고가 나옴 + 운영자가 같은 세션에서 "OK" 또는 "ok" 또는 "예" 입력,
   **When** 시스템이 OK 신호를 받음,
   **Then** 자동으로 라이브 worker가 시작됨 + 시작 audit 이벤트 기록 + 운영자에게 "라이브 시작됨. 현재 자본: ...USD"라는 한글 보고.

2. **Given** P1 검증 통과 보고 후 운영자가 "no" 또는 "취소" 또는 무응답,
   **When** 시스템이 거부/타임아웃 감지,
   **Then** 라이브 시작 안 함 + 생성된 룰은 audit_log에만 보관(rules.toml 기록 안 함) + 운영자에게 "라이브 시작 안 됨. 룰은 audit_log에 보관됨."이라는 한글 보고.

### P3 — Claude의 해석 매개변수를 audit_log에 명시적 기록

**As** 운영자 (자율 수행 중 사후 검토를 원함),
**I want** Claude가 운영자 의도를 해석할 때 사용한 정량적 매개변수를 모두 audit_log에 박아두기를,
**so that** 일주일·한 달 후 룰 동작이 의도와 다르게 보일 때 사후 추적이 가능하다.

**Acceptance scenarios**:

1. **Given** 운영자 의도 + Claude 해석 결과로 룰이 생성됨,
   **When** 시스템이 `RULE_DESIGN_REQUESTED` + `RULE_DESIGN_COMPLETED` 두 audit 이벤트 기록,
   **Then** `RULE_DESIGN_COMPLETED`의 payload에 다음이 포함:
   - 원본 자연어 의도 (글자 그대로).
   - Claude가 해석한 정량 매개변수 (예: `{"max_drawdown_pct": 5, "per_symbol_pct": 20, "universe": ["VOO", "QQQ", ...]}`).
   - 생성된 룰의 전체 텍스트 (TOML 직렬화).
   - Claude 모델 ID + 토큰 사용량 (spec 002 token usage tracking과 연동).
2. **Given** 같은 의도로 시간 두 번 호출,
   **When** 시스템이 룰을 두 번 생성,
   **Then** 두 audit_log에서 운영자가 `git log` 같은 명령으로 두 시점의 해석 매개변수 차이를 비교 가능.

## Functional Requirements

- **FR-001**: 시스템은 `auto-invest design --intent "..."` 형태의 CLI 명령 1개를 제공한다. `--intent`는 자연어 문자열 한 줄.
- **FR-002**: 명령 실행 시 시스템은 KIS REST API로 운영자의 실제 계좌 잔고(예수금)와 기존 보유 종목 리스트를 자동 조회한다. spec 001의 KIS 연동 모듈을 재사용한다.
- **FR-003**: Claude API 호출은 constitution III의 새 judgment point `rule_design`에서만 일어난다. 시스템 prompt에 운영자 의도 + 계좌 상태 + 안전 제약(constitution I·II·III·VI 원칙 요약)이 포함되어야 한다.
- **FR-004**: 생성된 룰은 다음 형태의 TOML 텍스트여야 한다: `[caps]`, `[whitelist]`, `[[rules]]` 섹션을 모두 포함한 spec 001 호환 형식.
- **FR-005**: 생성된 룰은 자동으로 다음 두 검증을 통과해야 한다:
  - **백테스트**: spec 008 backtest 엔진으로 최근 N개월 과거 데이터 시뮬 → 최대 손실률·시그널 발생 빈도·게이트 차단 비율이 운영자 의도와 부합.
  - **paper-run**: spec 009 paper-run 데몬으로 일주일 실시간 시장 모의 거래 → 안정성·룰 동작 검증.
- **FR-006**: 검증 합격 지표(예: 백테스트 최대 손실률 < X%, 시그널 발생 일평균 ≥ Y회, paper-run 외부 API 오류율 ≤ Z%)는 운영자가 의도에 명시한 경우 그대로 사용하고, 명시 없으면 Claude 해석 또는 기본값(`config/rule_design_pass_bands.toml` 같은 별도 파일).
- **FR-007**: 검증 실패 시 시스템은 Claude에게 "실패 사유 + 기존 룰 + 운영자 의도"를 다시 전달해 룰을 한 번 재설계하게 한다. 재설계는 최대 3회 자동 시도. 3회 모두 실패 시 운영자에게 한글 보고.
- **FR-008**: 모든 audit 이벤트는 한글로 추적 가능해야 한다. 신규 audit 이벤트 타입: `RULE_DESIGN_REQUESTED`, `RULE_DESIGN_COMPLETED`, `RULE_DESIGN_REJECTED`, `RULE_DESIGN_DEPLOYED`. payload는 contracts/에서 정의.
- **FR-009**: 검증 통과 후 자동 배포 단계는 운영자 1회 확인(OK)을 거친다. spec 007 hardened canary 완성 전까지는 이 1회 확인이 안전 가드. spec 007 완성 후 IX.D 확장으로 자동화 가능 (별도 스펙으로 분리 가능).
- **FR-010**: Claude API 비용은 spec 002의 token usage tracking에 자동 집계되어야 한다. 룰 설계 호출 1회당 한도(예: 입력 ≤ 50KB, 출력 ≤ 10KB)를 spec 002 KPI와 연결.
- **FR-011**: 생성된 룰은 constitution I~VII의 모든 안전망(cap·whitelist·LLM judgment point·append-only audit·시장 시간 가드)을 만족해야 한다. 시스템은 룰 생성 직후 정적 검증(예: cap 게이트 활성화 여부, whitelist에 들지 않은 종목 없음)을 한 번 더 한다.
- **FR-012**: 운영자가 의도를 다시 입력하면(예: 한 달 후 "위험 낮음으로 바꿔") 기존 룰은 그대로 두고 새 룰을 생성해 검증. 운영자가 OK하면 기존 라이브 worker는 graceful stop 후 새 룰로 재시작.
- **FR-013**: 한 호스트에서 `auto-invest design`은 동시 1개만 실행 가능 (자원 충돌 회피). spec 009의 mutex 패턴과 같은 audit_log 기반 가드.
- **FR-014**: 검증 합격까지의 전체 흐름이 일주일(paper-run 7일) 걸리므로, 시스템은 중간 상태를 audit_log에 저장하고 데몬 재시작 후에도 이어서 진행 가능해야 한다.

## Success Criteria

- **SC-001**: 운영자가 자연어 한 줄로 의도를 입력하면 시스템이 24시간 이내(백테스트 + paper-run 1일분)에 첫 검증 결과를 한글 요약으로 보고한다. (paper-run 일주일은 후속 단계지만, 백테스트 + paper-run 1일분으로 빠른 피드백 가능.)
- **SC-002**: 룰 설계 1회 호출의 Claude API 비용이 1달러를 넘지 않는다. 1달러는 spec 002 KPI 기준 입력+출력 토큰 한도 안에서 가능.
- **SC-003**: 자동 생성된 룰 100%가 constitution I~VII 정적 검증을 통과한다 — cap 게이트 활성·whitelist 종목만 포함·LLM 호출은 judgment point만·audit 페이로드 정합·시장 시간 가드 의존성 충족.
- **SC-004**: 운영자 의도가 모호한 경우(예: "위험 보통"만) Claude의 정량 해석이 audit_log에 명시적으로 기록되어, 운영자가 사후 100% 재현 가능. (테스트: 같은 의도 + 같은 계좌 상태로 두 번 호출 시 audit_log 두 row가 정량 매개변수까지 일치.)
- **SC-005**: 검증 통과 후 운영자가 "OK" 한 줄 답하면 5초 이내 라이브 worker가 시작된다.
- **SC-006**: 검증 실패 시 자동 재설계가 최대 3회까지 시도되며, 매 시도의 실패 사유가 audit_log에 한글 메시지로 기록된다.
- **SC-007**: `auto-invest design`이 동시 실행되면 두 번째 호출은 mutex 충돌로 즉시 거부되며 exit code 70이 리턴된다 (spec 009 패턴과 동일).
- **SC-008**: 자동 룰 설계 후 자동 검증 단계에서 KIS 실주문 API는 단 한 번도 호출되지 않는다 (paper-run의 SC-001 보장에 따름).

## Assumptions

- Claude API 키는 운영자의 기존 spec 004 환경(judgment points)에서 이미 구성된 상태.
- KIS 계좌는 운영자가 spec 001에서 이미 검증한 계좌.
- 운영자는 검증 통과 후 OK를 답할 의지가 있다 (자율 수행이 목표지만 자본 100달러 첫 라이브는 1회 확인이 안전).
- 본 스펙은 paper-run 일주일 + backtest 1회까지를 검증 단계로 본다. 더 긴 검증(예: 한 달)은 운영자가 의도에 명시한 경우만.
- 룰 설계의 정확성은 Claude 모델의 한계에 의존한다 — 시스템은 안전망(constitution I~VII)을 통한 후방 검증을 제공하지만, "수익률 최적화"는 보장하지 않는다. 시스템 목적은 "안전한 룰 자동 생성"이지 "최적 룰 자동 생성"이 아니다.
- KIS 계좌 잔고가 0이거나 운영자 의도의 자본보다 작으면 시스템이 한글 경고 후 진행 중단.
- 본 스펙은 미국 상장 주식·ETF만 다룬다. 옵션·채권·해외(미국 외) 시장은 비범위.

## Edge cases

1. **운영자 의도가 빈 문자열**: 시스템이 한글 에러 + exit 2.
2. **KIS API 토큰 발급 실패**: 시스템이 한글 에러 + exit 1, audit_log에 `RULE_DESIGN_REJECTED(reason="kis_token_failed")` 기록.
3. **Claude API 호출 실패 (네트워크/429)**: spec 002의 retry/backoff 사용. 최종 실패 시 audit + 운영자 보고.
4. **Claude가 잘못된 TOML 생성**: 정적 파싱 단계에서 catch → 자동 재설계 트리거 (3회 카운트에 1회 차감).
5. **Claude가 whitelist 위반 종목 포함**: 정적 검증에서 catch → 자동 재설계 트리거.
6. **백테스트 결과가 합격 지표 미달**: 자동 재설계 트리거.
7. **paper-run 도중 SIGTERM**: spec 009 mutex가 처리. design 명령은 audit_log를 보고 상태 복구.
8. **계좌 잔고가 의도 자본보다 작음**: 한글 경고 + design 진행 중단 (`RULE_DESIGN_REJECTED(reason="insufficient_balance")`).
9. **운영자가 의도에 비범위 자산(예: "비트코인", "닛케이 225") 명시**: Claude가 거부 시 자동 재설계 1회 시도 후 한글 보고.

## Non-goals

- 자동 룰 진화(시장 변화에 따른 룰 자동 업데이트) — spec 005 autonomous tuner 범위.
- 100% 자동 배포 (운영자 OK 단계 없음) — spec 007 hardened canary 완성 후 별도 스펙으로 분리.
- 복잡한 자산 클래스 — 미국 주식·ETF만.
- 룰 최적화(수익 극대화) — 안전한 룰 자동 생성이 목적. 운영자가 더 공격적·보수적 룰을 원하면 자연어 의도에 명시.

## Dependencies

- spec 001 (KIS REST 연동) — KIS 잔고 조회.
- spec 002 (telemetry + token usage) — LLM 비용 추적.
- spec 004 (judgment points) — 새 `rule_design` 판단점 추가. **K3 additive 변경**.
- spec 008 (backtest engine) — 백테스트 검증 (in-flight on separate branch).
- spec 009 (paper-run) — paper-run 검증.
- (옵션) spec 007 hardened canary — 완성 후 OK 단계 자동화 가능.
