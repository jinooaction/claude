# auto-invest — GitHub Actions로 Vultr 인스턴스 자동 생성 (비개발자용)

운영자가 클릭 두 번으로 자동 거래용 클라우드 서버가 가동되는 가장 자율적인 길.
이 길에서 운영자가 손대는 곳은 단 세 군데:

1. GitHub Secrets에 Vultr 토큰 한 번 박기
2. Actions 탭에서 워크플로우 한 번 실행
3. 인스턴스 가동 후 Vultr 콘솔에서 KIS 키 한 번 입력 (`set_secrets.sh`)

## 1단계 — Vultr 토큰 발급 (1분)

1. https://my.vultr.com/settings/#settingsapi 열기.
2. **API** 토글이 OFF면 ON으로.
3. **Access Control** 섹션의 **Allowed Subnet**에 `0.0.0.0/0`을 추가하세요. GitHub Actions runner의 IP가 매번 바뀌므로 IP 제한을 풀어야 합니다.
   - 토큰 폐기 + IP 제한 다시 좁히기는 작업 끝난 후 운영자가 챙기는 단계입니다 (3단계 끝나고).
4. **Personal Access Token** 영역의 토큰 문자열을 복사. (없으면 **"Regenerate"** 클릭으로 새로 발급. 이전에 발급한 토큰이 있으면 그것을 그대로 쓰셔도 됩니다.)

## 2단계 — GitHub Secrets에 토큰 박기 (2분)

1. 이 저장소의 GitHub 페이지로 이동: https://github.com/jinooaction/claude
2. 저장소 상단 메뉴 **Settings** 클릭. (탭은 Code / Issues / Pull requests / ... / **Settings**)
3. 왼쪽 메뉴에서 **Secrets and variables** → **Actions** 클릭.
4. 가운데 페이지 오른쪽 위 **"New repository secret"** 초록 버튼 클릭.
5. 두 칸 채우기:
   - **Name**: `VULTR_API_KEY` (정확히 이 이름)
   - **Secret**: (1단계에서 복사한 Vultr 토큰 문자열)
6. **"Add secret"** 클릭.

이제 GitHub Actions가 이 토큰을 안전하게 읽을 수 있습니다 (UI에서는 다시 안 보임).

## 3단계 — 워크플로우 실행 (1분 클릭 + 10분 자동 대기)

1. 저장소 상단 메뉴 **Actions** 탭 클릭.
2. 왼쪽 사이드바에서 **"Provision Vultr instance (auto-invest)"** 클릭.
3. 페이지 오른쪽에 나타나는 **"Run workflow"** 회색 버튼 클릭.
4. 작은 드롭다운이 열리면서 입력 양식이 보임:
   - **Branch**: `main` (그대로)
   - **시작 자본금 (USD)**: `100` (기본값 그대로 권장)
   - **Vultr 리전 ID**: `nrt` (Tokyo, 기본값)
   - **Vultr 플랜 ID**: `vc2-1c-1gb` (월 약 6달러, 기본값)
   - **인스턴스 라벨/호스트명**: `auto-invest` (기본값)
5. 초록 **"Run workflow"** 버튼 클릭.

워크플로우가 약 5~10분 동안 다음을 자동 수행:

| 단계 | 내용 |
|------|------|
| 1 | 저장소 체크아웃 |
| 2 | Vultr 토큰 검증 |
| 3 | Ubuntu 22.04 OS ID 조회 |
| 4 | cloud-init User-Data 빌드 (자본금 값 박아넣음) |
| 5 | Vultr API로 Tokyo 인스턴스 생성 |
| 6 | 인스턴스 IP 할당 대기 |
| 7 | **Workflow Summary에 인스턴스 IP + 다음 단계 안내 출력** |

완료되면 workflow run 페이지에 초록 체크 ✅ 가 뜨고, **"Summary"** 섹션에서 인스턴스 IP와 다음 단계가 친절히 안내됩니다.

## 4단계 — Vultr 콘솔에서 KIS 키 입력 (5분)

워크플로우 Summary에 적힌 그대로:

1. Vultr 콘솔의 인스턴스 페이지 링크 클릭 (Summary에 적힌 URL).
2. **Overview** 탭에서 **Password** 필드의 눈 모양 아이콘 클릭 → root 비밀번호 보기 → 복사.
3. 같은 페이지 오른쪽 위 **"View Console"** 버튼 클릭 (브라우저 안에서 콘솔 창 열림).
4. `auto-invest login:` 프롬프트가 보이면:
   - 사용자명: `root` 입력 → Enter
   - 비밀번호: 마우스 우클릭 → 붙여넣기 → Enter (입력 글자는 화면에 안 보임)
5. 콘솔 프롬프트(`root@auto-invest:~#`)가 보이면 다음 한 줄을 붙여넣고 Enter:

   ```bash
   bash /opt/auto-invest/scripts/set_secrets.sh
   ```

6. 세 가지 prompt가 차례로 뜸 (입력값은 화면에 안 보임):

   ```
   KIS_APP_KEY:               ← KIS 앱 키 붙여넣기 + Enter
   KIS_APP_SECRET:            ← KIS 시크릿 붙여넣기 + Enter
   KIS_ACCOUNT_NO (계좌번호): ← 계좌번호 붙여넣기 + Enter
   ```

7. `OK — auto-invest.service 가 정상 가동 중입니다 (dry-run 모드).` 메시지가 보이면 끝.

## 5단계 — 작업 끝났으니 Vultr 토큰 정리 (1분)

이 단계가 가장 중요한 안전 조치입니다. GitHub Secrets에 토큰이 박혀 있지만, Vultr 콘솔에서도 토큰을 폐기하면 만에 하나 GitHub 토큰이 노출돼도 안전.

1. https://my.vultr.com/settings/#settingsapi 다시 열기.
2. **"Regenerate"** 클릭 → 토큰이 새로 발급되고 이전 토큰 즉시 무효.
   - 또는 **API** 토글 OFF → 모든 토큰 무효.
3. (선택) Access Control의 `0.0.0.0/0`도 제거하셔도 됩니다 (어차피 API OFF면 무관).

## 그 후 — 매일 / 매주 운영

워커가 dry-run 모드로 1주일 동안 자동으로 굴러갑니다. 매일 한 번 Vultr 콘솔로 들어가 콘솔에서 다음 한 줄로 감사 로그 확인:

```bash
sqlite3 /opt/auto-invest/data/auto_invest.db \
  "SELECT ts_utc, event_type, json_extract(payload_json, '\$.symbol') AS symbol
   FROM audit_log
   WHERE ts_utc > datetime('now', '-1 day')
   ORDER BY seq DESC LIMIT 30;"
```

`ORDER_INTENT` 행이 자주 보이면 "이런 종목을 사려고 했다" (dry-run이라 실제 주문 안 나감). 1주일 후 만족스러우면 실주문 전환 (한 줄):

```bash
sed -i 's/^AUTO_INVEST_MODE=.*/AUTO_INVEST_MODE=live/' /opt/auto-invest/.env \
  && systemctl restart auto-invest.service
```

이제 진짜 돈이 움직입니다. **첫 한 달은 자본금 100달러 유지** 권장.

## 안전 약속 (꼭 지키기)

- 첫 한 달 자본금 100달러 이상 금지.
- 첫 1주일 dry-run만.
- `auto-invest halt --reason "잠깐"` 명령으로 즉시 새 주문 차단 가능.

## 막혔을 때 다음 세션에 가져올 것

| 어디서 막힘 | 가져올 정보 |
|------------|------------|
| GitHub Secrets 추가 단계 | Settings → Secrets 화면 캡처 |
| Run workflow 클릭 | Actions 탭 화면 캡처 |
| 워크플로우 실행 중 실패 | 실패한 step의 로그 (Actions → 실패한 run 클릭 → 빨간 step 펼치기 → 로그 복사) |
| 인스턴스는 만들어졌지만 set_secrets.sh 실행 시 | 콘솔 출력 캡처 + `cat /var/log/auto-invest-cloud-init.log` 결과 |

## 멈출 때

```bash
# 새 주문만 차단 (포지션은 그대로):
cd /opt/auto-invest && uv run --env-file .env auto-invest halt --reason "잠깐"

# 워커 완전 정지:
systemctl disable --now auto-invest-deploy.timer
systemctl stop auto-invest.service

# 인스턴스 완전 삭제 (월 비용 0):
# Vultr 콘솔 → 인스턴스 페이지 → Settings → Destroy Server
```

## 참고 — 다른 운영자 시작 가이드

- `docs/OPERATOR_VULTR_ONE_STEP_KR.md` — 운영자가 Vultr 콘솔에서 인스턴스를 직접 만드는 경로 (GitHub Actions 안 쓰는 버전).
- `docs/OPERATOR_START_NONDEV_KR.md` — 명령어를 손으로 한 줄씩 학습하는 경로.
- `docs/OPERATOR_START.md` — 개발자용 5분 가이드.
