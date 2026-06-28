# HANDOFF 068 — 스펙 067 영구 성장 목표 정정 (2026-06-29 KST)

main 베이스라인: `9e1e492`(PR #402). 운영자가 스펙 067의 목표 표현을 정정했다. 이 루프는
"기다리는 시간을 줄이거나 채우는 장치"가 아니라, 지금부터 영구적으로 데이터 수집·분석·전략
설계·포트폴리오 설계·실시간 매매·회고·에이전트 운영 전 영역에서 돈 버는 능력과 검증 능력을
복리화하는 상시 성장 엔진이다.

## 무엇이 바뀌었나

- `specs/067-autonomous-evolution-loop/spec.md`: 사용자 목표, 사용자 이야기, 기능 요구사항,
  성공 기준, 가정을 "고레버리지 돌파 후보"와 "영구 자율 성장" 기준으로 정정했다.
- `research.md`: 후보를 대기 시간 활용 기준이 아니라 장기 수익력, 증거 품질, 자본 경로,
  안전성, 학습 복리 기준으로 정렬한다는 결정을 추가했다.
- `data-model.md`: `BreakthroughCandidate`, `growth_leverage`, `capability_compounding`,
  `capital_path_alignment`, `evidence_dependency` 필드를 설계 기준으로 세웠다.
- `contracts/evolution-loop.md`, `quickstart.md`, `tasks.md`, checklist: sidecar와 구현 작업이
  `top breakthrough candidates`, `safe high-leverage work`, `evidence dependencies`를 출력·검증하도록
  용어를 정리했다.
- `HANDOFF.md`, `HANDOFF-067-AUTONOMOUS-EVOLUTION-LOOP.md`: 다음 세션용 설명을 같은 기준으로
  고쳤다.

## 현재 운영 상태

- 스펙 067 구현은 아직 시작하지 않았다. 다음 구현 세션은
  `specs/067-autonomous-evolution-loop/tasks.md` T001부터 진행한다.
- 구현자는 T011 후보 점수화를 "병목 제거"나 "대기 시간 활용"이 아니라, 장기 수익력·증거 신뢰도·
  자본 경로 정렬·안전 보존·학습 속도·재사용 복리 기준으로 만들어야 한다.
- 시장 관측 시간은 `evidence_dependency`의 한 종류일 뿐이다. 시장 관측이 필요한 후보가 있더라도
  루프 자체는 멈추지 않고 다른 고레버리지 안전 작업을 계속 고른다.

## 안전 경계

- 위험 등급: 2(스펙·인계 프레이밍 보정)
- 실제 주문 실행: 없음
- micro GTAA 재무장: 없음
- 자본 증액, 허용 종목 확대, live 전략 교체: 없음
- 주문 라우터, 포지션 한도, whitelist, 손실 브레이커, 감사 로그, 비밀값, K1/K2/K4/K5/K6 코드,
  헌법, 커널 목록 변경: 없음
- 스펙 067의 read-only 첫 구현 범위와 기존 스펙 055 재지정 게이트, 스펙 050 자본 사다리 경계는
  그대로 유지된다.

## 검증

PR #402 머지 전:

- `git diff --check` → clean
- `uv run python scripts/check_pr_quality_gate.py --template .github/pull_request_template.md` → OK
- `uv run python scripts/check_handoff_facts.py` → OK
- `uv run python scripts/agent_harness_probe.py --strict` → OK (14/14)
- `uv run pytest` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed
- PR #402 품질 관문 → success, mergeable `CLEAN`, merge 방식으로 main에 병합

handoff 갱신 기준:

- `uv run pytest -q` → 2286 passed, 4 skipped
- `uv run ruff check src tests` → All checks passed

## 다음 세션 한 줄

스펙 067은 "지금부터 영구적으로 전 영역 고레버리지 돌파 후보를 찾고, 안전한 실험과 기존 게이트로
승격하는 read-only 상위 성장 루프"다. 구현은 아직 시작하지 않았으므로 T001부터 진행한다.
