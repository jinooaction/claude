# HANDOFF 089 — 공개 데이터 수집·교차 검증 확장 (2026-07-02 KST)

main 코드 베이스라인: `d381199`(PR #455). 이 작업은 자율 작업 실행 루프가 고른 `candidate-facf2fa31834`를 처리한 등급 2 운영 보정이다. 연구 전용 공개 데이터 채널에 FRED 그래프 CSV DGS2/DGS10을 추가하고, 재무부 직접 금리와 FRED 금리의 수준 대조 2건을 더해 공개 금리 전송 경로의 조용한 변질을 더 빨리 잡게 했다.

## 무엇이 바뀌었나

- `deploy/public-data.toml`
  - `[fred]` 수집을 추가했다: `DGS2`, `DGS10`, `min_rows=1500`, `max_staleness_days=7`, `user_agent="httpx-default"`.
  - FRED 그래프 CSV DGS10 탐침 중복 호출은 제거했다. DGS2/DGS10 수집 자체가 매일의 측정이 된다.
  - Treasury-vs-FRED `levels` 교차 검증 2건을 추가했다.
- `src/auto_invest/market_data/public_data.py`
  - `fetch_text`에 소스별 user-agent 모드를 추가했다. 기본은 기존 채널 식별 헤더이고, FRED 설정에서만 HTTP 클라이언트 기본 식별 헤더를 쓴다.
  - FRED 공식 API 키 경로는 수집하지 않는다. 키 없는 그래프 CSV DGS2/DGS10만 연구 전용으로 발행한다.
- `.github/workflows/collect-public-data.yml`
  - 주석을 새 운영 사실에 맞게 고쳤다. Stooq와 FRED 공식 API 키 경로는 탐침/후속 선택지이고, FRED 그래프 CSV DGS2/DGS10은 연구 수집이다.
- `tests/unit/test_public_data.py`, `tests/unit/test_collect_public_data_workflow.py`
  - FRED 기본 user-agent 모드, 11개 발행 항목, 5개 교차 검증, FRED-재무부 대조 불변식을 고정했다.
- `specs/085-public-data-cross-validation/`
  - SDD 산출물과 `completed_candidate_id: candidate-facf2fa31834` 계약을 남겼다.

## 운영상 의미

- `collect-public-data`는 검증 통과 시 11개 항목을 발행한다: FRED 2개, Treasury 3개, Cboe VIX 1개, BLS 2개, DBnomics 3개.
- `summary.json`의 교차 검증은 5개가 된다: CPI 원본-vs-미러 1개, Treasury-vs-DBnomics H.15 2개, Treasury-vs-FRED 2개.
- FRED 실패는 항목 단위 fail-soft로 남고, 해당 대조는 `SKIPPED` 또는 `FAIL`로 드러난다. 다른 공식 소스 발행은 계속된다.
- 라이브 매매 신호는 계속 KIS 데이터만 사용한다. 이 sidecar는 연구·백테스트·검증 전용이며 live DB, 주문, 자본 배분, whitelist/caps, live 전략을 바꾸지 않는다.

## 배포 후 실제 실행 증거

- PR #455 merge commit: `d381199fe34afa43869c327afc8adfcc32c2d57a`
- feature commit: `f84e478c8850183d24ce47e66067857912ec9819`
- `Collect public data (research)` run `28596926048`: success, commit `d381199`, trigger `push`
- 최신 public-data sidecar:
  - `overall_ok=True`
  - `published=11`
  - `total_items=11`
  - `elapsed_seconds=9.5`
  - `fred:DGS2` rows `13066`, last observation `2026-06-30`
  - `fred:DGS10` rows `16826`, last observation `2026-06-30`
  - Treasury-vs-FRED DGS2 overlap `2373`, agree `100.00%`
  - Treasury-vs-FRED DGS10 overlap `2373`, agree `100.00%`
- `Released work ledger` run `28596925315`는 이 handoff가 T021을 닫기 전 PR #455 main push에서 실행됐으므로, 그 시점에는 spec 085를 건너뛴 것이 정상이다. 이 handoff가 T021을 닫는다. docs/spec-only handoff merge 뒤 다음 `released-work` run은 `candidate-facf2fa31834`를 포함해야 한다.
- 이 handoff 브랜치에서 `released_work_probe.py --repo-root .`를 재현하면 released_count `6`이고, `candidate-facf2fa31834`가 `specs/085-public-data-cross-validation/contracts/public-data-fred-cross-check.md`의 `completed_candidate_id` 근거로 `released` 처리된다.

## 안전 경계

- 위험 등급: 2(운영 데이터 채널 보정)
- 실제 주문 실행: 없음
- 브로커 실주문 API 호출: 없음
- 자본 증액, 자본 배분, 허용 종목 확대, 포지션 한도 완화, live 전략 교체, live sentinel 변경: 없음
- 헌법, 커널 목록, 주문 제한, 감사 로그 schema, 비밀값 저장, 외부 유료 서비스 변경: 없음
- `httpx-default` user-agent 모드는 FRED 그래프 CSV DGS2/DGS10에만 설정으로 한정된다. 다른 소스의 기존 채널 식별 헤더는 그대로다.

## 검증

PR #455 머지 전:

- `uv run pytest tests/unit/test_public_data.py tests/unit/test_collect_public_data_workflow.py` -> 54 passed
- `uv run auto-invest collect-public-data --config deploy/public-data.toml --out-dir <tmp> --json` -> `overall_ok=true`, `published=11`, cross_checks 5건 PASS
- `uv run pytest` -> 2438 passed, 4 skipped
- `uv run ruff check src tests` -> All checks passed
- `uv run python scripts/check_handoff_facts.py` -> OK
- `uv run python scripts/agent_harness_probe.py --strict` -> OK (14/14)
- PR 품질 관문 -> success

PR #455 머지 후:

- `origin/automation/public-data:LAST_RUN.md` -> run `28596926048`, `overall_ok=True`, `published=11`, cross_checks 5건 PASS
- `uv run ruff check src tests` -> All checks passed
- `uv run pytest -q`는 처음에 2개 테스트가 실패했다. 원인은 `HANDOFF.md`가 아직 #455 이전 main 커밋을 가리킨 것이며, 이 handoff가 고치는 낡은 HANDOFF 실패다.

## 다음 세션 한 줄

스펙 085는 공개 데이터 연구 채널에 FRED DGS2/DGS10과 재무부 대조를 추가했고, GitHub Actions 실제 public-data run에서 11개 발행과 5개 대조 PASS를 확인했다. 이 handoff가 merge되면 `candidate-facf2fa31834`도 `released-work` 완료 후보로 소비되어 다음 자율 작업 선택에서 반복되지 않아야 한다.
