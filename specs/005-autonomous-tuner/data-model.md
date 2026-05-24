# Phase 1 Data Model — Autonomous Tuner (스펙 005)

전부 frozen dataclass(불변) + 결정론적. 새 SQLite 테이블 없음(감사 로그 재사용). 단위는 기존 `Decimal` 정의를 따른다.

## 1. `AuthorityTier` (Literal)

```python
AuthorityTier = Literal["L1", "L2", "L3", "L4"]
```

- **L1**: 자동 적용(저위험·가역). v1 적용 노브: KPI 임계값 조이기.
- **L2/L3**: 캐너리 후보 기록만(튜너가 동기 통과 안 함).
- **L4**: Kernel 터치 — 자동 적용 거부, 포렌식 콜아웃.

## 2. `ProposedChange` (frozen dataclass)

후보가 제안하는 구체적 변경.

| 필드 | 타입 | 의미 |
|------|------|------|
| `kind` | `Literal["threshold_tighten", "proposal_only"]` | `threshold_tighten`=적용 경로 있음(L1), `proposal_only`=감지만(적용 노브 없음) |
| `target_paths` | `tuple[str, ...]` | 이 변경이 건드릴 repo-상대 파일 경로(분류 입력) |
| `config_key` | `str \| None` | 노브 키(예: `"latency_p95_ms.tier_b"`) |
| `old_value` | `str \| None` | 이전값(문자열 Decimal, 가역성·감사용) |
| `new_value` | `str \| None` | 새값(클램프 적용 후) |

## 3. `CandidateChange` (frozen dataclass)

탐지 규칙 1건의 발화 결과(분류 전).

| 필드 | 타입 | 의미 |
|------|------|------|
| `candidate_id` | `str` | 결정론적 id: `f"{rule}:{kpi}"` (같은 입력 → 같은 id) |
| `detection_rule` | `str` | 발화 규칙명(`threshold_tighten`/`cost_drift`/`cache_miss`/`latency_degradation`) |
| `kpi_name` | `str` | 관측 KPI |
| `observed_value` | `str` | 관측값(문자열 Decimal) |
| `observed_tier` | `str` | 관측 Tier(A/B/C/N/A) |
| `window` | `str` | 윈도(`"7d"`/`"30d"`) |
| `proposed` | `ProposedChange` | 제안 변경 |
| `rationale` | `str` | 사람이 읽는 근거 |
| `measurement_sample` | `int` | 윈도 표본 수(헌법 X 게이트 입력) |

## 4. `Classification` (frozen dataclass)

`CandidateChange`에 부여된 권한 등급.

| 필드 | 타입 | 의미 |
|------|------|------|
| `candidate` | `CandidateChange` | 분류 대상 |
| `tier` | `AuthorityTier` | 최종 등급 |
| `kernel_groups` | `tuple[str, ...]` | 매칭된 Kernel 그룹(비었으면 비커널) |
| `reason` | `str` | 분류 근거(예: `"kernel touch: K1_position_sizing → forced L4"`) |

**분류 규칙(`classify.py`)**:
1. `kernel_diff_check(candidate.proposed.target_paths, manifest)` 호출.
2. `not report.is_clean` → `tier="L4"`, `kernel_groups=report.touched_groups`, reason="kernel touch ... → forced L4". (방어 심층화 — FR-A05)
3. Kernel 비교집합일 때 1차 등급: `threshold_tighten`(config TOML, 비커널) → `L1`. `proposal_only`(적용 노브 없음) → 변경 종류·대상에 따라 기본 `L2`(프롬프트/파라미터급) 또는 감지-only는 `L1` 후보지만 적용 노브 없음으로 "proposal". v1 탐지 규칙은 전부 `config/` 또는 감지-only라 비커널 1차 등급은 L1.
4. **`kernel.toml`·`constitution.md`가 target_paths에 있으면**(K_meta) → L4 + "튜너는 K-meta를 수정하지 않음"(FR-A06). 튜너는 이런 후보를 **생성하지 않으나**, 외부 주입 방어로 분류기에서도 강제.

## 5. `SkipReason` (Literal)

```python
SkipReason = Literal["market_hours", "insufficient_measurement", "already_applied_this_session", "no_apply_path", "non_l1_tier"]
```

## 6. `AppliedChange` (frozen dataclass)

실제 적용된 L1 변경.

| 필드 | 타입 | 의미 |
|------|------|------|
| `candidate_id` | `str` | 원 후보 |
| `config_key` | `str` | 변경된 키 |
| `old_value` | `str` | 이전값 |
| `new_value` | `str` | 새값 |
| `audit_seq` | `int` | 기록된 `AUTO_TUNED_L1` 감사 행 seq |

## 7. `TunerRunResult` (frozen dataclass)

한 번의 `tune` 실행 산출물(→ `auto-tuner-report.json`).

| 필드 | 타입 | 의미 |
|------|------|------|
| `session_date` | `str` | 기준 날짜(`--as-of` 또는 오늘) |
| `generated_at_utc` | `str` | 생성 시각 |
| `mode` | `Literal["dry_run", "apply"]` | 실행 모드 |
| `candidates` | `tuple[Classification, ...]` | 감지·분류된 전 후보 |
| `applied` | `tuple[AppliedChange, ...]` | 적용된 L1 변경(dry-run이면 빈 튜플) |
| `canary_entered` | `tuple[Classification, ...]` | L2/L3 후보(기록만) |
| `awaiting_human_merge` | `tuple[Classification, ...]` | L4 후보(Kernel, 인간 머지 대기) |
| `skipped` | `tuple[tuple[str, SkipReason], ...]` | (candidate_id, 스킵 사유) |

## 8. 튜닝 가능 노브 레지스트리 (`knobs.py`)

```python
@dataclass(frozen=True)
class ThresholdKnob:
    kpi_name: str           # e.g., "latency_p95_ms"
    config_path: Path       # config/llm_kpi_thresholds.toml
    step_fraction: Decimal  # 0.2
```

- `compute_tighten(entry: ThresholdEntry) -> Decimal | None`: R-5 수학으로 새 `tier_b` 계산. 조일 여지 없으면(이미 Tier A 경계) `None`.
- `apply_threshold(config_path, kpi_name, new_tier_b) -> tuple[str, str]`: TOML을 읽어 `[kpi_name].tier_b`만 교체, **원자적 쓰기**(임시 파일 + `os.replace`). 반환 `(old, new)`. 다른 키·다른 KPI·주석은 보존(`tomli_w` round-trip 또는 최소 라인 교체).

## 9. K4 추가-전용 감사 페이로드 (`persistence/audit.py`)

`EventType` 리터럴 + `AnyPayload` union에 4종 추가. 전부 추가-전용, 마이그레이션 불필요.

```python
class AutoTunedL1Payload(AuditPayload):
    event_type: Literal["AUTO_TUNED_L1"] = "AUTO_TUNED_L1"
    session_date: str
    detection_rule: str
    kpi_name: str
    config_key: str          # "latency_p95_ms.tier_b"
    old_value: str
    new_value: str
    tier_before: str
    tier_after: str
    window: str

class AutoTunedL2CanaryEnteredPayload(AuditPayload):
    event_type: Literal["AUTO_TUNED_L2_CANARY_ENTERED"] = "AUTO_TUNED_L2_CANARY_ENTERED"
    session_date: str
    candidate_id: str
    authority_tier: Literal["L2", "L3"]
    detection_rule: str
    proposed_change: str     # 사람이 읽는 요약
    target_paths: list[str]

class AutoTunedL4ForensicPayload(AuditPayload):
    event_type: Literal["AUTO_TUNED_L4_FORENSIC"] = "AUTO_TUNED_L4_FORENSIC"
    session_date: str
    candidate_id: str
    detection_rule: str
    kernel_groups: list[str]
    target_paths: list[str]
    reason: str

class AutoTunerRunPayload(AuditPayload):
    event_type: Literal["AUTO_TUNER_RUN"] = "AUTO_TUNER_RUN"
    session_date: str
    mode: Literal["dry_run", "apply"]
    candidates_count: int
    applied_count: int
    canary_count: int
    l4_count: int
    skipped_count: int
```

**멱등 dedup 쿼리(R-8)**: 적용 전
```sql
SELECT COUNT(*) FROM audit_log
WHERE event_type='AUTO_TUNED_L1'
  AND json_extract(payload_json,'$.kpi_name')=?
  AND json_extract(payload_json,'$.session_date')=?
```
> 0 이면 skip(`already_applied_this_session`).

## 10. 상태 흐름 (runner)

```
compute snapshots(7d, 30d, per-day) 
  → detect.run() → [CandidateChange]
  → classify.run(each, manifest) → [Classification]
  → split by tier:
      L1 + threshold_tighten:
        gate: market_hours? → skip(market_hours)
        gate: sample < MIN_SAMPLE? → skip(insufficient_measurement)
        dedup: applied this session? → skip(already_applied_this_session)
        compute_tighten None? → skip(no_apply_path)
        else (mode==apply): apply_threshold + append(AUTO_TUNED_L1) → AppliedChange
      L2/L3: append(AUTO_TUNED_L2_CANARY_ENTERED) → canary_entered
      L4: append(AUTO_TUNED_L4_FORENSIC) → awaiting_human_merge
  → append(AUTO_TUNER_RUN summary)
  → build TunerRunResult → write auto-tuner-report.json (if output_root)
```

dry-run: 분류·게이트까지 동일하게 평가하되 `apply_threshold`·`append(AUTO_TUNED_L1)`을 실행하지 않는다(SC-A03). `AUTO_TUNER_RUN` 요약은 dry-run에서도 기록할지 — **dry-run은 어떤 감사도 쓰지 않는다**(read-only 보장, SC-A03 단순화). `AUTO_TUNED_L2/L4` 후보 기록도 apply 모드에서만. dry-run은 순수 분석.
