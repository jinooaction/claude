# Data Model — Tuner L2/L3 → Hardened-Canary Auto-Submission

전부 frozen dataclass(불변)·결정론. 단위·숫자는 문자열 Decimal 직렬화로 감사/리포트와
byte-stable. 기존 `tuner/models.py` 스타일을 따른다.

## 1. ChangeKind 확장 (`tuner/models.py`)

```python
ChangeKind = Literal["threshold_tighten", "proposal_only", "max_tokens_reduce"]
```

- `max_tokens_reduce` (신규): 판단 지점 `max_tokens` 를 한 스텝 줄이는 L2 후보.
  `ProposedChange.target_paths = ("config/judgment_tunables.toml",)`,
  `config_key = "<judgment_point>.max_tokens"`, `old_value`/`new_value` 채움.

## 2. CanaryCandidate (신규, `tuner/models.py`)

L2/L3 분류 후보를 캐너리가 평가할 수 있게 구체화한 단위.

```python
@dataclass(frozen=True)
class CanaryCandidate:
    candidate_id: str            # = 원 CandidateChange.candidate_id
    detection_rule: str          # cost_drift | latency_degradation | ...
    authority_tier: AuthorityTier  # L2 | L3
    target_path: str             # config/judgment_tunables.toml
    config_key: str              # "<judgment_point>.max_tokens"
    old_value: str
    new_value: str
    recommended_tier: str        # 캐너리 tier 이름(L2/L3 → 캐너리 bands tier 키)
    recommended_window_days: int # bands[tier].trading_days (≥30 L2 / ≥45 L3)
    measurement_sample: int
    rationale: str
```

- **불변식**: `old_value != new_value`, `new_value` 는 바닥 클램프 이상.
- **결정성**: 같은 Classification 입력이면 같은 CanaryCandidate(LLM 미호출).

## 3. CanaryValidationResult (신규, `tuner/models.py`)

후보 1건을 캐너리에 투입한 결과.

```python
ValidationOutcome = Literal["passed", "failed", "skipped", "internal_error"]

@dataclass(frozen=True)
class CanaryValidationResult:
    candidate_id: str
    outcome: ValidationOutcome
    canary_run_id: str | None        # passed/failed 일 때만
    candidate_rev: str | None        # 임시 후보 SHA(검증 후 ref 없음)
    baseline_rev: str | None         # = HEAD
    failing_metrics: tuple[str, ...] # failed 일 때 밴드 벗어난 지표
    skip_reason: str | None          # skipped 일 때(no_replay_data 등)
    promoted: bool                   # 항상 False(자동 승격 금지 — 명시 기록)
```

- **불변식**: `promoted is False` (FR-C12-07·SC-C12-04). passed 여도 False.
- `outcome == "skipped"` → fail-safe(리플레이 데이터 없음 등), `candidate_rev`/`canary_run_id` None.

## 4. SkipReason 확장 (`tuner/models.py`)

```python
SkipReason = Literal[
    "market_hours", "insufficient_measurement", "already_applied_this_session",
    "no_apply_path", "non_l1_tier",
    "no_replay_data",            # 신규: 캐너리 데이터 없음(fail-safe)
    "already_validated_this_session",  # 신규: 멱등 dedup
]
```

## 5. TunerRunResult 확장 (`tuner/models.py`)

```python
@dataclass(frozen=True)
class TunerRunResult:
    ...                                  # 기존 필드 유지
    canary_candidates: tuple[CanaryCandidate, ...] = ()        # 신규
    canary_validations: tuple[CanaryValidationResult, ...] = () # 신규
```

기존 `canary_entered: tuple[Classification, ...]` 는 유지(하위 호환). 신규 필드는
기본값으로 추가만 → 기존 테스트 무회귀.

## 6. 감사 이벤트 (K4 추가-전용, `persistence/audit.py`)

EventType 유니온 + `_PAYLOADS` 레지스트리에 **추가만**. 기존 이벤트·마이그레이션 무수정.

```python
class AutoTunedCanaryCandidatePayload(AuditPayload):
    event_type: Literal["AUTO_TUNED_CANARY_CANDIDATE"] = "AUTO_TUNED_CANARY_CANDIDATE"
    session_date: str
    candidate_id: str
    detection_rule: str
    authority_tier: str
    target_path: str
    config_key: str
    old_value: str
    new_value: str
    recommended_tier: str
    recommended_window_days: int

class AutoTunedCanaryValidatedPayload(AuditPayload):
    event_type: Literal["AUTO_TUNED_CANARY_VALIDATED"] = "AUTO_TUNED_CANARY_VALIDATED"
    session_date: str
    candidate_id: str
    outcome: str                 # passed|failed|skipped|internal_error
    canary_run_id: str | None
    candidate_rev: str | None
    baseline_rev: str | None
    failing_metrics: list[str]
    skip_reason: str | None
    promoted: bool               # 항상 False
```

- **K4 터치**: 추가-전용 2종. 이 커밋 해시를 PR 본문에 forensic callout(IX.A).
- **자동 승격 금지 측정(SC-C12-04)**: `promoted` 가 payload 에 박혀 항상 False 로 감사됨.

## 7. judgment_tunables.toml (신규 config, 비커널)

```toml
# 판단 지점 튜닝 표면 (비커널). registry.py 가 폴백 기본값과 함께 읽는다.
# 파일/키 없으면 registry.py 의 현재 하드코딩 기본값 사용 → 동작 무변경.
[volatility_assessment]
max_tokens = 256
[daily_summary]
max_tokens = 700
[news_screen]
max_tokens = 128
```

- **폴백 불변식**: 파일 부재 또는 키 부재 → 현재 `registry.py` 값과 동일.
- **바닥 클램프**: 튜너는 `max_tokens` 를 환경 최소(예: 32) 아래로 내리지 않는다.

## 8. 상태 흐름 (apply 모드, 후보 1건)

```
Classification(L2/L3, non-kernel)
  └─ candidate.py: build_canary_candidate() → CanaryCandidate (멱등 미검사)
       └─ audit: AUTO_TUNED_CANARY_CANDIDATE (이미 있으면 skip — already_validated_this_session)
            └─ canary_submit.py:
                 ├─ 리플레이 데이터 없음 → CanaryValidationResult(skipped, no_replay_data)
                 ├─ git plumbing → 임시 후보 rev
                 ├─ run_canary(candidate_rev, baseline_rev=HEAD, tier) → passed|failed
                 └─ 예외/EXIT_INTERNAL → CanaryValidationResult(internal_error)
                      └─ audit: AUTO_TUNED_CANARY_VALIDATED (promoted=False 항상)
```

L4(Kernel) 후보는 이 흐름에 진입하지 않음 — 기존 `awaiting_human_merge` 분기 유지.
dry-run 은 build_canary_candidate 까지만(보고용), 감사·git·캐너리 없음.
