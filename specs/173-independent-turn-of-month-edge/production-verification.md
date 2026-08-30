# 생산 재생 검증

## 재생 순서

1. 명세·후보·분할·비용·관문을 먼저 커밋 `d05b3d6`으로 고정했다.
2. `origin/automation/autonomous-strategy-factory-last-run`의 최신 중앙 장부 752행을 읽었다.
3. 출시된 `specs/171-parallel-regime-edge-challenger/production-result.json`의 후보 16개를
   `EXPLORATORY_REJECTED` 상태로 복원했다.
4. 같은 코드 커밋으로 500회 가족 관문 교정을 재생해 `CALIBRATED`를 확인했다.
5. Kenneth French 공식 일별 자료를 새로 내려받고 월말·월초 16개 후보를 한 번 재생했다.

## 입력 지문

- 공식 자료 SHA-256: `39f9ae1d0e9f575024bc23145980ac270cea508fb67e592578b3f4d65f36d006`
- 자료 범위: 1926-07-01~2026-06-30, 26,274행
- 이전 중앙 장부 코드: `c418db88314849926c53ca990bf1862daa1dec1d`
- 이전 중앙 장부 생성 시각: `2026-08-30T14:06:14Z`
- 현재 사전등록 코드: `d05b3d61541c7a60a1ee552e70e653c135612558`
- 결과 배치: `turn-of-month-39f9ae1d0e9f-d05b3d61541c`

## 재생 명령

```bash
uv run python scripts/edge_gate_calibration_probe.py \
  --seed 60000 --repetitions 500 \
  --code-commit d05b3d61541c7a60a1ee552e70e653c135612558 \
  --json-out /tmp/spec173-edge-gate-calibration.json

uv run python scripts/turn_of_month_equity_factory_probe.py \
  --prior-factory-json /tmp/spec173-prior-strategy-factory.json \
  --released-regime-json specs/171-parallel-regime-edge-challenger/production-result.json \
  --calibration-json /tmp/spec173-edge-gate-calibration.json \
  --code-commit d05b3d61541c7a60a1ee552e70e653c135612558 \
  --timestamp-utc 2026-08-30T15:00:00Z \
  --json-out /tmp/spec173-turn-of-month-production.json
```

## 독립 확인

- 전체 원시 결과: 1,205,293바이트
- 감사 행: 784개, 전략 지문 고유값: 784개
- 전략군: 19개
- 개발 선택에 홀드아웃 사용: false
- 실패 관문: `holdout_excess_psr`, `holdout_annual_excess`, `positive_eras`,
  `single_year_concentration`, `stress_25bps_positive`
- 주문·자본·라이브 전략 변경: 모두 0건

## 저장소 완료 관문

- 관련 회귀시험: 175개 통과
- 전체 시험: 3,155개 통과, 실브로커 환경변수 전용 6개 제외
- 린트: `uv run ruff check src tests` 통과
- 에이전트 하네스: 엄격 모드 14/14 통과
- HANDOFF 사실 검증: 통과
- 결과 JSON 스키마와 전체 원시 결과 핵심 필드 일치: 통과
