# 자동 룰 설계자 (`auto-invest design`) 운영자 사용법

`auto-invest design`은 자연어 의도에서 룰 후보를 만들고 검증 상태를 남기는
제안 전용 명령입니다. 이 명령은 실거래 프로세스를 시작하지 않고 실제 주문도 내지
않습니다.

## 전제

- Vultr 인스턴스가 가동 중입니다.
- KIS 키와 Anthropic API 키가 `.env`에 입력돼 있습니다.
- KIS 계좌 정보는 후보 설계 문맥을 읽기 위해 사용됩니다. 주문 쓰기 권한으로
  사용하지 않습니다.

## 콘솔에서 실행

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
```

시스템이 수행하는 일:

1. KIS 계좌 잔고와 보유 종목을 읽습니다.
2. Claude API로 룰 후보를 생성합니다.
3. 정적 검증을 수행합니다.
4. 동적 백테스트와 paper/모의 검증 증거가 없으면 `WAIT_DYNAMIC_VALIDATION`으로
   남깁니다.
5. `config/rules_auto_<timestamp>.toml` 후보 파일, 같은 이름의
   `.proposal.json` 검증 보고서, 감사 기록을 남깁니다.

정상 종료는 “후보 생성 완료”를 뜻합니다. 라이브 승격은 별도 경로입니다.

```text
candidate rules
→ static validation
→ backtest
→ paper/forward validation
→ hardened canary
→ approved live path
```

## GitHub Actions에서 실행

Actions 탭에서 `Operator design (auto-invest)`를 수동 실행하고 `intent`를 입력합니다.
예약 실행과 자동 확인 입력은 제거됐습니다.

## 과거 상태 확인

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --check
```

`--check`는 과거에 남아 있는 `RULE_DESIGN_DEPLOYED` 기록을 읽기 전용으로 요약하는
역사 호환 모드입니다. 새 `design` 실행은 그 이벤트를 만들지 않습니다.

## 막혔을 때

- **"ANTHROPIC_API_KEY가 없습니다"**: `set_secrets.sh`를 다시 실행해 Anthropic 키를
  입력합니다.
- **"KIS 잔고 조회 실패"**: KIS 키 또는 계좌번호를 확인합니다.
- **"WAIT_DYNAMIC_VALIDATION"**: 후보는 생성됐지만 백테스트와 paper/모의 증거가
  아직 없다는 뜻입니다. 기존 검증·승격 경로로 후보를 넘깁니다.
- 그 외: `journalctl -u auto-invest.service -n 50`으로 로그를 확인합니다.

## 금지

- `design` 결과를 곧바로 실거래 설정으로 적용하지 않습니다.
- 후보 파일을 만들었다는 이유만으로 `AUTO_INVEST_MODE=live`, live sentinel,
  자본 사다리, whitelist, caps를 바꾸지 않습니다.
