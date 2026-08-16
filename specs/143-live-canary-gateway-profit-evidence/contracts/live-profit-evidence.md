# Contract: Live Profit Evidence

## Input

- 현재 `performance --mode live --format json` 출력
- 직전 `automation/live-profit-evidence-last-run:profit_evidence.json`

## Output states

- `UNKNOWN`: 성과 JSON 없음·파싱 실패·live 모드 불일치
- `NO_FILLS_YET`: live 체결 0건
- `PNL_INCOMPLETE`: 체결은 있으나 열린 종목 시세 또는 데이터 품질 증거가 불완전
- `FILLED_NOT_PROFITABLE`: 완전한 증거이나 총손익 0 이하
- `FIRST_PROFIT_OBSERVED`: 체결 1건 이상, 결측·경고 0, 총손익 > 0

최초 `FIRST_PROFIT_OBSERVED`의 시각과 당시 수치는 prior sidecar에서 누적 보존한다.
