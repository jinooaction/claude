# auto-invest — 운영자 5분 시작 가이드 (한글)

운영자가 자기 호스트에서 처음 자동 거래를 가동시킬 때의 가장 짧은 경로.
리눅스 + systemd 환경 가정. 이 문서대로만 따라 하면 됩니다.

## 0. 준비물 한 줄

- Ubuntu 22+ / Debian 12+ 같은 systemd 기반 리눅스 호스트.
- `uv`(파이썬 환경/실행기). 없으면 `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- KIS Developers 계정 + 미국 주식 거래 가능한 계좌 + 발급된 `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO`.
- 운영자(root 권한 보유) 본인.

## 1. 받아오기 + 의존성 설치 (1분)

```bash
sudo install -d -m 0750 -o $(whoami) -g $(whoami) /opt/auto-invest
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
cd /opt/auto-invest
uv sync
```

## 2. `.env`에 자격증명 채우기 (1분)

```bash
cp .env.example .env
nano .env   # 또는 vim/code/원하는 편집기
```

채워야 하는 항목 (네 개 전부 필수):

| 키 | 의미 |
|----|------|
| `KIS_APP_KEY` | KIS Developers 앱 키 |
| `KIS_APP_SECRET` | KIS Developers 앱 시크릿 |
| `KIS_ACCOUNT_NO` | 미국 주식 거래 가능한 계좌번호 (CANO+ACNT_PRDT) |
| `AUTO_INVEST_CAPITAL` | 이번 세션 운영 자본금 USD 정수 (예: `10000`) — 포지션 사이징의 분모 |

`.env`는 `.gitignore`에 들어 있고, 워커가 읽은 값은 로그/리포트 어디서도 `***REDACTED***`로만 출력됩니다(원칙 V 비밀 격리).

## 3. 자동 검증 스크립트 한 줄 (1분)

```bash
bash scripts/operator_install.sh
```

이 스크립트는 5단계 검증을 수행합니다:

1. CLI 표면 확인 (`auto-invest --help`).
2. `.env`에 필수 키 4종이 빈 값 아닌지 확인.
3. SQLite 감사 로그 마이그레이션 적용 (`data/auto_invest.db`).
4. 워커 dry-run — 룰 파일 파싱, 캡 적용 확인, **브로커 호출 없음**.
5. `auto-invest deploy --dry-run` — 배포 자동화 파이프라인 확인.

성공하면 마지막에 정확히 실행해야 할 `sudo systemctl ...` 명령 6줄을 출력합니다. **이 스크립트는 root로 escalation하지 않습니다** — 운영자가 출력된 명령을 검토한 다음 직접 실행하는 게 안전합니다.

실패하면 어느 단계에서 막혔는지 종료 코드(11~17)로 알려주고, `/tmp/auto-invest-*.log`에 자세한 로그가 남습니다.

## 4. systemd 유닛 설치 + 활성화 (1분)

3단계가 출력한 명령을 그대로 복붙해서 root로 실행:

```bash
sudo install -m 0644 deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
sudo install -m 0644 deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
sudo install -m 0644 deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
sudo systemctl daemon-reload
sudo systemctl enable --now auto-invest.service
sudo systemctl enable --now auto-invest-deploy.timer
```

이 시점에서:
- `auto-invest.service`가 워커를 백그라운드로 띄움 (재시작 정책: 실패 시 10초 후 재시도).
- `auto-invest-deploy.timer`가 미국 장 외 시간대에 30분마다 알아서 `git pull` + 배포.

## 5. 가동 확인 (1분)

```bash
sudo systemctl status auto-invest.service
sudo journalctl -u auto-invest.service -n 50
sudo systemctl list-timers auto-invest-deploy.timer

# 감사 로그에서 직접 확인
sqlite3 /opt/auto-invest/data/auto_invest.db \
  "SELECT ts_utc, event_type FROM audit_log
   ORDER BY seq DESC LIMIT 10;"
```

`WORKER_STARTED` 행이 보이면 가동 성공.

## 자주 막히는 곳

| 증상 | 원인 | 해결 |
|------|------|------|
| 스크립트 종료 코드 12 | `.env` 파일 없음 | `cp .env.example .env` 먼저 |
| 종료 코드 13 | KIS 키 비어 있음 | `.env` 편집, 실제 값 채우기 |
| 종료 코드 14 | `AUTO_INVEST_CAPITAL`가 정수 아님 | 따옴표 없이 `10000` 같은 정수만 |
| 워커가 즉시 죽음 | KIS 키 오타 / 계좌 미활성화 | `journalctl -u auto-invest.service`로 메시지 확인 |
| 배포 타이머가 동작 안 함 | 시간대 / 미국 장중 | 미국 장중(13:30–20:00 UTC)에는 자동 거부. 다음 비장중 슬롯까지 대기 |
| `DEPLOY_KERNEL_TOUCHED` 행이 보임 | 정상 — 헌법 v3.0.0 정보성 신호 | 배포는 계속 진행됨. 그냥 포렌식 기록 |

## 멈출 때

```bash
sudo systemctl disable --now auto-invest-deploy.timer
sudo systemctl stop auto-invest.service

# 즉시 매수/매도 중단을 원하면:
sudo -u auto-invest /usr/local/bin/uv run --directory /opt/auto-invest auto-invest halt --reason "operator pause"
```

## 다음 세션이 이어받는 법

이 가이드대로 가동한 후 다음 세션을 시작하면, 그 세션은 `HANDOFF.md`의
"운영자 사용성 — 지금 바로 가능한 것" 절에서 현재 운영 상태를 파악하고
이어 작업할 수 있습니다.

여기서 다음으로 권장되는 작업(선택):

- **스펙 004 — LLM 판단 지점**: Claude를 거래 결정 루프에 처음 끌어들임. 결정성을 일부 양보, 추론력 획득. 30일치 토큰 텔레메트리(스펙 002)가 쌓인 후 권장.
- **스펙 005 — 자율 튜너**: KPI 임계값 자동 조정. 운영자 손이 더 줄지만 v1엔 필수 아님.

둘 다 안 해도 v1 자동 거래 서비스는 위 절차만으로 무한 가동됩니다.
