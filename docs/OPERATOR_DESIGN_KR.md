# 자동 룰 설계자 (auto-invest design) 운영자 사용법

**전제**: Vultr 인스턴스가 이미 가동 중 (`auto-invest.service` systemd로 24시간 도는 중). KIS 키는 이미 `set_secrets.sh`로 입력 완료. Anthropic API 키만 추가 입력 + design 명령 실행하면 끝.

## 한 줄로 정리한 절차

### 1단계 — Anthropic API 키 추가 (한 번만)

Vultr 웹 콘솔에서 인스턴스 "View Console" 클릭 → root 로그인 → 다음 한 줄:

```bash
sudo /opt/auto-invest/scripts/set_secrets.sh
```

prompt가 KIS 키 3개를 다시 물어봅니다 (그냥 같은 값을 다시 입력하거나, Enter 누르면 기존 값 유지 안 됨 — KIS 키는 다시 입력 필요).

마지막 prompt에 ANTHROPIC_API_KEY 한 번 붙여넣기. 이후 자동 진행 — 워커 재시작 + 다음 절차 안내.

### 2단계 — 자동 룰 설계 실행 (한 줄)

Anthropic 키 입력 후 같은 콘솔에서:

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --intent "자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"
```

시스템이 자동으로 진행하는 단계:

1. KIS 계좌 잔고 조회.
2. Claude API가 룰 자동 생성 (~수 초).
3. 정적 검증 5종 (cap·whitelist·자본 한도·종목 형식).
4. 검증 통과 시 한글 요약 + `OK` 입력 prompt.
5. 운영자가 `OK` 입력 → 새 라이브 worker subprocess 자동 시작.
6. 자동 생성된 `config/rules_auto_<timestamp>.toml`이 main으로 commit되어 deploy timer 통해 다음 30분 안에 적용.

### 3단계 — 라이브 worker 상태 확인 (언제든)

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --check
```

가장 최근 design 결과의 라이브 worker가 한글로 요약:

- 실행 상태 (실행 중 / 종료됨)
- 라이브 시작 이후 시그널·체결·차단·오류 카운트
- 운영자 원본 의도 + Claude 해석 매개변수

## 의도 변경

한 달 후 룰을 바꾸고 싶으면 2단계만 다시 실행 (다른 의도 텍스트로):

```bash
sudo -u auto-invest /usr/local/bin/uv run --project /opt/auto-invest \
  auto-invest design --intent "자본 200달러, 미국 대형주 + ETF 분산, 위험 낮음"
```

기존 라이브 worker는 자동 종료, 새 worker가 새 룰로 시작.

## 막혔을 때

- **"ANTHROPIC_API_KEY가 없습니다"**: 1단계 다시 실행 (Anthropic 키 입력 추가).
- **"KIS 잔고 조회 실패"**: KIS 키가 만료됐을 수 있음. 1단계 다시 실행.
- **"잔고 부족"**: KIS 계좌에 입금 후 다시 시도.
- **"Claude API 오류"**: Anthropic 계정에 결제 카드 등록 되어 있는지 확인.
- 그 외: `journalctl -u auto-invest.service -n 50`으로 로그 확인.

## 주의

- design 명령은 운영자가 인스턴스 콘솔에서 직접 실행해야 합니다. systemd timer로 자동화는 별도 스펙 (spec 005 autonomous tuner) 후속.
- 라이브 시작 후 24시간 정도 관찰하고 시그널·체결이 너무 적거나 너무 많으면 의도를 좀 더 구체적으로 다시 시도.
