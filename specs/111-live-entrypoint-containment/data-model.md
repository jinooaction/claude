# Data Model: Live Entrypoint Containment

## Overview

이 스펙은 새 영구 데이터베이스 테이블을 요구하지 않는다. 핵심은 기존 설계 결과를 “라이브 배포 결과”가 아니라 **실행 권한 없는 후보와 검증 증거**로 모델링하는 것이다.

구현은 기존 Pydantic 또는 dataclass 패턴을 따르고, JSON 직렬화 가능한 구조를 사용한다.

## 1. DesignCandidate

설계 명령이 생성하는 실행 권한 없는 후보.

| Field | Type | Required | Description |
|---|---|---:|---|
| `candidate_id` | `str` | yes | 안정적인 후보 식별자 |
| `candidate_fingerprint` | `str` | yes | 정규화된 룰 본문의 SHA-256 등 결정론적 지문 |
| `created_at_utc` | `str` | yes | UTC ISO-8601 시각 |
| `source_commit` | `str | None` | no | 후보를 생성한 저장소 커밋 |
| `intent_digest` | `str` | yes | 원문을 노출하지 않는 의도 해시 |
| `rules_path` | `str | None` | no | 후보 TOML 저장 경로 |
| `rules_toml` | `str | None` | no | 호출자 내부 사용용. 로그에는 전체 비밀값 없는 룰만 허용 |
| `authority` | literal `"PROPOSAL_ONLY"` | yes | 실거래 권한 없음 |
| `verification` | `DesignVerificationResult` | yes | 단계별 검증 결과 |

### Invariants

- `authority`는 항상 `PROPOSAL_ONLY`다.
- 후보 생성만으로 live worker PID, broker order id, capital allocation을 만들 수 없다.
- `candidate_fingerprint`는 모든 검증 단계에서 동일해야 한다.
- 원본 자연어 intent는 감사·로그에 기본 저장하지 않는다. 필요 시 민감값 마스킹 후 별도 정책을 따른다.

## 2. VerificationStageResult

한 단계의 검증 결과.

| Field | Type | Required | Description |
|---|---|---:|---|
| `stage` | `static | backtest | paper` | yes | 검증 단계 |
| `status` | `PASS | WAIT | FAIL` | yes | 단계 상태 |
| `reason_code` | `str` | yes | 기계 판독 가능한 이유 |
| `reason_ko` | `str` | yes | 운영자 설명 |
| `candidate_fingerprint` | `str` | yes | 검증한 후보 지문 |
| `evidence_ref` | `str | None` | no | run id, 결과 파일, audit correlation id 등 |
| `observed_at_utc` | `str | None` | no | 증거 생성 시각 |
| `fresh_until_utc` | `str | None` | no | 신선도 계약이 있을 때 만료 시각 |
| `metrics` | `dict[str, object]` | yes | 비밀값 없는 정량 결과 |

### Status Rules

#### PASS

- 해당 단계가 실제 실행됐다.
- 결과가 성공 기준을 충족했다.
- 후보 지문이 일치한다.
- 필요한 경우 증거가 신선하다.

#### WAIT

- 단계가 아직 실행되지 않았다.
- 실행기는 있지만 필수 데이터나 관측이 부족하다.
- 후보는 보존할 수 있으나 aggregate `ok`는 false다.

#### FAIL

- 실행 실패
- 검증 기준 미달
- stub 또는 skipped 결과를 성공으로 표시하려는 경우
- 후보 지문 불일치
- malformed 또는 신뢰할 수 없는 증거
- 명시된 신선도 초과

## 3. DesignVerificationResult

세 단계 결과를 합친 fail-closed 판정.

| Field | Type | Required | Description |
|---|---|---:|---|
| `ok` | `bool` | yes | 세 단계가 모두 PASS일 때만 true |
| `overall_status` | `VERIFIED | WAIT_DYNAMIC_VALIDATION | BLOCKED` | yes | 운영 상태 |
| `candidate_fingerprint` | `str` | yes | 집계 기준 후보 지문 |
| `static_result` | `VerificationStageResult` | yes | 정적 검증 |
| `backtest_result` | `VerificationStageResult` | yes | 백테스트 |
| `paper_result` | `VerificationStageResult` | yes | 모의 운용 또는 paper validation |
| `blocking_reasons` | `tuple[str, ...]` | yes | WAIT 또는 FAIL 원인 |
| `evidence_refs` | `tuple[str, ...]` | yes | 모든 유효 증거 참조 |

### Aggregate Rules

```text
all stage status == PASS
AND all candidate_fingerprint identical
AND all required evidence fresh
=> ok=True, overall_status=VERIFIED

any stage status == FAIL
OR fingerprint mismatch
OR malformed evidence
=> ok=False, overall_status=BLOCKED

otherwise
=> ok=False, overall_status=WAIT_DYNAMIC_VALIDATION
```

`ok=True`와 `backtest_skipped=True` 또는 `paper_run_skipped=True`가 동시에 존재하는 상태는 금지한다. 기존 호환 필드가 남아야 한다면 skipped는 반드시 aggregate failure를 뜻해야 한다.

## 4. IntentPayload

워크플로에서 셸 평가 없이 전달되는 운영자 의도.

| Field | Type | Required | Description |
|---|---|---:|---|
| `encoding` | `utf-8 | base64 | json` | yes | 전달 형식 |
| `payload` | `bytes | str` | yes | opaque data |
| `sha256` | `str` | yes | 전달 무결성 확인 |
| `length_bytes` | `int` | yes | 최대 크기 검증 |

### Invariants

- 셸 `eval` 금지
- 원문을 SSH 명령 문자열에 직접 연결 금지
- 디코딩 후 해시 일치 확인
- 출력 로그에 원문 전체를 자동 노출하지 않음
- 최대 크기를 합리적으로 제한

## 5. DesignCommandPolicy

명령 안전 등록부의 기대 계약.

```json
{
  "name": "design",
  "level": "A2",
  "level_label": "proposal",
  "autonomous_allowed": true,
  "operator_approval_required": false,
  "can_place_order": false,
  "can_change_live_config": false,
  "can_scale_capital": false,
  "can_reassign_strategy": false,
  "writes_db": true,
  "uses_broker": true,
  "uses_llm": true
}
```

`uses_broker`는 계좌 문맥을 읽는 현재 기능을 유지할 경우에만 true다. 읽기조차 제거된다면 false로 낮춘다. 어느 경우든 주문 쓰기 권한은 없다.

## 6. Historical Audit Compatibility

기존 이벤트를 삭제하거나 과거 row를 수정하지 않는다.

- `RULE_DESIGN_REQUESTED`: 계속 사용 가능
- `RULE_DESIGN_COMPLETED`: 후보 생성 완료로 사용 가능
- `RULE_DESIGN_REJECTED`: 검증 실패 또는 운영자 취소로 사용 가능
- `RULE_DESIGN_DEPLOYED`: 새 design 실행에서 더 이상 발생시키지 않음

과거 `RULE_DESIGN_DEPLOYED` row는 역사적 사실로 읽을 수 있어야 한다. 이벤트 union이나 migration을 제거하지 않는다.

## State Transition

```text
REQUESTED
  ├─ generation failure ───────────────> REJECTED
  └─ candidate generated
       ├─ static FAIL ─────────────────> BLOCKED
       ├─ static PASS + dynamic WAIT ──> PROPOSAL_ONLY / WAIT_DYNAMIC_VALIDATION
       ├─ any dynamic FAIL ────────────> BLOCKED
       └─ all PASS ────────────────────> VERIFIED_CANDIDATE

VERIFIED_CANDIDATE
  └─ existing promotion pipeline only; no direct LIVE transition here
```

## No New Persistence Requirement

이번 스펙의 최소 구현은 JSON/Markdown 결과와 기존 후보 파일로 충분하다. 새 DB migration은 만들지 않는다. 별도 후보 저장소가 필요하다고 판단되면 범위를 키우기 전에 기존 candidate factory, released-work, promotion sidecar 구조를 재사용할 수 있는지 먼저 확인한다.
