# Research — Tuner L2/L3 → Hardened-Canary Auto-Submission

Phase 0. 모든 NEEDS CLARIFICATION 해소 + 핵심 통합 결정 기록.

## R1. 후보를 캐너리에 어떻게 넘기는가 (git rev 구체화)

**Decision**: L2/L3 후보를 **git plumbing(임시 인덱스 + commit-tree)** 으로 임시 후보
커밋 SHA 로 만든다. 작업트리·실제 인덱스·브랜치를 건드리지 않고, 원격으로 푸시하지
않으며, ref 도 만들지 않는다(루스 객체는 무해, 추후 git GC 대상).

절차(후보 1건):
1. 임시 인덱스 파일에 `git read-tree HEAD`.
2. 변경된 파일 내용을 `git hash-object -w` 로 블롭 기록.
3. 임시 인덱스에 `git update-index --cacheinfo 100644,<blob>,<path>`.
4. `git write-tree`(임시 인덱스) → 트리 SHA.
5. `git commit-tree <tree> -p HEAD -m "<ephemeral canary candidate>"` → 후보 커밋 SHA.
6. `run_canary(candidate_rev=<후보 SHA>, baseline_rev=HEAD, ...)`.

**Rationale**: `run_canary` 는 후보 rev vs baseline rev 의 git 트리를 `diff_paths`
로 비교하고 리플레이한다(`canary/run.py`, `canary/diff.py`). 후보를 rev 로 줘야 한다.
working-tree 를 고쳐서 커밋하는 방식은 (a) 동시 작업과 충돌, (b) 실패 시 더러운 트리
잔존 위험이 있다. plumbing 방식은 이 둘을 원천 차단 → FR-C12-05·US3(작업트리 무변경,
미푸시) 를 구조적으로 보장.

**Alternatives rejected**:
- working-tree 수정 후 임시 브랜치 커밋: 더러운 트리·정리 실패 위험. 기각.
- `git worktree add`: 디스크·시간 비용 큼, 백테스트 데이터 경로 의존. 과함. 기각.
- 후보를 rev 없이 "오버레이"로 캐너리에 주입: `run_canary` 가 git rev 비교에 강하게
  묶여 있어 캐너리 내부 대수술 필요(스펙 007 은 건드리지 않는다는 원칙 위반). 기각.

## R2. baseline rev 는 무엇으로

**Decision**: 후보 구체화 시 `baseline_rev = HEAD` 를 **명시**한다. 그러면 `diff_paths`
가 정확히 그 후보 한 파일 변경만 본다(Kernel 교집합·회귀 판정이 깨끗).

**Rationale**: `run_canary` 의 기본 baseline 은 "직전 CANARY_PASSED 또는 origin/main".
그건 후보와 무관한 다른 변경까지 끌고 와 검증을 흐린다. 우리는 "이 후보 변경 한 건이
안전한가"를 보고 싶으므로 baseline=HEAD 로 고정한다.

## R3. v1 구체적 튜닝 노브는 무엇 (cost/latency 드리프트 → 어떤 변경)

**Decision**: v1 의 구체 노브는 **판단 지점 `max_tokens` 축소**다.
- `cost_drift`(usd_per_decision 너무 높음) → 가장 비싼 판단 지점의 `max_tokens` 를
  STEP_FRACTION 만큼 줄임(바닥값 클램프, 가역).
- `latency_degradation`(p95 너무 높음) → 같은 노브(토큰 적을수록 지연↓).
- `cache_miss` → 깨끗한 숫자 노브 없음(스펙 003 캐시는 프롬프트 캐시 구조). **v1
  캐너리 범위 밖**, proposal-only 유지(문서화).

`max_tokens` 값은 현재 `judgment/registry.py` 에 하드코딩돼 있다. 깨끗하게 튜닝
가능하게 하려고 **비커널 config `config/judgment_tunables.toml`** 를 신설하고
`registry.py` 가 폴백 기본값(=현재 하드코딩값)과 함께 읽는다. 파일이 없거나 키가
없으면 현재 값과 동일 → **런타임 동작 무변경**(안전).

**Rationale**: `max_tokens` 는 (a) 비용·지연에 직접·단조적으로 영향, (b) 가역,
(c) 경계 클램프 가능(바닥 토큰 수 아래로 안 내려감), (d) 모델 교체(Haiku↔Sonnet)
보다 품질 영향이 작고 검증 가능. 모델 교체는 더 큰 품질 변화라 **v1 범위 밖**(후속).

**Alternatives rejected**:
- 모델 교체(Sonnet→Haiku)를 v1 노브로: 품질 영향 큼, 백테스트 리플레이가 LLM 판단을
  재현하지 않아 캐너리가 품질 회귀를 직접 못 봄. 후속으로 미룸.
- `registry.py` 파이썬 리터럴 정규식 편집: 프로즌 데이터클래스 소스 편집은 취약.
  config 인덱션이 L1 임계값 패턴(`apply_threshold`)과 일관되고 안전. 채택.

## R4. 후보의 권한 등급(L2 vs L3) 과 분류 일관성

**Decision**: `config/judgment_tunables.toml` 변경은 **LLM 행동(비용/품질)에 영향**
하므로 L2(캐너리, ≥30 거래일 윈도)로 분류한다. `classify.py` 에 이 config 경로를
L2 규칙에 **추가**한다(기존 `/judgment/`·`prompt` → L2 규칙의 자연 확장). Kernel 교집합
후보는 기존대로 무조건 L4 강등 → 캐너리 자동 투입 제외(FR-C12-08).

**Rationale**: 헌법 III(LLM 비용)·VI(모델/프롬프트 변경은 캐너리 단계 필수). L1(즉시
적용)은 부적절 — 이건 검증을 거쳐야 하는 변경이다. 분류 규칙 **추가**이지 완화 아님.

## R5. 캐너리 리플레이 데이터 부재 시 (fail-safe)

**Decision**: 캐너리 입력(`ReplayWindowInputs`)은 인제스트된 과거 데이터셋을 요구한다
(`latest_dataset_dir(history_root)` 가 None 이면 데이터 없음). 데이터가 없으면 캐너리를
**건너뛰고**(skipped) 후보를 "미검증 캐너리 후보"로만 기록하며 튜너는 종료 0 으로 끝낸다.

**Rationale**: 운영 워커/개발 컨테이너에 백테스트 데이터가 항상 있지는 않다. 데이터
부재로 튜너 전체가 실패하면 L1 자동 적용·다른 후보 처리까지 막힌다. `deploy/run-tune.sh`
의 "DB 없으면 종료 0" fail-safe 철학과 일관(스펙 005 후속). FR-C12-09.

## R6. 멱등성 + 오류 격리

**Decision**:
- **멱등**: 같은 세션 날짜·같은 후보(candidate_id)에 대해 이미 후보 기록/검증 이벤트가
  감사 로그에 있으면 중복 투입하지 않는다(기존 L1 의 `_already_applied` dedup 패턴 확장).
- **오류 격리**: 한 후보의 캐너리 호출이 예외/EXIT_INTERNAL 이면 그 후보만
  "internal_error"로 기록하고 `continue` — 다른 후보·전체 튜너 실행은 계속(FR-C12-10).

**Rationale**: 결정론·재현성(SC-A01 계열)과 견고성. 한 후보의 데이터/git 문제가 전체를
무너뜨리면 안 된다.

## R7. 감사 이벤트 (K4 추가-전용)

**Decision**: `persistence/audit.py` 에 추가-전용 신규 이벤트 타입을 더한다:
- `AUTO_TUNED_CANARY_CANDIDATE` — L2/L3 후보를 구조화 기록(P1).
- `AUTO_TUNED_CANARY_VALIDATED` — 캐너리 검증 결과(합격/불합격/건너뜀/내부오류 + 실패
  지표 + canary_run_id)(P2).

기존 `AUTO_TUNED_L2_CANARY_ENTERED` 는 **유지하되 의미를 명확화**(투입 진입 시점 마커).
EventType 리터럴 유니온 + `_PAYLOADS` 레지스트리에 **추가만** 한다(기존 변경 0). 이는
spec 005 커밋 `8bbfca2`(`AUTO_TUNED_*` 4종 추가)와 동일한 **K4 추가-전용 터치 패턴**.

**Rationale**: 헌법 IV·IX.A — 추가-전용. 기존 이벤트·마이그레이션 무수정. 새 이벤트는
JSON payload 라 스키마 마이그레이션 불필요(기존 `payload_json` 컬럼 재사용).

## R8. 자동 승격 절대 금지 (안전 경계)

**Decision**: 캐너리 합격은 `AUTO_TUNED_CANARY_VALIDATED(result=passed)` 로만 기록하고
**거기서 멈춘다**. 라이브 워커 설정·코드를 바꾸지 않고, 배포/승격 이벤트
(`DEPLOY_*`·`STRATEGY_PROMOTED`)를 발생시키지 않는다. 튜너 리포트는 합격 후보 옆에
**"라이브 미승격 — 운영자/스펙 006 게이트"** 를 명시한다.

**Rationale**: 헌법 IX.B-2 — 하드닝 캐너리는 생산 배포 게이트이며 그조차 운영자 게이트.
"검증"과 "배포"의 분리가 이 기능의 안전 경계 그 자체(US3, FR-C12-07, SC-C12-04).

## R9. dry-run 무변경·결정론

**Decision**: dry-run 모드는 후보를 구체화·보고만 하고 git plumbing·캐너리 호출·감사
기록을 일절 하지 않는다(기존 튜너 dry-run 계약과 동일). 같은 입력이면 같은 후보 집합.

**Rationale**: SC-C12-05, 기존 `runner.py` dry-run 계약 유지.
