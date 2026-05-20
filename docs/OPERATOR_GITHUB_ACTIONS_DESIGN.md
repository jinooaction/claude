# GitHub Actions로 design 자동화 — 운영자 셋업 가이드

운영자(mason)가 인스턴스 콘솔에 두 번 다시 안 들어가도 되는 자율 수행 경로.

GitHub Actions UI에서 한 번 클릭, **또는 매주 자동 실행** (cron schedule).

## 비용 — $0

| 항목 | 비용 |
|------|------|
| `jinooaction/claude` repo | Public (시간 무제한 무료) |
| Anthropic API ($0.02/design 호출) | 변화 없음 (인스턴스에서 직접 호출하든 워크플로우로 호출하든 동일) |
| Vultr 인스턴스 | 변화 없음 |

## 사전 준비 — 한 번만 (~3분, 거의 자동)

### 1단계 — 인스턴스 콘솔에서 단 한 줄 (마지막 콘솔 작업)

Vultr 콘솔 → View Console → root 로그인 후:

```bash
curl -sSL https://raw.githubusercontent.com/jinooaction/claude/main/scripts/operator_one_time_setup.sh | sudo bash
```

이 한 줄이 자동 처리:
- 인스턴스 안에서 SSH 키페어 생성 (운영자 노트북에 키 보관 안 함 — 더 안전)
- 공개키를 `/root/.ssh/authorized_keys`에 등록
- **GitHub Secrets에 복붙할 값 4개를 화면에 한글 안내와 함께 출력**

### 2단계 — 출력된 값 4개를 GitHub Secrets에 복붙 (브라우저, ~2분)

스크립트 출력에 표시된 페이지를 브라우저에서 열기:

> https://github.com/jinooaction/claude/settings/secrets/actions

**"New repository secret"** 버튼을 4번 클릭, 차례대로 화면 출력의 Name/Value 4쌍을 복붙:

| Name | 값의 출처 |
|------|----------|
| `VULTR_SSH_HOST` | 스크립트가 자동 감지한 인스턴스 IP |
| `VULTR_SSH_USER` | `root` |
| `VULTR_SSH_PORT` | `22` |
| `VULTR_SSH_PRIVATE_KEY` | 스크립트 출력의 `----- 여기부터 복사 -----` 부터 `----- 여기까지 복사 -----` 사이 전체 |

⚠️ **개인키 (`VULTR_SSH_PRIVATE_KEY`)는 절대 공유 금지**. Discord/Slack/이메일에 안 됨. GitHub Secrets에만.

**셋업 끝.** 그 후 영구 자율 수행.

## 사용법

### 옵션 A — 자동 실행 (운영자 클릭 0)

워크플로우 파일이 **매주 월요일 UTC 04:00 (KST 13:00, 미국 시장 외 시간)** 자동 실행됩니다 (`schedule: - cron: "0 4 * * 1"`). 운영자가 GitHub UI에서 클릭조차 안 함.

의도(`intent`)를 바꾸려면 `.github/workflows/operator-design.yml`의 `INTENT` 줄을 GitHub UI에서 편집 후 커밋. 또는 schedule을 끄려면 그 줄들을 삭제.

### 옵션 B — 직접 트리거 (UI 1 클릭)

다른 의도로 즉시 실행하고 싶을 때:

1. 저장소 페이지 → **Actions** 탭 → 왼쪽 사이드바에서 **"Operator design (auto-invest)"** 선택.
2. 오른쪽 위 **"Run workflow"** 드롭다운 클릭.
3. 입력 칸:
   - **intent**: design 의도. 기본값 그대로 두거나 수정.
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

## schedule 자동 실행 — 이미 활성화됨

워크플로우 파일에 다음이 이미 들어가 있습니다:

```yaml
on:
  workflow_dispatch:
    ...
  schedule:
    - cron: "0 4 * * 1"   # 매주 월요일 UTC 04:00 (KST 13:00)
```

운영자가 셋업만 끝내면 그 후 매주 자동 design 실행. UI 클릭조차 안 함.

| 주기 변경 | cron 패턴 |
|----------|----------|
| 매일 새벽 4시 UTC | `0 4 * * *` |
| 매주 월요일 새벽 4시 UTC (기본) | `0 4 * * 1` |
| 매월 1일 새벽 4시 UTC | `0 4 1 * *` |
| 멈추기 | `schedule:` 두 줄 삭제 또는 주석 처리 |

의도(intent)는 workflow 파일의 `INTENT` 줄에 적혀 있습니다 — GitHub UI에서 한 줄만 편집하면 됨.
