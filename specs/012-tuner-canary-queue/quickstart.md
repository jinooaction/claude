# Quickstart — Tuner L2/L3 → Hardened-Canary Auto-Submission (spec 012)

## 무엇이 바뀌나 (한 줄)

자율 튜너가 모델·토큰 같은 위험 변경(L2/L3)을 감지하면, 이제 **하드닝 캐너리로
자동 투입해 검증**하고 합격/불합격을 감사 로그·리포트에 남긴다. **합격해도 라이브로
자동 배포하지 않는다** — 승격은 운영자/스펙 006 게이트 전용.

## 운영자 관점

평소처럼 튜너가 자동(오프아워 타이머) 또는 수동으로 돈다:

```bash
auto-invest tune --apply          # 실제 적용 모드(L1 적용 + L2/L3 캐너리 투입)
auto-invest tune                  # dry-run(분석만, 무변경)
```

출력 끝에 캐너리 요약이 추가된다:

```
캐너리 후보 2건 / 합격 1 / 불합격 0 / 건너뜀 1 — 라이브 미승격(운영자 게이트)
```

검증 결과는 감사 로그에서 조회:

```bash
# 캐너리 후보 + 검증 결과
sqlite3 data/auto_invest.db \
  "SELECT event_type, json_extract(payload_json,'$.candidate_id'),
          json_extract(payload_json,'$.outcome'),
          json_extract(payload_json,'$.promoted')
   FROM audit_log
   WHERE event_type LIKE 'AUTO_TUNED_CANARY_%' ORDER BY seq DESC LIMIT 10;"
```

`promoted` 는 **항상 0(False)** — 자동 승격이 일어나지 않았음의 증거.

## 합격 후보를 실제로 올리려면 (운영자 결정)

캐너리 합격은 "안전 검증됨, 승격 대기"일 뿐이다. 실제 라이브 반영은 운영자가
기존 경로로 결정한다(스펙 006 배포 / PR 머지). 이 기능은 **그 직전까지만** 자동화한다.

## 개발자 관점 — 검증

```bash
uv run pytest tests/unit/tuner/ tests/unit/judgment/test_tunables_config.py \
              tests/integration/tuner/test_canary_pipeline.py
uv run ruff check src tests
```

핵심 불변(테스트로 고정):
- **작업트리 무변경**: 튜너 apply 전후 `git status --porcelain` 동일(후보 대상 파일 미변경).
- **미푸시**: 캐너리 검증이 origin 에 새 ref/커밋을 만들지 않음.
- **승격 0건**: 합격 후보가 있어도 `DEPLOY_*`·`STRATEGY_PROMOTED` 이벤트 0건.
- **fail-safe**: 인제스트 데이터 없으면 캐너리 건너뜀(skipped) + 튜너 종료 0.
- **결정론**: 같은 입력 dry-run 두 번 → 같은 후보 집합, 무변경.

## 안전 경계 요약

- 캐너리 검증 = 과거/합성 데이터 **시뮬레이션** (실거래·실배포 아님).
- 합격 ≠ 배포. 라이브 승격은 운영자/스펙 006 게이트 전용(헌법 IX.B-2).
- Kernel 터치 후보는 L4 강등 → 캐너리 자동 투입 제외(인간 머지 경로 유지).
- 추가-전용 감사(K4) 2종만 추가, 기존 이벤트·마이그레이션 무수정.
