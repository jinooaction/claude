# Contract: `auto-invest design`

**Spec**: 010 · **Phase**: 1 · **Date**: 2026-05-19

운영자가 자연어 한 줄로 룰 설계를 의뢰하는 CLI 진입점.

## Usage

```bash
auto-invest design \
    --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통" \
    [--db PATH] \
    [--env-file PATH] \
    [--base-url URL] \
    [--halt-path PATH] \
    [--prices PATH] \
    [--check]
```

### Options

| 옵션 | 필수 | 의미 |
|------|------|------|
| `--intent` | yes (단, `--check`이면 no) | 자연어 한 줄 의도. 한글·영어 혼용 OK. |
| `--db` | no | SQLite 경로. 기본 `data/auto_invest.db`. |
| `--env-file` | no | KIS/Claude 시크릿이 든 .env. |
| `--base-url` | no | KIS REST base URL. |
| `--halt-path` | no | halt flag 경로. |
| `--prices` | no | LLM price table. spec 002 호환. |
| `--check` | no | 가장 최근 paper-run 진행 상태 확인 모드 (R-D5). |

## Behavior

### 정상 흐름 (한 호출)

1. **시작 단계**: config·secrets·prices 로드 → mutex check → KIS 잔고 조회.
2. **Claude 호출**: 시스템 prompt 조립 → anthropic SDK 호출 → 응답을 TOML로 파싱.
3. **정적 검증**: caps·whitelist·종목 범위·자본 한도 확인. 실패 시 재시도.
4. **paper-run 1일분**: subprocess로 paper-run 띄움 → audit_log polling → 1일치 fill·error 통계 수집.
5. **운영자 OK prompt**: 검증 결과 한글 요약 + `typer.prompt("OK/y/예/yes 입력")` (60s timeout).
6. **라이브 시작**: OK 받으면 `RULE_DESIGN_DEPLOYED` 기록 + 새 worker subprocess.

### `--check` 흐름

1. audit_log에서 가장 최근 `RULE_DESIGN_REQUESTED`의 session_id 조회.
2. 같은 session의 paper-run 상태 (PAPER_RUN_STARTED/STOPPED) 확인.
3. 일주일 미달이면 진행 상황 paper-report 출력.
4. 일주일 지났으면 최종 paper-report + 운영자 OK prompt → 라이브 시작.

### 거부 시퀀스

mutex 충돌·KIS 토큰 실패·3회 재설계 실패·운영자 거부 모두 동일 패턴: `RULE_DESIGN_REJECTED` audit + 한글 stderr + 적절한 exit code.

## Exit Codes

| Code | 의미 |
|------|------|
| 0 | 정상 (라이브 시작 또는 OK 단계 거부) |
| 1 | 일반 오류 (KIS 실패·Claude API 오류·max_retries 등) |
| 2 | 설정·인자 오류 (의도 빈 문자열·자본 부족) |
| 70 | mutex 충돌 — design 이미 실행 중 |

## stdout/stderr 출력 (모두 한글)

### 정상 흐름 예시

```
auto-invest design 시작 (session_id=42)
KIS 잔고 조회 중...
잔고: 102.45 USD, 보유 종목: VOO(0.2주)

Claude에게 룰 설계 요청 중... (시도 1/3)
Claude 응답 받음 (모델: claude-opus-4-7, 토큰: 입력 1234 / 출력 567, 비용 $0.012)

운영자 의도 해석:
  - 위험 "보통" → max_drawdown 5%
  - 종목 우주 → VOO, QQQ, SPY (대형 ETF 3개)
  - 매주 월요일 적립 → 종목당 동일 비중 33%씩 매주 매수

정적 검증 통과.

paper-run 1일분 시작 중...
(약 6.5시간 후 완료 예정. background로 진행하시려면 Ctrl+C 후 --check 옵션 사용.)

paper-run 1일분 결과:
  - 시그널 발생: VOO 1건, QQQ 1건, SPY 1건
  - 시뮬 체결: 3건 모두 성공 (총 $99.83 사용)
  - 외부 API 오류: 0건

이 룰로 라이브 시작하시려면 'OK' 또는 'y' 또는 '예' 또는 'yes'를 입력해주세요. (60초 안에 응답 없으면 자동 거부)
> OK

라이브 시작됨. session_id=58, 현재 자본 102.45 USD.
```

### 거부 예시

```
auto-invest design 시작 거부:
다른 design 명령이 이미 실행 중입니다 (session_id=41, 시작 시각 2026-05-19T01:00:00Z).
기존 명령 종료 후 다시 시도해주세요.
```

## 테스트 가능한 invariants

| Invariant | 검증 방법 |
|-----------|----------|
| design 명령이 KIS 주문 API에 접근 안 함 | `tests/integration/test_design_cli.py::test_no_kis_orders` |
| Claude mock으로 end-to-end 흐름 동작 | `tests/integration/test_design_claude_mock.py` |
| mutex 충돌 시 exit 70 | `tests/unit/test_design_mutex.py` |
| 운영자 OK timeout 시 거부 | `tests/integration/test_design_cli.py::test_ok_timeout` |
| 3회 재설계 실패 시 exit 1 + audit row | 동 통합 테스트 |
