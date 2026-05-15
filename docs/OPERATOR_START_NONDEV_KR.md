# auto-invest — Vultr에서 처음 시작하기 (비개발자용 한글 가이드)

이 문서는 **개발 지식이 없는 분이 Vultr 가상 서버 + KIS 계정으로 자동
거래를 시작하는** 가장 짧은 길입니다. 명령어는 전부 복사-붙여넣기 가능.
각 단계의 예상 시간을 적어두었습니다.

## 시작 전 준비물

- Vultr 계정 (이미 있음).
- KIS Developers 앱 키 / 시크릿 / 미국 주식 거래 가능한 계좌번호 (`KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO`).
- 신용카드 (Vultr 서버 결제용 — 월 약 6달러).
- 운영 자본금 100달러 (처음에는 이 정도로 시작 권장).

## 안전 약속 (꼭 읽기)

- **첫 한 달은 절대 100달러 이상 넣지 마세요.** 시스템이 어떻게 동작하는지 감을 잡은 다음 천천히 늘리세요.
- **첫 1주일은 `--dry-run` 모드로만 운영하세요.** 실제 주문 안 나가고, 감사 로그만 쌓입니다(단계 6 참조). 어떤 결정을 내리는지 관찰한 다음 실주문으로 전환.
- **막혔을 때 무리해서 해결하려 들지 마세요.** 어디서 막혔는지 화면을 그대로 캡처하고 다음 세션을 시작해서 도움을 받으세요.
- **`auto-invest halt --reason "잠깐"` 명령으로 새 주문이 즉시 막힙니다.** 이 명령을 외워두세요.

## 단계 1 — Vultr에서 서버 만들기 (5분)

1. Vultr 콘솔(https://my.vultr.com/) 로그인.
2. 오른쪽 위 **Deploy +** → **Deploy New Server** 클릭.
3. 다음 옵션을 차례로 선택:
   - **Choose Server**: Cloud Compute → Shared CPU.
   - **CPU & Storage Technology**: Regular Performance (가장 저렴).
   - **Server Location**: **Tokyo** (한국에서 가장 빠름). 도쿄가 없으면 Singapore.
   - **Server Image**: **Ubuntu** → **22.04 LTS x64**.
   - **Server Size**: 가장 작은 것 (월 약 6달러, 1 CPU + 1GB RAM + 25GB SSD). 자동 거래에는 이게 충분합니다.
   - **Additional Features**: 다 끄세요 (백업/IPv6 등 필요 없음).
   - **Server Hostname & Label**: 둘 다 `auto-invest`로 적으세요.
4. 페이지 아래 **Deploy Now** 클릭.
5. 1~2분 기다리면 서버가 준비됩니다. 인스턴스 상태가 **Running**이 되면 클릭해서 들어가세요.
6. **반드시 메모**: 인스턴스 페이지에서
   - **IP Address**: 예) `108.61.x.x`
   - **Username**: `root`
   - **Password**: 자동 생성된 값. 눈 모양 아이콘으로 보기 + 복사해서 메모장에 저장.

## 단계 2 — 서버에 웹 브라우저로 접속 (1분)

별도의 SSH 프로그램 필요 없습니다. Vultr가 브라우저 안에서 콘솔을 열어줍니다.

1. 인스턴스 페이지 오른쪽 위 **View Console** 버튼 클릭 (모니터 모양 아이콘).
2. 새 창이 열립니다. `login:` 프롬프트가 보입니다.
3. `root` 입력 후 Enter.
4. `Password:` 프롬프트에 단계 1에서 메모한 비밀번호 붙여넣기 (마우스 우클릭 → 붙여넣기). **타이핑한 글자는 화면에 안 보이지만 정상이에요.** Enter.
5. `root@auto-invest:~#` 같은 프롬프트가 보이면 성공.

## 단계 3 — 서버 기본 도구 설치 (5분, 복붙)

콘솔에 다음 명령을 한 줄씩 붙여넣고 Enter:

```bash
apt update && apt upgrade -y
apt install -y git curl nano build-essential
timedatectl set-timezone UTC
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv --version
```

마지막 줄이 `uv 0.x.x` 같은 버전을 출력하면 OK.

## 단계 4 — 저장소 받기 + 의존성 설치 (3분)

```bash
git clone https://github.com/jinooaction/claude.git /opt/auto-invest
cd /opt/auto-invest
uv sync
```

`uv sync`가 1~2분 걸립니다. 끝나면 다음 줄 프롬프트가 다시 나옵니다.

## 단계 5 — `.env` 파일에 KIS 자격증명 + 자본금 채우기 (3분)

```bash
cp .env.example .env
nano .env
```

`nano` 편집기가 열립니다. 다음 네 줄을 찾아 빈 값을 채우세요:

```
KIS_APP_KEY=여기에_KIS앱키_붙여넣기
KIS_APP_SECRET=여기에_KIS시크릿_붙여넣기
KIS_ACCOUNT_NO=여기에_계좌번호_붙여넣기
AUTO_INVEST_CAPITAL=100
```

저장 + 종료:
- `Ctrl+O` → Enter (저장).
- `Ctrl+X` (종료).

## 단계 6 — 자동 검증 스크립트 실행 (1분)

```bash
bash scripts/operator_install.sh
```

5단계 검증이 차례로 실행됩니다. 전부 통과하면 마지막에 `sudo systemctl ...` 명령 6줄이 출력됩니다.

**실패한 경우**: 종료 코드와 `/tmp/auto-invest-*.log` 내용을 다음 세션에 그대로 가져오세요. 어떤 단계에서 막혔는지 알면 다음 세션이 정확히 도울 수 있습니다.

## 단계 7 — 1주일 dry-run으로 관찰 (1주일)

**처음 1주일은 실제 주문이 안 나가는 dry-run 모드로 운영합니다.** 어떤 결정이 내려지는지 감사 로그를 보며 감을 잡는 시간입니다.

```bash
cd /opt/auto-invest
nohup uv run --env-file .env auto-invest run --dry-run \
    --config tests/fixtures/rules/sample-canary.toml \
    --db data/auto_invest.db \
    --capital 100 > logs/dryrun.out 2>&1 &
echo $! > data/worker.pid
```

워커가 백그라운드로 떠 있고, 콘솔 창을 닫아도 계속 동작합니다. 로그는 `logs/dryrun.out`에서 볼 수 있습니다.

매일 한 번씩 다음 명령으로 감사 로그를 살펴보세요:

```bash
sqlite3 /opt/auto-invest/data/auto_invest.db \
  "SELECT ts_utc, event_type, json_extract(payload_json, '$.symbol') AS symbol
   FROM audit_log
   WHERE ts_utc > datetime('now', '-1 day')
   ORDER BY seq DESC LIMIT 30;"
```

`ORDER_INTENT` 행이 보이면 "어떤 종목을 사려고 했다"는 뜻 (dry-run이라 실제로 안 나감). 일주일치 결정을 보고 마음에 들면 다음 단계로.

워커 멈추기:

```bash
kill $(cat /opt/auto-invest/data/worker.pid) && rm /opt/auto-invest/data/worker.pid
```

## 단계 8 — 실주문 모드로 전환 (자본 100달러 유지)

dry-run 1주일이 만족스러우면:

1. 단계 7의 워커를 멈추세요 (`kill` 명령).
2. `bash scripts/operator_install.sh` 다시 실행. 통과하면 출력된 `sudo systemctl ...` 명령 6줄을 그대로 실행:

```bash
install -m 0644 deploy/auto-invest.service        /etc/systemd/system/auto-invest.service
install -m 0644 deploy/auto-invest-deploy.service /etc/systemd/system/auto-invest-deploy.service
install -m 0644 deploy/auto-invest-deploy.timer   /etc/systemd/system/auto-invest-deploy.timer
systemctl daemon-reload
systemctl enable --now auto-invest.service
systemctl enable --now auto-invest-deploy.timer
```

(Vultr에서는 이미 `root`로 들어가 있으므로 `sudo`를 빼셔도 됩니다.)

가동 확인:

```bash
systemctl status auto-invest.service
journalctl -u auto-invest.service -n 50
```

`WORKER_STARTED` 행이 보이면 실주문 모드로 가동된 것입니다. 이제 진짜 돈이 움직일 수 있습니다.

## 멈출 때 / 일시 중단할 때

**즉시 새 주문 차단** (가지고 있는 포지션은 그대로):

```bash
cd /opt/auto-invest
uv run --env-file .env auto-invest halt --reason "잠깐 멈춤"
```

**완전 정지**:

```bash
systemctl disable --now auto-invest-deploy.timer
systemctl stop auto-invest.service
```

## 자본금을 늘리고 싶을 때 (한 달 관찰 후)

1. 워커 정지: `systemctl stop auto-invest.service`.
2. `.env` 편집: `nano /opt/auto-invest/.env` → `AUTO_INVEST_CAPITAL=500` (예시).
3. 저장 + 종료 후 워커 재시작: `systemctl start auto-invest.service`.
4. 또는 자동 배포 타이머가 다음 주기에 알아서 반영함.

## 비용 정리 (월 기준 예상)

- Vultr 가장 작은 인스턴스: 약 6달러/월 (≒ 8천 원).
- KIS API: 무료 (앱 등록 비용 없음).
- 자본금: 운영자가 직접 설정 (시작 100달러 권장).

## 다음 세션이 도와드리려면 가져올 것

위 단계 중 어디서 막혔는지 + 다음 정보를 준비해 다음 세션을 시작하세요:

1. **단계 번호와 명령어**: "단계 6의 `bash scripts/operator_install.sh`에서 막혔음" 같이 정확한 위치.
2. **오류 메시지 전체**: 콘솔에 빨갛게 뜬 줄을 마우스로 긁어 복사하거나, 화면을 캡처해서 첨부.
3. **종료 코드** (있다면): 예) "Exit code: 13".
4. **로그 파일 내용** (있다면): `cat /tmp/auto-invest-*.log` 명령 결과.

이 정보를 다음 세션 첫 줄에 붙여 넣으시면 그 자리에서 막힌 부분을 풀어드릴 수 있습니다.

## 참고 문서 (선택)

- `docs/OPERATOR_START.md` — 개발자가 쓰는 5분 가이드(이 문서의 축약본).
- `deploy/README.md` — systemd 설치 + 트러블슈팅 표.
- `specs/006-deploy-automation/quickstart.md` — 배포 자동화 동작 원리.
- `HANDOFF.md` — 시스템 전체 현재 상태.
