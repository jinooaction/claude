# Contract: 자율 루프 품질 폐쇄

## Autonomous work execution JSON

선택된 작업 패킷은 기존 필드에 더해 다음 필드를 포함한다.

```json
{
  "autonomy_level": "CODEX_AUTONOMOUS_START",
  "start_guidance_ko": "운영자 추가 질문 없이 새 worktree 또는 브랜치에서 SDD 두께를 판단하고 구현, 검증, PR, 자동 머지 절차로 진행한다.",
  "completion_gates": [
    "관련 focused pytest 통과",
    "uv run pytest 통과",
    "uv run ruff check src tests 통과",
    "uv run python scripts/check_handoff_facts.py 통과",
    "uv run python scripts/agent_harness_probe.py --strict 통과",
    "PR 품질 관문 통과",
    "필요한 HANDOFF 갱신"
  ]
}
```

## Money gate alignment JSON

관측 수가 다르지만 결론이 같은 경우 정렬 이슈 배열에 정보성 항목을 추가한다.

```json
{
  "severity": "SNAPSHOT_SKEW",
  "gate_key": "snapshot_provenance",
  "expected": "same observation snapshot",
  "observed": "14-15/20 (money-path=14, edge-autoarm=15)",
  "reason_ko": "서로 다른 sidecar 실행 시각 때문에 관측 수가 다르지만 모든 게이트가 관측 부족 대기를 말한다."
}
```

## Workflow trigger

`pipeline-liveness.yml`은 `Operator mobile alerts` workflow 완료 후 다시 실행될 수 있어야 한다. 이 후속 실행은 읽기 전용이며 `automation/pipeline-liveness-last-run`만 갱신한다.
