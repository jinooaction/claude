# auto-invest — Vultr 한 번에 가동 (비개발자용, 진짜 한 단계)

이 길은 운영자가 **딱 한 번** 클릭 + 붙여넣기만 하면, 그 후로는 인스턴스가
부팅과 동시에 모든 셋업을 알아서 끝내고 dry-run 모드로 자동 가동합니다.
콘솔에 들어가 명령어를 칠 필요가 없습니다.

이게 헌법 IX.D 운영자 자율 수행 보장의 정신에 가장 가까운 길입니다.

## 운영자가 해야 할 일 (단 한 번)

### 1. Vultr 콘솔에서 새 인스턴스 만들기 (3분)

1. https://my.vultr.com/ 로그인 → **Deploy + → Deploy New Server**.
2. 다음 옵션 선택:
   - **Choose Server**: Cloud Compute → Shared CPU.
   - **CPU & Storage Technology**: Regular Performance.
   - **Server Location**: **Tokyo** (한국 가까움).
   - **Server Image**: **Ubuntu 22.04 LTS x64**.
   - **Server Size**: 가장 작은 것 (월 약 6달러, 1 CPU + 1GB RAM).
3. 페이지 아래로 스크롤해서 **Additional Features** 옆 / 또는 **Server Hostname & Label** 위쪽에 있는 **"View advanced features"** 또는 **"Cloud-Init User-Data"** 영역을 펼치세요.

### 2. User-Data에 스크립트 + KIS 키 한 번에 붙여넣기 (3분)

저장소의 `deploy/vultr-userdata.sh` 파일을 통째로 복사해서 User-Data 칸에 붙여넣고, **그 안의 네 줄만** 채워주세요:

```bash
KIS_APP_KEY="여기에_KIS앱키"          # ← 실제 KIS 앱 키로 교체
KIS_APP_SECRET="여기에_KIS시크릿"      # ← 실제 KIS 시크릿으로 교체
KIS_ACCOUNT_NO="여기에_계좌번호"        # ← 실제 미국 주식 계좌번호로 교체
AUTO_INVEST_CAPITAL="100"               # ← 시작 자본금 (100달러 권장)
```

스크립트 전체 파일은 GitHub에서 바로 보실 수 있어요:
https://github.com/jinooaction/claude/blob/main/deploy/vultr-userdata.sh

**Hostname & Label**: `auto-invest`로.

### 3. Deploy Now 클릭 (1번)

끝.

## 그 후로 자동으로 일어나는 일 (5~10분)

인스턴스가 부팅되면서 cloud-init이 8단계를 차례로 실행합니다:

| 단계 | 내용 |
|------|------|
| 1 | 우분투 시스템 업데이트 + git/curl/nano/sqlite3 설치 |
| 2 | 타임존을 UTC로 |
| 3 | `auto-invest` 시스템 계정 생성 + 디렉토리 권한 |
| 4 | `uv` (파이썬 환경 관리자) 설치 |
| 5 | 저장소 클론 + 의존성 설치 |
| 6 | `.env` 생성 — KIS 키 4줄을 chmod 0600으로 디스크에 저장 |
| 7 | SQLite 감사 로그 마이그레이션 |
| 8 | systemd 유닛 설치 + 활성화 → **워커 dry-run 모드로 가동** |

5~10분 후 인스턴스 IP로 SSH 들어가거나 Vultr 웹 콘솔로 접속해서 다음 한 줄로 가동 상태 확인:

```bash
systemctl status auto-invest.service
```

`active (running)` + 최근 `WORKER_STARTED` 행이 보이면 성공.

## 1주일 dry-run 후 실주문 전환 (한 줄)

워커가 dry-run 모드로 1주일 굴러가는 동안 매일 한 번 감사 로그를 확인:

```bash
sqlite3 /opt/auto-invest/data/auto_invest.db \
  "SELECT ts_utc, event_type, json_extract(payload_json, '\$.symbol') AS symbol
   FROM audit_log
   WHERE ts_utc > datetime('now', '-1 day')
   ORDER BY seq DESC LIMIT 30;"
```

`ORDER_INTENT` 행이 자주 보이면 "이런 종목을 사려고 했다" — dry-run이라 실제 주문은 안 나갔습니다.

만족스러우면 실주문으로 전환 (한 줄):

```bash
sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \
  && systemctl restart auto-invest.service
```

이제 진짜 돈이 움직입니다. 첫 한 달은 자본금 100달러 유지 권장.

## 멈출 때 (즉시 새 주문 차단)

```bash
cd /opt/auto-invest && uv run --env-file .env auto-invest halt --reason "잠깐"
```

가지고 있는 포지션은 그대로, 새 매수/매도만 차단.

완전 정지:

```bash
systemctl disable --now auto-invest-deploy.timer
systemctl stop auto-invest.service
```

## 자본금 늘리기 (한 달 관찰 후)

```bash
sed -i 's/^AUTO_INVEST_CAPITAL=.*/AUTO_INVEST_CAPITAL=500/' /opt/auto-invest/.env \
  && systemctl restart auto-invest.service
```

## 안전 약속 (꼭 지키기)

- **첫 한 달 자본금 100달러 이상 금지.** 시스템 감 잡은 다음 천천히.
- **첫 1주일 dry-run만.** `.env`의 `AUTO_INVEST_MODE=dry-run` 그대로 두기.
- **`auto-invest halt`** 명령 외워두기 — 이상 시 즉시 새 주문 차단.

## 막혔을 때 다음 세션에 가져올 것

1. 어디서 막혔는지 (예: "Deploy Now 클릭했는데 인스턴스가 안 만들어짐", "10분 기다려도 systemctl status가 inactive").
2. cloud-init 로그: `cat /var/log/auto-invest-cloud-init.log` (Vultr 웹 콘솔에서 root 로그인 후).
3. 워커 로그: `journalctl -u auto-invest.service -n 100`.
4. 스크린샷이면 더 좋음.

다음 세션은 `HANDOFF.md`를 읽고 자동으로 이 길을 따라가고 있다는 걸 알아챕니다.

## 비교: 왜 이 길이 더 자율적인가

| 항목 | `OPERATOR_START_NONDEV_KR.md` (이전) | `OPERATOR_VULTR_ONE_STEP_KR.md` (이 문서) |
|------|--------------------------------------|------------------------------------------|
| 운영자가 직접 실행할 명령어 수 | 약 15줄 | **0줄 (붙여넣기만)** |
| 웹 콘솔/SSH 접속 횟수 | 7~10번 | **0번 (가동까지)** |
| 막힐 수 있는 단계 수 | 8개 | **1개 (User-Data 붙여넣기)** |
| KIS 키 입력 방식 | nano 편집기로 .env 손편집 | Vultr User-Data 한 칸에 한 번 |
| 1주일 후 실주문 전환 | systemd disable/enable 2줄 | `sed` + `restart` 한 줄 |

운영자가 해야 하는 일은 **Vultr 콘솔에서 한 번의 양식 작성 + Deploy 클릭**, 그게 전부입니다.
