# HANDOFF 067 — 자율 고도화 루프 설계 (2026-06-28 KST)

main 베이스라인: `8f9a99f`(PR #400). 운영자는 데이터 수집, 데이터 분석, 전략 설계,
포트폴리오 설계, 실시간 매매, 회고, 에이전트 운영 전 영역에서 지금부터 영구적으로 돈 버는
능력과 검증 능력을 복리화하는 자동 자율 성장 루프를 원한다고 지시했다. 이 루프는 기다리는
시장 관측 시간을 채우는 보조 장치가 아니라 상시 동작하는 성장 엔진이다. 이번 작업은
실주문·자본·전략 설정을 바꾸지 않고, 그 목표를 안전하게 구현할 수 있는 스펙 067 SDD 산출물을
만든 등급 2 운영 설계 변경이다.

## 무엇이 바뀌었나

- `specs/067-autonomous-evolution-loop/spec.md`: 전 영역 고레버리지 돌파 후보 발굴, 안전한 실험 설계,
  기존 게이트를 통한 승격, 학습 기록·생존 감시를 사용자 시나리오와 요구사항으로 고정했다.
- `specs/067-autonomous-evolution-loop/plan.md`: 첫 구현 슬라이스를 read-only 스캔, 돌파 후보 점수화,
  학습 장부, 최신 실행 sidecar, pipeline liveness 편입으로 제한했다.
- `specs/067-autonomous-evolution-loop/tasks.md`: 구현 작업 33개를 T001부터 T033까지
  실행 순서와 독립 검증 기준으로 나눴다.
- `research.md`, `data-model.md`, `quickstart.md`, `contracts/evolution-loop.md`,
  `checklists/requirements.md`를 함께 남겼다.
- `.specify/feature.json`과 `CLAUDE.md` Speckit 포인터가 `specs/067-autonomous-evolution-loop`를
  가리킨다.

## 현재 운영 상태

- 구현은 아직 시작하지 않았다. 다음 구현 세션은 `specs/067-autonomous-evolution-loop/tasks.md`
  T001부터 진행하면 된다.
- 스펙 067의 첫 구현 범위는 읽기 전용이다. evidence 수집, 고레버리지 돌파 후보 발굴,
  실험 계획, 학습 장부, latest-run sidecar, liveness 편입을 만든다.
- 자동 고도화 루프는 기존 스펙 005 자율 튜너, 스펙 055 자율 재지정, 스펙 050 자본 사다리,
  스펙 062 money-path, 스펙 064 opportunity feedback, 스펙 051 pipeline liveness를 대체하지 않는다.
  위에 얹혀 "무엇이 장기 수익력·증거 품질·자본 경로·안전성·학습 속도를 가장 크게 키우는지"를
  정하는 상위 루프다.
- 현재 micro GTAA 돈 경로 상태는 이 작업으로 바뀌지 않았다. 기존 handoff 기준대로
  `armed:false`, money-path `PREVIEW_ONLY`, `latest_intent_loss` 차단 상태를 먼저 읽어야 한다.

## 안전 경계

- 위험 등급: 2(운영 설계·SDD 포인터 변경)
- 실제 주문 실행: 없음
- micro GTAA 재무장: 없음
- 자본 증액, 허용 종목 확대, live 전략 교체: 없음
- 주문 라우터, 포지션 한도, whitelist, 손실 브레이커, 감사 로그, 비밀값, K1/K2/K4/K5/K6 코드,
  헌법, 커널 목록 변경: 없음
- 스펙 067 요구사항은 자동 루프가 주문, 자본, whitelist, caps, 실거래 모드, live 전략 교체를
  직접 수행하지 못하도록 명시한다. 전략 교체는 스펙 055 5중 게이트, 자본 증액은 스펙 050
  자본 사다리와 운영자 소유 낙폭 예산 밖에서 처리하지 않는다.

## 검증

PR #400 머지 전:

- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- `git diff --cached --check` → clean
- tasks 형식 검사 → 33개 task 통과
- `.specify/feature.json` 산출물 경로 검증 → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- PR #400 품질 관문 → success, mergeable `CLEAN`, merge 방식으로 main에 병합

머지 후 handoff 갱신 전:

- `uv run pytest -q`는 `HANDOFF.md`가 아직 #400 main commit을 모른다는 이유로
  하네스 관련 2건이 실패했다. 이는 코드 실패가 아니라 이 handoff 갱신이 해결해야 하는 stale
  handoff 상태다.

handoff 갱신 후:

- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest -q` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

스펙 067은 "지금부터 영구적으로 전 영역 고레버리지 돌파 후보를 찾고 안전한 실험으로 승격하는
read-only 상위 성장 루프"의 설계다. 구현은 아직 시작하지 않았으므로, 다음 세션은
`specs/067-autonomous-evolution-loop/tasks.md`의 T001부터 시작한다.
