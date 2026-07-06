# Feature Specification: Cost-Adjusted Edge Experiment

**Feature Branch**: `Codex/097-cost-adjusted-edge-experiment`
**Created**: 2026-07-06
**Status**: Draft
**Input**: Autonomous work candidate `candidate-cost-adjusted-edge-experiment`

## 사용자 시나리오와 테스트

### User Story 1 - 비용 차감 no-live 계약을 한 곳에서 본다 (Priority: P1)

운영자는 forward verdict, execution-quality, money-path, released-work, learning ledger, pipeline-liveness 증거를 한 번에 읽는 보고서를 보고, 현재 후보가 비용을 차감해도 실험 가능한 엣지인지 판단하고 싶다.

**왜 중요한가**: forward 성과만 보면 비용과 실행 품질 악화가 빠진다. 이 기능은 비용 차감 관문을 별도 계약으로 고정해 다음 세션이 같은 sidecar를 다시 조립하지 않게 한다.

**Independent Test**: 필수 sidecar 원문을 입력하면 결정론적 JSON/Markdown 보고서가 생성되고, `experiment_id`, `completed_candidate_id`, 비용 스트레스 후보, 안전 경계, 검증 게이트가 안정적으로 출력된다.

### User Story 2 - 비용 근거 부족과 관측 부족을 정직하게 분리한다 (Priority: P2)

운영자는 forward 관측 부족, 실행 품질 관측 부족, 비용 기준 부족, 파이프라인 장애를 서로 다른 게이트로 보고 싶다.

**왜 중요한가**: 현재 execution-quality는 `INTENT_LOSS`와 브로커 거부를 관측하지만, 실제 체결 비용과 회전율 근거는 충분하지 않다. 이를 수익률로 과장하면 no-live 후보 평가가 잘못된다.

**Independent Test**: 현재처럼 forward 비교 가능 트랙이 0개이고 execution-quality가 `INSUFFICIENT_DATA`이면 전체 상태는 `OBSERVATION_WAIT`이며, 파이프라인 장애나 필수 증거 누락만 `BLOCKED`가 된다.

### User Story 3 - 후보 완료 뒤 다음 자율 루프가 전진한다 (Priority: P3)

운영자는 이 후보가 완료되면 released-work와 autonomous-work가 `candidate-cost-adjusted-edge-experiment`를 완료로 보고, 다음 후보 발굴로 넘어가는지 확인하고 싶다.

**왜 중요한가**: 자율 성장 루프는 한 후보를 끝냈다는 마커가 있어야 같은 일을 반복하지 않는다.

**Independent Test**: 계약 파일과 tasks 완료 상태가 released-work 스캔에 잡히고, autonomous-work 로컬 replay에서 현재 후보가 다시 선택되지 않는다.

## 요구사항

### Functional Requirements

- **FR-001**: 시스템은 다음 6개 입력을 필수 증거로 선언해야 한다: `rebalance-paper-forward`, `execution-quality`, `money-path`, `released-work`, `evolution-ledger`, `pipeline-liveness`.
- **FR-002**: 시스템은 forward 리더보드에서 track key, label, incumbent 여부, verdict, comparability, n_obs, min_obs, total_return_pct, max_drawdown_pct, universe를 추출해야 한다.
- **FR-003**: 시스템은 execution-quality 보고서에서 overall_status, monitor_verdict, latest_signal, cumulative_pnl_usd, rejected_orders, parsed_broker_errors, KIS smoke 상태를 추출해야 한다.
- **FR-004**: 시스템은 forward 성과에 보수적 비용 스트레스(기본 10/25/50 bps)를 차감한 provisional cost-adjusted return을 계산해야 한다.
- **FR-005**: 시스템은 회전율, 실제 체결 비용, 충분한 accepted/fill 근거가 없을 때 `cost-basis-completeness`를 `WAIT`로 표시해야 한다.
- **FR-006**: 시스템은 money-path가 `can_submit_real_orders=true`여도 실제 주문을 만들거나 live 전략을 바꾸지 않아야 하며, 보고서는 읽기 전용이어야 한다.
- **FR-007**: 시스템은 필수 증거 누락, 파싱 실패, critical pipeline 상태, learning ledger 억제 신호를 `BLOCKED` 사유로 분리해야 한다.
- **FR-008**: 시스템은 현재 checkout 또는 released-work sidecar가 완료 후보 마커를 포함하면 `released-work-closure`를 `PASS`로 표시해야 한다.
- **FR-009**: probe는 `--manifest`, `--json`, `--json-out`, `--summary-out`, `--repo-root`, `--now`, `--run-id`, `--commit` 옵션을 제공해야 한다.
- **FR-010**: 출력 JSON은 다음 세션과 자동화가 재사용할 수 있도록 정렬 가능한 키와 명시적 상태값을 포함해야 한다.

### Non-Goals

- 실제 주문, 계좌 조회, 브로커 API 호출, 실거래 전환, 자본 배분은 하지 않는다.
- 비용 모델을 live 주문 라우터나 portfolio sizing에 연결하지 않는다.
- 헌법, 커널 목록, whitelist/caps, 감사 로그, 비밀값, 배포 제한은 바꾸지 않는다.

## 핵심 엔티티

- **CostAdjustedEdgeExperimentReport**: 전체 no-live 계약 보고서.
- **ForwardCostTrack**: forward track 성과와 비용 스트레스별 보수적 결과.
- **ExecutionCostSnapshot**: execution-quality에서 읽은 의도 손실, 거부 주문, smoke 상태.
- **ValidationGate**: 증거 입력, 관측 준비, 비용 기준, no-live 안전, released-work closure 상태.

## 성공 기준

- **SC-001**: 필수 sidecar 6개를 읽은 현재 증거 replay가 `OBSERVATION_WAIT`를 안정적으로 출력한다.
- **SC-002**: 비용 기준이 부족할 때도 비용 스트레스 후보는 계산되지만, `CONTRACT_READY`로 과장하지 않는다.
- **SC-003**: 필수 입력 누락 또는 pipeline critical 상태는 `BLOCKED`로 구분된다.
- **SC-004**: 새 계약 파일은 released-work가 `candidate-cost-adjusted-edge-experiment` 완료로 인식할 수 있는 마커를 포함한다.
- **SC-005**: 전체 검증(`pytest`, `ruff`, handoff fact check, strict harness)이 통과한다.

## 위험 등급과 안전 경계

위험 등급은 2다. 새 no-live 운영 보고서, 후보 closure, 다음 세션 포인터를 추가하므로 운영 체계에는 영향을 준다. 다만 돈 경로와 안전 경계는 바꾸지 않는다.

보존해야 할 경계: broker API 호출 없음, 주문 없음, 자본 배분 없음, live 전략 변경 없음, whitelist/caps 변경 없음, 비밀값 읽기/쓰기 없음, 외부 유료 서비스 없음, 헌법/커널 변경 없음.

