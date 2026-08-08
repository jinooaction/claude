# 자율 작업 실행 루프 (as of 2026-08-08T09:51:19Z)

읽기 전용 보고입니다. 이 루프는 다음 Codex 작업 패킷만 발행합니다.
주문, 자본 배분, live 설정 변경, 코드 자동 수정, PR 자동 생성은 하지 않습니다.

## 종합 판정

| 항목 | 값 |
|------|-----|
| overall_status | OBSERVATION_WAIT |
| selected_work | wait-for-fresh-evidence |
| title_ko | 새 증거 대기 |
| status | OBSERVATION_WAIT |
| autonomy_level | OBSERVATION_WAIT |
| risk_grade | 0 |
| priority_score | 0 |
| next_action_ko | 다음 scheduled sidecar 갱신 뒤 released-work와 autonomous-work를 다시 읽어 새 EXECUTION_READY 후보가 생겼는지 확인합니다. |
| start_guidance_ko | 현재는 새 코드 작업을 시작하지 말고 다음 sidecar 갱신 증거를 기다린다. |
| completion_gates | 새 sidecar 증거 수집; released-work/autonomous-work 재실행 |

## 실행 가능 후보

- 현재 실행 가능한 안전 후보가 없습니다.

## 승인 필요 또는 억제 후보

| 후보 | 영역 | 상태 | 위험 | 안전 표면 | 이유 |
|------|------|------|-----:|-----------|------|
| wait-for-fresh-evidence | agent_ops | OBSERVATION_WAIT | 0 | - | 실행 가능한 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없습니다. 현재 보이는 후보는 완료 8개와 억제 2개뿐이므로 완료 후보를 다시 선택하지 않고 새 sidecar 증거를 기다립니다. |
| candidate-fd04772a23c5 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-source-diversification-sidecar-bottleneck | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-88a7e7f07361 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-e481b0309206 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-fa66202bf496 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-dff4f9344b02 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-6ee3370e933d | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-facf2fa31834 | analysis | RELEASED | 2 | - | released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다. |
| candidate-1ed634d8bf6d | analysis | SUPPRESSED | 2 | - | learning ledger가 이 후보를 억제했다: 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다. |

## 목적 함수 보정

| 항목 | 값 |
|------|-----|
| objective_version | autonomous-growth-objective-v1 |
| selected_candidate_id | wait-for-fresh-evidence |
| max_ranked_candidates | 10 |
| max_parallel_candidates | 1 |
| max_validation_minutes | 90 |
| requires_handoff_refresh | True |
| requires_pr_quality_gate | True |

### 중단 조건

- operator approval required for safety-impact or grade >=4 work
- missing or malformed required sidecar evidence blocks autonomous start
- full pytest, ruff, handoff fact check, strict harness, or PR quality gate failure blocks merge
- WIP or DO NOT MERGE PR body blocks automatic merge

### 반복 학습 지표

| 지표 | 값 |
|------|-----:|
| ranked_count | 0 |
| suppressed_count | 10 |
| operator_approval_count | 0 |
| released_count | 8 |
| blocked_count | 0 |
| safety_impact_count | 0 |

### 후보 점수

| 후보 | 상태 | 위험 | 총점 | 성장 | 증거 | 검증 | 안전 | 학습 | 설명 |
|------|------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|------|
| wait-for-fresh-evidence | OBSERVATION_WAIT | 0 | 66 | 0 | 100 | 80 | 100 | 85 | 안전 경계 안에서 자율 성장 루프의 반복 판단 비용을 줄이는 후보입니다. |
| candidate-fd04772a23c5 | RELEASED | 2 | 89 | 90 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-source-diversification-sidecar-bottleneck | RELEASED | 2 | 89 | 90 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-88a7e7f07361 | RELEASED | 2 | 89 | 89 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-e481b0309206 | RELEASED | 2 | 89 | 89 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-fa66202bf496 | RELEASED | 2 | 89 | 89 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-dff4f9344b02 | RELEASED | 2 | 89 | 88 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-6ee3370e933d | RELEASED | 2 | 88 | 87 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-facf2fa31834 | RELEASED | 2 | 88 | 86 | 100 | 85 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |
| candidate-1ed634d8bf6d | SUPPRESSED | 2 | 90 | 89 | 100 | 90 | 100 | 45 | 기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다. |

## 거시 후보 지도

| 영역 | 상태 | 실행 | 닫힘 | 완료 | 억제 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----:|-----:|-----:|-----:|-----------|------|
| 투자 엣지 | exhausted | 0 | 10 | 8 | 2 | 2400 | candidate-investment-edge-frontier-map | 최근 후보는 운영 체계 개선에 치우쳤고, 장기 목표는 측정 가능한 투자 성과 성장이다. |
| 데이터 증거 | underexplored | 0 | 0 | 0 | 0 | 2300 | candidate-data-evidence-frontier-map | 새 투자 후보는 데이터 깊이와 교차 검증 표면이 충분해야 재현 가능하다. |
| 체결 품질 | underexplored | 0 | 0 | 0 | 0 | 2200 | candidate-execution-quality-frontier-map | 투자 엣지가 실제 돈으로 이어지려면 주문 거부, 슬리피지, 지연, 비용 관측이 계속 닫혀야 한다. |
| 운영 체계 | underexplored | 0 | 0 | 0 | 0 | 2100 | candidate-agent-ops-frontier-map | 후보 생성·검증·인계 루프 자체가 멈추면 다음 세션이 다시 수동 발굴을 반복한다. |

## 투자 엣지 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----------|------|
| forward 레짐 엣지 | released | 2350 | candidate-forward-regime-edge-experiment | forward verdict 관측과 레짐 성과 증거는 존재하지만, 레짐별 견고성을 다음 no-live 실험 후보로 분리한 계약은 아직 없다. |
| 신호 다변화 엣지 | released | 2250 | candidate-signal-diversification-edge-experiment | 기존 forward 후보가 특정 신호·전략군에 치우치면 세계 수준의 투자 엣지 탐색 폭이 좁아진다. |
| 비용 차감 엣지 | released | 2150 | candidate-cost-adjusted-edge-experiment | paper 성과가 실제 돈으로 이어지려면 비용과 슬리피지에 둔감한 엣지를 분리해 검증해야 한다. |

## 데이터 증거 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----------|------|
| 공개 데이터 입력 품질 | released | 2250 | candidate-public-data-input-quality-contract | public-data sidecar는 발행 항목과 교차 검증 요약을 갖고 있지만, 그 범위·누락·검증 상태를 다음 투자 후보의 입력 품질 계약으로 고정하지 않았다. |
| 레짐 타임라인 커버리지 | released | 2150 | candidate-regime-timeline-coverage-contract | 레짐 층화는 public-data 타임라인에 의존하지만, 라벨 결측·관측 수·전망적 조인 품질을 별도 후보로 닫지 않았다. |
| 데이터 증거 생존성 | released | 2050 | candidate-data-evidence-liveness-contract | pipeline-liveness는 public-data와 regime-stratify 신선도를 보여주지만, 데이터 품질 후보 관점의 대기·복구 기준은 분리돼 있지 않다. |

## 체결 품질 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----------|------|
| 브로커 거부 분류 | released | 2150 | candidate-broker-rejection-taxonomy-contract | execution-quality sidecar는 거부 주문과 KIS 오류 코드를 관측하지만, 거부 원인 분류와 재발 기준은 별도 후보로 닫혀 있지 않다. |
| 체결 비용 기준 | released | 2050 | candidate-execution-cost-basis-contract | 비용 차감 엣지 후보는 execution-quality를 읽지만, accepted fill 비용 기준의 충분성은 아직 독립 후보로 닫혀 있지 않다. |
| 브로커 진단 생존성 | released | 1950 | candidate-broker-diagnostic-liveness-contract | KIS smoke와 execution-quality는 신선도와 성공 상태를 보여주지만, 체결 품질 후보 관점의 PASS/WAIT/FAIL 계약은 아직 분리돼 있지 않다. |

## 운영 체계 frontier 지도

| 영역 | 상태 | 점수 | 추천 후보 | 이유 |
|------|------|-----:|-----------|------|
| HANDOFF 사실성 생존성 | released | 2150 | candidate-handoff-truth-liveness-contract | HANDOFF.md와 check_handoff_facts는 최신 main·코드 merge 상태를 다음 세션에 전달하지만, stale handoff와 정상 handoff-only 예외를 후보 관점에서 분리하는 계약은 아직 없다. |
| PR/머지 증거 생존성 | released | 2050 | candidate-pr-merge-evidence-liveness-contract | PR 품질 관문, merge commit, released-work, deploy 관측은 각각 존재하지만 작업 완료 보고가 어느 증거까지 살아 있어야 하는지 후보 단위로 닫혀 있지 않다. |
| worktree 동시 작업 생존성 | released | 1950 | candidate-worktree-concurrency-liveness-contract | local_concurrency_guard와 session lease는 병렬 Codex 작업을 막지만, WARN/BLOCK·isolate·복구 스냅샷 흐름의 생존성은 후보로 닫혀 있지 않다. |
| agent harness 회귀 생존성 | released | 1850 | candidate-agent-harness-regression-liveness-contract | evaluation, 첫 판단 품질, redteam 하네스 묶음은 존재하지만, strict harness가 무엇을 PASS/WAIT/FAIL로 보존해야 하는지 후보 단위로 아직 닫혀 있지 않다. |
| 운영자 이해 가능 보고 생존성 | released | 1750 | candidate-operator-report-liveness-contract | AGENTS.md, quality gate, PR 템플릿, 첫 판단 품질 과제는 완료 보고의 의미 전달을 요구하지만, 최종 보고가 실제 운영 상태 변화·검증·남은 위험을 후보 단위로 보존하는 계약은 아직 닫혀 있지 않다. |

## 입력 증거

| 증거 | 존재 | 파싱 | 요약 |
|------|:----:|------|------|
| capital-path-readiness | yes | ok | readiness=ACCUMULATING_EDGE, live=PREVIEW_ONLY |
| evolution-backlog | yes | ok | candidates=10 |
| evolution-ledger | yes | ok | entries=5 |
| autonomous-promotion | yes | ok | overall=ok |
| candidate-implementation-factory | yes | ok | overall=degraded |
| candidate-packages | yes | ok | packages=2 |
| candidate-result-executor | yes | ok | results=2 |
| rebalance-paper-forward | yes | ok | 구조화 JSON 존재 |
| edge-autoarm | yes | ok | 구조화 JSON 존재 |
| money-path | yes | ok | 구조화 JSON 존재 |
| execution-quality | yes | ok | overall=OBSERVE |
| kis-smoke | yes | ok | state=success, exit=0 |
| rebalance-micro-gtaa | yes | ok | signal=INTENT_LOSS |
| public-data | yes | ok | overall_ok=True, published=11 |
| regime-stratify | yes | ok | total_return_days=753 |
| released-work | yes | ok | overall=OK |
| pipeline-liveness | yes | ok | overall=OK |

## 안전 경계

- no broker API call
- no orders
- no capital allocation
- no live strategy change
- no whitelist/caps change
- no secret read/write
- no external paid service
- work packet only; code/PR/merge stays in Codex review path

## 메타데이터

| 항목 | 값 |
|------|-----|
| run_id | [REDACTED_ACCOUNT] |
| run_url | https://github.com/jinooaction/claude/actions/runs/[REDACTED_ACCOUNT] |
| commit | 758dda2534af38f444ac75361295fb49b489e234 |
| trigger | schedule |
| timestamp_utc | 2026-08-08T09:51:19Z |

## 결정 JSON

```json
{
  "agent_ops_frontier_map": [
    {
      "coverage_status": "released",
      "frontier_key": "handoff_truth_liveness",
      "label_ko": "HANDOFF 사실성 생존성",
      "next_action_ko": "HANDOFF.md, check_handoff_facts.py, agent_harness_probe.py, released-work, autonomous-work 증거를 함께 읽어 stale handoff와 정상 handoff-only baseline을 분리하는 읽기 전용 계약을 만든다.",
      "priority_score": 2150,
      "reason_ko": "HANDOFF.md와 check_handoff_facts는 최신 main·코드 merge 상태를 다음 세션에 전달하지만, stale handoff와 정상 handoff-only 예외를 후보 관점에서 분리하는 계약은 아직 없다.",
      "recommended_candidate_id": "candidate-handoff-truth-liveness-contract",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml"
      ],
      "title_ko": "HANDOFF 사실성 생존성 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "pr_merge_evidence_liveness",
      "label_ko": "PR/머지 증거 생존성",
      "next_action_ko": "PR 본문 품질 관문, merge commit, released-work sidecar, deploy-status 관측을 함께 읽어 머지 뒤 완료 증거의 PASS/WAIT/FAIL 계약을 만든다.",
      "priority_score": 2050,
      "reason_ko": "PR 품질 관문, merge commit, released-work, deploy 관측은 각각 존재하지만 작업 완료 보고가 어느 증거까지 살아 있어야 하는지 후보 단위로 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-pr-merge-evidence-liveness-contract",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml"
      ],
      "title_ko": "PR/머지 증거 생존성 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "worktree_concurrency_liveness",
      "label_ko": "worktree 동시 작업 생존성",
      "next_action_ko": "local_concurrency_guard, .codex/state/concurrency 복구 스냅샷, pre-commit/pre-push 훅 경로를 읽어 동시 작업 방어의 PASS/WAIT/FAIL 계약을 만든다.",
      "priority_score": 1950,
      "reason_ko": "local_concurrency_guard와 session lease는 병렬 Codex 작업을 막지만, WARN/BLOCK·isolate·복구 스냅샷 흐름의 생존성은 후보로 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-worktree-concurrency-liveness-contract",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml"
      ],
      "title_ko": "worktree 동시 작업 생존성 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "agent_harness_regression_liveness",
      "label_ko": "agent harness 회귀 생존성",
      "next_action_ko": ".codex/harness/evaluation_tasks.toml, quality_tasks.toml, redteam_tasks.toml, scripts/agent_harness_probe.py를 함께 읽어 하네스 회귀 증거의 PASS/WAIT/FAIL 계약을 만든다.",
      "priority_score": 1850,
      "reason_ko": "evaluation, 첫 판단 품질, redteam 하네스 묶음은 존재하지만, strict harness가 무엇을 PASS/WAIT/FAIL로 보존해야 하는지 후보 단위로 아직 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-agent-harness-regression-liveness-contract",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml"
      ],
      "title_ko": "agent harness 회귀 생존성 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "operator_report_liveness",
      "label_ko": "운영자 이해 가능 보고 생존성",
      "next_action_ko": "AGENTS.md 보고 기준, .codex/quality-gate.md, PR 템플릿, QUALITY-006, HANDOFF와 released-work 증거를 함께 읽어 운영자가 다시 묻지 않아도 되는 완료 보고의 PASS/WAIT/FAIL 계약을 만든다.",
      "priority_score": 1750,
      "reason_ko": "AGENTS.md, quality gate, PR 템플릿, 첫 판단 품질 과제는 완료 보고의 의미 전달을 요구하지만, 최종 보고가 실제 운영 상태 변화·검증·남은 위험을 후보 단위로 보존하는 계약은 아직 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-operator-report-liveness-contract",
      "required_inputs": [
        "automation/autonomous-work-execution-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "AGENTS.md",
        "CLAUDE.md",
        "HANDOFF.md",
        ".codex/quality-gate.md",
        "scripts/local_concurrency_guard.py",
        ".codex/hooks.json",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".codex/state/concurrency",
        ".codex/harness/evaluation_tasks.toml",
        ".codex/harness/quality_tasks.toml",
        ".codex/harness/redteam_tasks.toml",
        "scripts/check_handoff_facts.py",
        "scripts/agent_harness_probe.py",
        ".github/pull_request_template.md",
        ".github/workflows/pr-quality-gate.yml"
      ],
      "title_ko": "운영자 이해 가능 보고 생존성 계약"
    }
  ],
  "commit": "758dda2534af38f444ac75361295fb49b489e234",
  "data_evidence_frontier_map": [
    {
      "coverage_status": "released",
      "frontier_key": "public_data_input_quality",
      "label_ko": "공개 데이터 입력 품질",
      "next_action_ko": "public-data summary, regime.json, regime_timeline.csv, regime-stratify, pipeline-liveness를 함께 읽어 공개 데이터 입력 품질 검증 게이트를 만든다.",
      "priority_score": 2250,
      "reason_ko": "public-data sidecar는 발행 항목과 교차 검증 요약을 갖고 있지만, 그 범위·누락·검증 상태를 다음 투자 후보의 입력 품질 계약으로 고정하지 않았다.",
      "recommended_candidate_id": "candidate-public-data-input-quality-contract",
      "required_inputs": [
        "automation/public-data:LAST_RUN.md",
        "automation/public-data:summary.json",
        "automation/public-data:regime.json",
        "automation/public-data:regime_timeline.csv",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "공개 데이터 입력 품질 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "regime_timeline_coverage",
      "label_ko": "레짐 타임라인 커버리지",
      "next_action_ko": "regime_timeline.csv와 regime-stratify 결과를 읽어 라벨 커버리지, 레짐별 관측 수, 전망적 조인 품질을 검증하는 후보를 만든다.",
      "priority_score": 2150,
      "reason_ko": "레짐 층화는 public-data 타임라인에 의존하지만, 라벨 결측·관측 수·전망적 조인 품질을 별도 후보로 닫지 않았다.",
      "recommended_candidate_id": "candidate-regime-timeline-coverage-contract",
      "required_inputs": [
        "automation/public-data:LAST_RUN.md",
        "automation/public-data:summary.json",
        "automation/public-data:regime.json",
        "automation/public-data:regime_timeline.csv",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "레짐 타임라인 커버리지 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "data_evidence_liveness",
      "label_ko": "데이터 증거 생존성",
      "next_action_ko": "pipeline-liveness의 collect-public-data와 regime-stratify 체크를 데이터 품질 후보의 PASS/WAIT/FAIL 기준으로 분리한다.",
      "priority_score": 2050,
      "reason_ko": "pipeline-liveness는 public-data와 regime-stratify 신선도를 보여주지만, 데이터 품질 후보 관점의 대기·복구 기준은 분리돼 있지 않다.",
      "recommended_candidate_id": "candidate-data-evidence-liveness-contract",
      "required_inputs": [
        "automation/public-data:LAST_RUN.md",
        "automation/public-data:summary.json",
        "automation/public-data:regime.json",
        "automation/public-data:regime_timeline.csv",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "데이터 증거 생존성 계약"
    }
  ],
  "evidence_surfaces": [
    {
      "key": "capital-path-readiness",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/capital-path-readiness-last-run:capital_path_readiness.json",
      "summary_ko": "readiness=ACCUMULATING_EDGE, live=PREVIEW_ONLY"
    },
    {
      "key": "evolution-backlog",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-evolution-last-run:candidate_backlog.json",
      "summary_ko": "candidates=10"
    },
    {
      "key": "evolution-ledger",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-evolution-last-run:learning_ledger.json",
      "summary_ko": "entries=5"
    },
    {
      "key": "autonomous-promotion",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/autonomous-promotion-last-run:promotion_summary.json",
      "summary_ko": "overall=ok"
    },
    {
      "key": "candidate-implementation-factory",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/candidate-implementation-factory-last-run:candidate_factory.json",
      "summary_ko": "overall=degraded"
    },
    {
      "key": "candidate-packages",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/candidate-implementation-factory-last-run:candidate_packages.json",
      "summary_ko": "packages=2"
    },
    {
      "key": "candidate-result-executor",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/candidate-implementation-results:candidate_results.json",
      "summary_ko": "results=2"
    },
    {
      "key": "rebalance-paper-forward",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
      "summary_ko": "구조화 JSON 존재"
    },
    {
      "key": "edge-autoarm",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/edge-autoarm-last-run:LAST_RUN.md",
      "summary_ko": "구조화 JSON 존재"
    },
    {
      "key": "money-path",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/money-path-last-run:LAST_RUN.md",
      "summary_ko": "구조화 JSON 존재"
    },
    {
      "key": "execution-quality",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/execution-quality-last-run:LAST_RUN.md",
      "summary_ko": "overall=OBSERVE"
    },
    {
      "key": "kis-smoke",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/kis-smoke-last-run:LAST_RUN.md",
      "summary_ko": "state=success, exit=0"
    },
    {
      "key": "rebalance-micro-gtaa",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
      "summary_ko": "signal=INTENT_LOSS"
    },
    {
      "key": "public-data",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/public-data:LAST_RUN.md",
      "summary_ko": "overall_ok=True, published=11"
    },
    {
      "key": "regime-stratify",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/regime-stratify-last-run:LAST_RUN.md",
      "summary_ko": "total_return_days=753"
    },
    {
      "key": "released-work",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/released-work-last-run:released_work.json",
      "summary_ko": "overall=OK"
    },
    {
      "key": "pipeline-liveness",
      "parse_status": "ok",
      "present": true,
      "source_ref": "automation/pipeline-liveness-last-run:LAST_RUN.md",
      "summary_ko": "overall=OK"
    }
  ],
  "execution_quality_frontier_map": [
    {
      "coverage_status": "released",
      "frontier_key": "broker_rejection_taxonomy",
      "label_ko": "브로커 거부 분류",
      "next_action_ko": "execution-quality, rebalance-micro-gtaa, kis-smoke 증거를 함께 읽어 브로커 거부 코드·원인·재발 가능성을 분류하는 읽기 전용 계약을 만든다.",
      "priority_score": 2150,
      "reason_ko": "execution-quality sidecar는 거부 주문과 KIS 오류 코드를 관측하지만, 거부 원인 분류와 재발 기준은 별도 후보로 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-broker-rejection-taxonomy-contract",
      "required_inputs": [
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "브로커 거부 분류 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "execution_cost_basis",
      "label_ko": "체결 비용 기준",
      "next_action_ko": "execution-quality와 money-path 증거를 읽어 실제 비용 기준이 충분한지와 관측 대기 상태를 분리하는 읽기 전용 계약을 만든다.",
      "priority_score": 2050,
      "reason_ko": "비용 차감 엣지 후보는 execution-quality를 읽지만, accepted fill 비용 기준의 충분성은 아직 독립 후보로 닫혀 있지 않다.",
      "recommended_candidate_id": "candidate-execution-cost-basis-contract",
      "required_inputs": [
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "체결 비용 기준 계약"
    },
    {
      "coverage_status": "released",
      "frontier_key": "broker_diagnostic_liveness",
      "label_ko": "브로커 진단 생존성",
      "next_action_ko": "kis-smoke, execution-quality, pipeline-liveness를 함께 읽어 브로커 진단 증거의 생존성 기준을 읽기 전용 계약으로 고정한다.",
      "priority_score": 1950,
      "reason_ko": "KIS smoke와 execution-quality는 신선도와 성공 상태를 보여주지만, 체결 품질 후보 관점의 PASS/WAIT/FAIL 계약은 아직 분리돼 있지 않다.",
      "recommended_candidate_id": "candidate-broker-diagnostic-liveness-contract",
      "required_inputs": [
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/pipeline-liveness-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/capital-path-readiness-last-run:capital_path_readiness.json"
      ],
      "title_ko": "브로커 진단 생존성 계약"
    }
  ],
  "investment_edge_frontier_map": [
    {
      "coverage_status": "released",
      "frontier_key": "forward_regime_edge",
      "label_ko": "forward 레짐 엣지",
      "next_action_ko": "rebalance-paper-forward, money-path, released-work, learning ledger를 함께 읽어 레짐별 forward edge no-live 실험 계약과 검증 기준을 SDD로 만든다.",
      "priority_score": 2350,
      "reason_ko": "forward verdict 관측과 레짐 성과 증거는 존재하지만, 레짐별 견고성을 다음 no-live 실험 후보로 분리한 계약은 아직 없다.",
      "recommended_candidate_id": "candidate-forward-regime-edge-experiment",
      "required_inputs": [
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md"
      ],
      "title_ko": "forward 레짐 엣지 no-live 실험 설계"
    },
    {
      "coverage_status": "released",
      "frontier_key": "signal_diversification_edge",
      "label_ko": "신호 다변화 엣지",
      "next_action_ko": "기존 forward verdict와 released-work를 읽어 상관이 낮은 신호 후보군을 no-live 실험 후보로 분리한다.",
      "priority_score": 2250,
      "reason_ko": "기존 forward 후보가 특정 신호·전략군에 치우치면 세계 수준의 투자 엣지 탐색 폭이 좁아진다.",
      "recommended_candidate_id": "candidate-signal-diversification-edge-experiment",
      "required_inputs": [
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md"
      ],
      "title_ko": "신호 다변화 no-live 엣지 실험 설계"
    },
    {
      "coverage_status": "released",
      "frontier_key": "cost_adjusted_edge",
      "label_ko": "비용 차감 엣지",
      "next_action_ko": "forward verdict, execution-quality, money-path 증거를 함께 읽어 비용 차감 no-live 실험 후보와 통과 기준을 만든다.",
      "priority_score": 2150,
      "reason_ko": "paper 성과가 실제 돈으로 이어지려면 비용과 슬리피지에 둔감한 엣지를 분리해 검증해야 한다.",
      "recommended_candidate_id": "candidate-cost-adjusted-edge-experiment",
      "required_inputs": [
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md"
      ],
      "title_ko": "거래 비용 차감 no-live 엣지 실험 설계"
    }
  ],
  "macro_candidate_map": [
    {
      "closed_count": 10,
      "coverage_status": "exhausted",
      "domain_key": "investment_edge",
      "label_ko": "투자 엣지",
      "next_action_ko": "forward verdict, money-path, released-work, learning ledger를 함께 읽어 투자 엣지 후보 공간을 영역별로 지도화하고 첫 no-live 실험 후보를 생성한다.",
      "operator_or_blocked_count": 0,
      "priority_score": 2400,
      "ready_count": 0,
      "reason_ko": "최근 후보는 운영 체계 개선에 치우쳤고, 장기 목표는 측정 가능한 투자 성과 성장이다.",
      "recommended_candidate_id": "candidate-investment-edge-frontier-map",
      "released_count": 8,
      "suppressed_count": 2,
      "title_ko": "투자 엣지 frontier 지도와 실험 후보 재생성",
      "work_domain_key": "strategy_design"
    },
    {
      "closed_count": 0,
      "coverage_status": "underexplored",
      "domain_key": "data_evidence",
      "label_ko": "데이터 증거",
      "next_action_ko": "공개 데이터, regime, pipeline-liveness, public-data sidecar의 빈 영역을 지도화해 다음 데이터 품질 후보를 생성한다.",
      "operator_or_blocked_count": 0,
      "priority_score": 2300,
      "ready_count": 0,
      "reason_ko": "새 투자 후보는 데이터 깊이와 교차 검증 표면이 충분해야 재현 가능하다.",
      "recommended_candidate_id": "candidate-data-evidence-frontier-map",
      "released_count": 0,
      "suppressed_count": 0,
      "title_ko": "데이터 증거 frontier 지도와 입력 품질 후보 재생성",
      "work_domain_key": "data_quality"
    },
    {
      "closed_count": 0,
      "coverage_status": "underexplored",
      "domain_key": "execution_quality",
      "label_ko": "체결 품질",
      "next_action_ko": "execution-quality와 broker 진단 증거를 지도화해 다음 읽기 전용 체결 품질 후보를 생성한다.",
      "operator_or_blocked_count": 0,
      "priority_score": 2200,
      "ready_count": 0,
      "reason_ko": "투자 엣지가 실제 돈으로 이어지려면 주문 거부, 슬리피지, 지연, 비용 관측이 계속 닫혀야 한다.",
      "recommended_candidate_id": "candidate-execution-quality-frontier-map",
      "released_count": 0,
      "suppressed_count": 0,
      "title_ko": "체결 품질 frontier 지도와 거래 비용 후보 재생성",
      "work_domain_key": "execution_quality"
    },
    {
      "closed_count": 0,
      "coverage_status": "underexplored",
      "domain_key": "agent_ops",
      "label_ko": "운영 체계",
      "next_action_ko": "autonomous-work, released-work, handoff, harness 증거를 지도화해 다음 운영 체계 후보를 생성한다.",
      "operator_or_blocked_count": 0,
      "priority_score": 2100,
      "ready_count": 0,
      "reason_ko": "후보 생성·검증·인계 루프 자체가 멈추면 다음 세션이 다시 수동 발굴을 반복한다.",
      "recommended_candidate_id": "candidate-agent-ops-frontier-map",
      "released_count": 0,
      "suppressed_count": 0,
      "title_ko": "운영 체계 frontier 지도와 자율 루프 후보 재생성",
      "work_domain_key": "agent_ops"
    }
  ],
  "objective_calibration": {
    "candidate_scores": [
      {
        "candidate_id": "wait-for-fresh-evidence",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 0,
          "learning_value": 85,
          "safety_margin": 100,
          "validation_cost_fit": 80
        },
        "explanation_ko": "안전 경계 안에서 자율 성장 루프의 반복 판단 비용을 줄이는 후보입니다.",
        "priority_score": 0,
        "risk_grade": 0,
        "status": "OBSERVATION_WAIT",
        "total_score": 66
      },
      {
        "candidate_id": "candidate-fd04772a23c5",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 90,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2997,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-source-diversification-sidecar-bottleneck",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 90,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2994,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-88a7e7f07361",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 89,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2968,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-e481b0309206",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 89,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2960,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-fa66202bf496",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 89,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2959,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-dff4f9344b02",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 88,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2927,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 89
      },
      {
        "candidate_id": "candidate-6ee3370e933d",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 87,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2910,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 88
      },
      {
        "candidate_id": "candidate-facf2fa31834",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 86,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 85
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2894,
        "risk_grade": 2,
        "status": "RELEASED",
        "total_score": 88
      },
      {
        "candidate_id": "candidate-1ed634d8bf6d",
        "component_scores": {
          "evidence_readiness": 100,
          "growth_leverage": 89,
          "learning_value": 45,
          "safety_margin": 100,
          "validation_cost_fit": 90
        },
        "explanation_ko": "기존 안전 경계 안에서 검증 가능한 다음 작업 후보입니다.",
        "priority_score": 2974,
        "risk_grade": 2,
        "status": "SUPPRESSED",
        "total_score": 90
      }
    ],
    "exploration_budget": {
      "max_parallel_candidates": 1,
      "max_ranked_candidates": 10,
      "max_validation_minutes": 90,
      "requires_handoff_refresh": true,
      "requires_pr_quality_gate": true
    },
    "learning_metrics": {
      "blocked_count": 0,
      "operator_approval_count": 0,
      "ranked_count": 0,
      "released_count": 8,
      "safety_impact_count": 0,
      "suppressed_count": 10
    },
    "objective_version": "autonomous-growth-objective-v1",
    "selected_candidate_id": "wait-for-fresh-evidence",
    "stop_conditions": [
      "operator approval required for safety-impact or grade >=4 work",
      "missing or malformed required sidecar evidence blocks autonomous start",
      "full pytest, ruff, handoff fact check, strict harness, or PR quality gate failure blocks merge",
      "WIP or DO NOT MERGE PR body blocks automatic merge"
    ]
  },
  "overall_status": "OBSERVATION_WAIT",
  "ranked_work": [],
  "run_id": "[REDACTED_ACCOUNT]",
  "safety_invariants": [
    "no broker API call",
    "no orders",
    "no capital allocation",
    "no live strategy change",
    "no whitelist/caps change",
    "no secret read/write",
    "no external paid service",
    "work packet only; code/PR/merge stays in Codex review path"
  ],
  "schema_version": "1.0",
  "selected_work": {
    "autonomy_level": "OBSERVATION_WAIT",
    "blocked_package_refs": [],
    "candidate_id": "wait-for-fresh-evidence",
    "completion_gates": [
      "새 sidecar 증거 수집",
      "released-work/autonomous-work 재실행"
    ],
    "domain_key": "agent_ops",
    "next_action_ko": "다음 scheduled sidecar 갱신 뒤 released-work와 autonomous-work를 다시 읽어 새 EXECUTION_READY 후보가 생겼는지 확인합니다.",
    "packet_id": "work-f29d42d07679",
    "priority_score": 0,
    "reason_ko": "실행 가능한 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없습니다. 현재 보이는 후보는 완료 8개와 억제 2개뿐이므로 완료 후보를 다시 선택하지 않고 새 sidecar 증거를 기다립니다.",
    "required_inputs": [
      "automation/capital-path-readiness-last-run:capital_path_readiness.json",
      "automation/autonomous-evolution-last-run:candidate_backlog.json",
      "automation/autonomous-evolution-last-run:learning_ledger.json",
      "automation/autonomous-promotion-last-run:promotion_summary.json",
      "automation/candidate-implementation-factory-last-run:candidate_factory.json",
      "automation/candidate-implementation-factory-last-run:candidate_packages.json",
      "automation/candidate-implementation-results:candidate_results.json",
      "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
      "automation/edge-autoarm-last-run:LAST_RUN.md",
      "automation/money-path-last-run:LAST_RUN.md",
      "automation/execution-quality-last-run:LAST_RUN.md",
      "automation/kis-smoke-last-run:LAST_RUN.md",
      "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
      "automation/public-data:LAST_RUN.md",
      "automation/regime-stratify-last-run:LAST_RUN.md",
      "automation/released-work-last-run:released_work.json",
      "automation/pipeline-liveness-last-run:LAST_RUN.md"
    ],
    "risk_grade": 0,
    "safety_boundary": [
      "no broker API call",
      "no orders",
      "no capital allocation",
      "no live strategy change",
      "no whitelist/caps change",
      "no secret read/write",
      "no external paid service",
      "work packet only; code/PR/merge stays in Codex review path"
    ],
    "safety_impact": [],
    "source_refs": [
      "automation/capital-path-readiness-last-run:capital_path_readiness.json",
      "automation/autonomous-evolution-last-run:candidate_backlog.json",
      "automation/autonomous-evolution-last-run:learning_ledger.json",
      "automation/autonomous-promotion-last-run:promotion_summary.json",
      "automation/candidate-implementation-factory-last-run:candidate_factory.json",
      "automation/candidate-implementation-factory-last-run:candidate_packages.json",
      "automation/candidate-implementation-results:candidate_results.json",
      "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
      "automation/edge-autoarm-last-run:LAST_RUN.md",
      "automation/money-path-last-run:LAST_RUN.md",
      "automation/execution-quality-last-run:LAST_RUN.md",
      "automation/kis-smoke-last-run:LAST_RUN.md",
      "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
      "automation/public-data:LAST_RUN.md",
      "automation/regime-stratify-last-run:LAST_RUN.md",
      "automation/released-work-last-run:released_work.json",
      "automation/pipeline-liveness-last-run:LAST_RUN.md"
    ],
    "start_guidance_ko": "현재는 새 코드 작업을 시작하지 말고 다음 sidecar 갱신 증거를 기다린다.",
    "status": "OBSERVATION_WAIT",
    "title_ko": "새 증거 대기",
    "validation_failure_groups": [],
    "work_type": "agent_operating_system"
  },
  "suppressed_work": [
    {
      "autonomy_level": "OBSERVATION_WAIT",
      "blocked_package_refs": [],
      "candidate_id": "wait-for-fresh-evidence",
      "completion_gates": [
        "새 sidecar 증거 수집",
        "released-work/autonomous-work 재실행"
      ],
      "domain_key": "agent_ops",
      "next_action_ko": "다음 scheduled sidecar 갱신 뒤 released-work와 autonomous-work를 다시 읽어 새 EXECUTION_READY 후보가 생겼는지 확인합니다.",
      "packet_id": "work-f29d42d07679",
      "priority_score": 0,
      "reason_ko": "실행 가능한 후보, 운영자 승인 필요 후보, 복구 우선 후보가 없습니다. 현재 보이는 후보는 완료 8개와 억제 2개뿐이므로 완료 후보를 다시 선택하지 않고 새 sidecar 증거를 기다립니다.",
      "required_inputs": [
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
        "automation/autonomous-evolution-last-run:candidate_backlog.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/candidate-implementation-factory-last-run:candidate_factory.json",
        "automation/candidate-implementation-factory-last-run:candidate_packages.json",
        "automation/candidate-implementation-results:candidate_results.json",
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/edge-autoarm-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/public-data:LAST_RUN.md",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md"
      ],
      "risk_grade": 0,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/capital-path-readiness-last-run:capital_path_readiness.json",
        "automation/autonomous-evolution-last-run:candidate_backlog.json",
        "automation/autonomous-evolution-last-run:learning_ledger.json",
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/candidate-implementation-factory-last-run:candidate_factory.json",
        "automation/candidate-implementation-factory-last-run:candidate_packages.json",
        "automation/candidate-implementation-results:candidate_results.json",
        "automation/rebalance-paper-forward-last-run:LAST_RUN.md",
        "automation/edge-autoarm-last-run:LAST_RUN.md",
        "automation/money-path-last-run:LAST_RUN.md",
        "automation/execution-quality-last-run:LAST_RUN.md",
        "automation/kis-smoke-last-run:LAST_RUN.md",
        "automation/rebalance-micro-gtaa-last-run:LAST_RUN.md",
        "automation/public-data:LAST_RUN.md",
        "automation/regime-stratify-last-run:LAST_RUN.md",
        "automation/released-work-last-run:released_work.json",
        "automation/pipeline-liveness-last-run:LAST_RUN.md"
      ],
      "start_guidance_ko": "현재는 새 코드 작업을 시작하지 말고 다음 sidecar 갱신 증거를 기다린다.",
      "status": "OBSERVATION_WAIT",
      "title_ko": "새 증거 대기",
      "validation_failure_groups": [],
      "work_type": "agent_operating_system"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-fd04772a23c5",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-2c9e2c9c3c96",
      "priority_score": 2997,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-source-diversification-sidecar-bottleneck",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-0ddc1686384e",
      "priority_score": 2994,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-88a7e7f07361",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-0df8a55123ba",
      "priority_score": 2968,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-e481b0309206",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-5bde83d8e6c6",
      "priority_score": 2960,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-fa66202bf496",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-4cc491a78202",
      "priority_score": 2959,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-dff4f9344b02",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-7a3821c877e5",
      "priority_score": 2927,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-6ee3370e933d",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-821895cc1539",
      "priority_score": 2910,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_RELEASED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-facf2fa31834",
      "completion_gates": [
        "released-work 장부 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "이미 구현·머지·인계된 후보이므로 다음 후보로 넘어간다.",
      "packet_id": "work-18ad4945d0c5",
      "priority_score": 2894,
      "reason_ko": "released-work 장부가 이 후보를 완료 처리했다: 완료된 Speckit 작업 산출물에서 명시적으로 완료 후보로 기록되었습니다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json",
        "automation/released-work-last-run:released_work.json"
      ],
      "start_guidance_ko": "이미 구현·머지·인계된 후보이므로 다시 착수하지 않는다.",
      "status": "RELEASED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    },
    {
      "autonomy_level": "CLOSED_SUPPRESSED",
      "blocked_package_refs": [],
      "candidate_id": "candidate-1ed634d8bf6d",
      "completion_gates": [
        "learning ledger 억제 사유 유지"
      ],
      "domain_key": "analysis",
      "next_action_ko": "승격 판단과 필요한 검증 evidence를 확인한다.",
      "packet_id": "work-08043b9ad7c4",
      "priority_score": 2974,
      "reason_ko": "learning ledger가 이 후보를 억제했다: 기계 판독 검증 결과에 실패가 있어 승격 증거로 병합하지 않는다.",
      "required_inputs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json"
      ],
      "risk_grade": 2,
      "safety_boundary": [
        "no broker API call",
        "no orders",
        "no capital allocation",
        "no live strategy change",
        "no whitelist/caps change",
        "no secret read/write",
        "no external paid service",
        "work packet only; code/PR/merge stays in Codex review path"
      ],
      "safety_impact": [],
      "source_refs": [
        "automation/autonomous-promotion-last-run:promotion_summary.json"
      ],
      "start_guidance_ko": "learning ledger가 억제한 후보이므로 새 증거 또는 재검토 조건 없이는 다시 착수하지 않는다.",
      "status": "SUPPRESSED",
      "title_ko": "제목 없음",
      "validation_failure_groups": [],
      "work_type": "analytics_validation"
    }
  ],
  "timestamp_utc": "2026-08-08T09:51:19Z"
}
```
