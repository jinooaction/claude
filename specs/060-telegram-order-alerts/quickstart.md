# Quickstart: Telegram Order Alerts

Telegram 알림은 Bot API 텍스트 메시지만 사용한다. Telegram 결제 계정이나 유료 봇
호스팅은 필요하지 않지만, 기존 서버와 GitHub Actions 실행 자원은 그대로 사용한다.

## 1. 텔레그램 봇 만들기

1. Telegram 앱에서 `@BotFather`를 연다.
2. `/newbot`을 실행해 봇을 만든다.
3. BotFather가 준 token을 `TELEGRAM_BOT_TOKEN`으로 보관한다.
4. 만든 봇에게 아무 메시지나 한 번 보낸다.
5. 아래 주소를 브라우저에서 열어 `chat.id`를 찾는다.

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

## 2. GitHub Actions micro GTAA 알림 켜기

GitHub repository secrets에 추가:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

이후 `Micro GTAA live canary rebalance` 실행이 끝나면 텔레그램 요약이 전송된다. secrets가 없으면 조용히 skip된다.

## 3. 서버 일반 주문 알림 켜기

서버 `/opt/auto-invest/.env`에 추가:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_SOURCE_LABEL=auto-invest
```

테스트 메시지:

```bash
cd /opt/auto-invest
/usr/local/bin/uv run auto-invest telegram-alerts \
  --env-file .env \
  --db data/auto_invest.db \
  --state-file data/telegram_alerts_state.json \
  --test-message
```

서비스 활성화:

```bash
sudo systemctl enable --now auto-invest-telegram-alerts.service
sudo journalctl -u auto-invest-telegram-alerts.service -f
```

중지:

```bash
sudo systemctl disable --now auto-invest-telegram-alerts.service
```

## 4. 로컬 검증

```bash
uv run pytest tests/unit/test_telegram_alerts.py tests/integration/test_telegram_alerts_cli.py tests/unit/test_micro_gtaa_telegram_alerts.py
uv run ruff check src tests
```

## 안전 메모

- 알림 서비스는 audit_log를 읽기만 한다.
- 알림 실패는 주문 제출, 체결 동기화, 손실 브레이커, halt 설정에 영향을 주면 안 된다.
- Telegram token과 chat id는 저장소에 커밋하지 않는다.
