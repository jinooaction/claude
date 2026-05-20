# GitHub Actions로 design 자동화 — 운영자 셋업 가이드

운영자(mason)가 인스턴스 콘솔에 두 번 다시 안 들어가도 되는 자율 수행 경로.

GitHub Actions UI에서 한 번 클릭만 하면 워크플로우가 SSH로 인스턴스에 접속해서 `auto-invest design`을 실행하고, 결과를 GitHub UI에 출력합니다.

## 비용 — $0

| 항목 | 비용 |
|------|------|
| `jinooaction/claude` repo | Public (시간 무제한 무료) |
| Anthropic API ($0.02/design 호출) | 변화 없음 (인스턴스에서 직접 호출하든 워크플로우로 호출하든 동일) |
| Vultr 인스턴스 | 변화 없음 |

## 사전 준비 — 한 번만 (~5분)

### 1단계 — SSH 키페어 생성 (운영자 노트북에서)

운영자 노트북의 터미널(Windows면 PowerShell, Mac/Linux면 Terminal)에서:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/auto_invest_gh -N ""
```

이 명령은 두 파일을 만듭니다:
- `~/.ssh/auto_invest_gh` (개인키 — GitHub Secrets에 등록할 것)
- `~/.ssh/auto_invest_gh.pub` (공개키 — 인스턴스에 등록할 것)

### 2단계 — 공개키를 인스턴스에 등록 (인스턴스 콘솔에서, 마지막 콘솔 작업)

공개키 내용을 클립보드에 복사:

```bash
# Mac/Linux:
cat ~/.ssh/auto_invest_gh.pub | pbcopy
# Windows PowerShell:
Get-Content ~\.ssh\auto_invest_gh.pub | Set-Clipboard
```

Vultr 콘솔 → View Console → root 로그인 후 다음 한 줄(`PASTED_PUBKEY` 자리에 공개키 붙여넣기):

```bash
echo "PASTED_PUBKEY" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
```

또는 nano로 편집:

```bash
mkdir -p /root/.ssh && nano /root/.ssh/authorized_keys
# 새 줄에 공개키 붙여넣기 → Ctrl+O 저장 → Ctrl+X 종료
chmod 600 /root/.ssh/authorized_keys
```

### 3단계 — GitHub Secrets 등록 (브라우저에서)

저장소 페이지 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

다음 4개 시크릿을 차례로 추가:

| Name | Value | 비고 |
|------|-------|------|
| `VULTR_SSH_HOST` | `202.182.125.132` | 인스턴스 IP 주소 |
| `VULTR_SSH_USER` | `root` | SSH 접속할 사용자 |
| `VULTR_SSH_PRIVATE_KEY` | (개인키 전체 내용 붙여넣기) | `-----BEGIN OPENSSH PRIVATE KEY-----` 부터 `-----END OPENSSH PRIVATE KEY-----` 줄까지 모두 포함 |
| `VULTR_SSH_PORT` | `22` | 기본 포트. 다른 포트면 변경 |

개인키 내용 보는 법:

```bash
# Mac/Linux:
cat ~/.ssh/auto_invest_gh
# Windows PowerShell:
Get-Content ~\.ssh\auto_invest_gh
```

전체 출력을 복사해서 `VULTR_SSH_PRIVATE_KEY` 값에 붙여넣기.

⚠️ **개인키는 절대 공유 금지**. Discord/Slack/이메일에 보내지 말 것. GitHub Secrets에만.

### (선택) 4단계 — SSH 접속 확인

운영자 노트북에서:

```bash
ssh -i ~/.ssh/auto_invest_gh root@202.182.125.132 "whoami; uname -a"
```

`root` + 인스턴스 OS 정보가 출력되면 셋업 성공. 종료(`exit`).

## 사용법 — GitHub UI에서 클릭만

1. 저장소 페이지 → **Actions** 탭 → 왼쪽 사이드바에서 **"Operator design (auto-invest)"** 선택.
2. 오른쪽 위 **"Run workflow"** 드롭다운 클릭.
3. 입력 칸:
   - **intent**: design 의도. 기본값 `"자본 100달러, 미국 대형주 분산, 매주 월요일 적립, 위험 보통"` 그대로 두거나 수정.
   - **auto_ok**:
     - `true` (기본) — 검증 통과 즉시 라이브 worker 자동 시작.
     - `false` — 검증된 룰만 출력하고 종료. 운영자가 결과 보고 만족하면 `true`로 다시 실행.
4. 초록색 **"Run workflow"** 버튼 클릭.
5. 워크플로우 실행 페이지로 이동 → 1~3분 내 완료.

## 결과 확인

| 결과 | 의미 | 다음 단계 |
|------|------|----------|
| ✅ 정상 종료, `auto_ok=true` | 라이브 worker subprocess 시작됨. dry-run/live는 `.env`의 `AUTO_INVEST_MODE` 기준 | 1주일 dry-run 관찰 후 `AUTO_INVEST_MODE=live`로 전환 |
| ✅ 정상 종료, `auto_ok=false` | 룰 검증 통과 + audit_log 기록. 라이브 시작 안 함 | 룰 확인 후 `auto_ok=true`로 재실행 (Anthropic 비용 ~$0.02 추가) |
| ❌ 실패 | 로그의 마지막 줄 확인 | 의도 문구 다듬기 / KIS·Anthropic 키 재확인 |

## 자주 발생하는 함정

### `Authentication failed` (SSH)

- 공개키가 `/root/.ssh/authorized_keys`에 정확히 들어갔는지 확인.
- 줄바꿈/공백 깨졌는지 확인 — 공개키는 한 줄.
- `chmod 600 /root/.ssh/authorized_keys` 권한 확인.

### `VULTR_SSH_PRIVATE_KEY 가 SSH 개인키 형식이 아닙니다`

- 개인키를 복사할 때 `-----BEGIN OPENSSH PRIVATE KEY-----` 와 `-----END OPENSSH PRIVATE KEY-----` 줄을 포함했는지 확인.
- 줄바꿈 제거되면 안 됨 — 전체 멀티라인 그대로 붙여넣기.

### `required secret(s) missing from environment`

- 이는 인스턴스의 `.env` 에 KIS 키가 없다는 뜻. workflow가 자동으로 `set_secrets.sh`를 호출하지 않습니다 (interactive prompt이므로 SSH non-interactive 환경에서 못 받음).
- 한 번만 인스턴스 콘솔에 들어가 `bash /opt/auto-invest/scripts/set_secrets.sh` 실행 후 다시 워크플로우 트리거.

## 보안 메모

- 이 워크플로우는 GitHub Secrets에 저장된 SSH 개인키를 GitHub Actions runner에 임시 설치합니다. runner는 워크플로우 종료 후 자동 폐기됩니다.
- repo가 public이므로 워크플로우 로그도 public — KIS 잔고, Claude 응답, 룰 TOML이 모두 노출됩니다. 민감 정보 노출이 우려되면 repo를 private으로 전환하세요 (Settings → Danger Zone → Change visibility).
- Anthropic API 키, KIS 키는 `.env`에만 있고 워크플로우 로그에는 절대 노출되지 않습니다 (logging_config의 register_secret가 마스킹).

## 자동 실행 (선택 — 더 강력한 자율 수행)

GitHub Actions는 cron schedule도 지원합니다. workflow 파일 상단의 `on:` 블록을 다음처럼 확장하면 매일 자동 실행:

```yaml
on:
  workflow_dispatch:
    ...
  schedule:
    - cron: "0 4 * * *"   # 매일 UTC 04:00 (KST 13:00, 미국 시장 외 시간)
```

단, schedule 트리거는 `inputs`를 받을 수 없으므로 의도가 고정됨. 의도를 매번 다르게 하려면 `workflow_dispatch`만 사용.
