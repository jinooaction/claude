# HANDOFF-153 - 전략 성과 장부 교정과 저회전 AI 검증

## 상태

PR #642가 `main`에 병합되어 계정 전체 손익과 자동매매 전략 손익이 분리됐다. 생산 배포와 KIS 회귀 검사는 성공했고, 주문 없는 수동 production 검증으로 새 전략 측정 계약의 NAV와 성과 보고서가 실제 서버에서 생성됐다.

현재 자동매매 전략 자체의 체결은 0건, 총손익은 0달러, NAV는 293달러다. 과거의 +15.93달러 실현손익과 ORANY 평가손익은 시스템 시작 전 보유 자산에서 나온 것이므로 전략 엣지 증거가 아니다.

## 무엇을 고쳤나

- `deploy/live-opening-positions.toml`의 BHP·MRK·ORANY·RELX를 전략 측정에서 제외하는 결정적 계약 해시를 추가했다.
- 전략 성과 보고서는 제외된 체결 수와 실현·미실현 손익을 별도 공개한다.
- live NAV, 성장률, forward 판정, 최초 수익 증거는 같은 측정 계약의 최신 연속 구간만 사용한다.
- 과거 계정 범위 `FIRST_PROFIT_OBSERVED`는 전략 범위 계약이 없으므로 더 이상 승계하지 않는다.
- `resume-readiness`가 최신 정합성, halt, 측정 계약을 읽기 전용으로 평가한다. 이 명령은 주문과 halt 해제를 수행하지 않는다.
- 일봉 AI에 최소 보유 4주, 거래 임계값 8%, 예상 비용 25bp를 적용하고 기존 후보와 회전율을 비교하는 관문을 추가했다.

## 생산 증거

- 기능 커밋: `db5d8ac`.
- main 머지: `bb868b4`, PR #642.
- 배포: run `32548715032`, 성공.
- KIS smoke: run `32548715072`, 5/5 통과. 매수가능현금 934.27달러, ORANY 28주, 열린 미체결 0건.
- 주문 없는 production 검증: run `32548824195`, 성공.
- 전략 측정 계약: `sha256:2542c0ddd4499481582d820ebee48fadbbfbab9b6208c749d843c025b74288d8`.
- 전략 성과: 체결 0건, 총손익 0달러, NAV 293달러.
- 제외 증거: 체결 3건, 실현 +15.93달러, 미실현 +209.86달러.
- 저회전 AI: run `32548715047`, 회전율 34.34 -> 8.374194, 75.61388% 감소, 판정 `NO_EDGE`.

## 검증

- `uv run pytest`: 2888 passed, 6 skipped.
- `uv run ruff check src tests`: 통과.
- `bash -n deploy/live-canary-on-instance.sh deploy/observe-on-instance.sh`: 통과.
- `uv run python scripts/agent_harness_probe.py --strict`: OK 14/14.
- `uv run python scripts/check_handoff_facts.py`: OK.
- PR 품질 관문과 GitHub 검사: 통과.

## 안전 경계

`K4` 추가 전용 감사 로그에는 선택 필드만 추가했고 기존 행을 수정하지 않았다. 실제 주문, 주문 취소, 자본 증액, 허용 종목 확대, 포지션 한도 완화는 0건이다.

수동 production 검증은 `manual-no-order-preflight`라 주문을 내지 않았다. `armed:true`와 293달러 자본 배정은 유지되지만, 현재 `data/halt.flag`와 오래된 정합성 `MISMATCH`가 주문을 차단한다.

## 다음 세션 판단

최우선은 최신 계좌 정합성을 다시 실행해 `OK` 또는 실제 차이를 확인하는 것이다. 최신 결과가 `OK`이고 같은 전략 측정 계약의 증거가 유효할 때만 `RESUME_ELIGIBLE`이 된다. 그 전에는 halt를 해제하지 않는다.

저회전 AI는 비용 민감도를 크게 낮췄지만 수익 품질 관문을 넘지 못했다. `NO_EDGE` 후보를 실거래로 승격하지 말고, 새로운 독립 신호나 충분히 다른 모델 가설이 생길 때만 no-live 연구를 추가한다.
