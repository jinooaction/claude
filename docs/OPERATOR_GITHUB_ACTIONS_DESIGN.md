# GitHub Actions로 design 후보 생성

이 워크플로는 운영자가 GitHub UI에서 수동으로 실행하는 제안 전용 경로입니다.
예약 실행과 자동 확인 입력은 제거됐습니다. 정상 종료는 룰 후보와 검증 상태가
생성됐다는 뜻이며, 실거래 프로세스 시작이나 실제 주문을 뜻하지 않습니다.

## 사전 준비

GitHub Actions Secret 5개가 필요합니다.

| Name | 용도 |
|------|------|
| `VULTR_SSH_HOST` | 운영 인스턴스 주소 |
| `VULTR_SSH_USER` | 제한된 deploy SSH 사용자(root 금지) |
| `VULTR_SSH_PORT` | SSH 포트 |
| `VULTR_SSH_PRIVATE_KEY` | Actions에서 임시로 사용할 SSH 개인키 |
| `VULTR_SSH_KNOWN_HOSTS` | 서버 SSH host key 고정값 |

인스턴스의 `.env`에는 KIS 키와 `ANTHROPIC_API_KEY`가 이미 있어야 합니다.

서버에는 먼저 제한 SSH 경계가 설치되어 있어야 합니다. root 콘솔 또는 이미
검증된 out-of-band root SSH에서 fresh 공개키를 넣어 다음을 실행합니다.

```bash
DEPLOY_PUBLIC_KEY="$(cat ~/.ssh/auto_invest_gh.pub)" \
  sudo -E bash /opt/auto-invest/deploy/repair-ssh-boundary.sh
```

서버가 아직 이전 SHA라 이 파일이 없으면, GitHub raw 파일을 임시 파일로 받은 뒤
내용과 `bash -n`을 확인하고 실행합니다. 원격 코드를 root shell에 바로 pipe하지 않습니다.

이 스크립트는 `gh-deploy` 같은 non-root deploy 사용자를 만들고,
`authorized_keys`에는 forced-command gateway만 허용합니다. 또한 예전
`github-actions@auto-invest` root 키 항목과 `/root/.ssh/auto_invest_gh`
파일을 별도 retired 디렉터리로 옮깁니다. GitHub에는 이 fresh deploy 키의
개인키를 `VULTR_SSH_PRIVATE_KEY`로 등록하고, `VULTR_SSH_USER`는 root가 아닌
deploy 사용자로 둡니다.

## 실행

1. 저장소 페이지 → **Actions** 탭 → **Operator design (auto-invest)** 선택.
2. **Run workflow** 클릭.
3. `intent`에 자연어 의도를 입력.
4. 실행 로그에서 후보 파일, `.proposal.json` 검증 보고서, 후보 지문, 검증 상태를 확인.
   실행 로그와 `.verify/last_design.md`에는 입력 의도 원문 대신 길이와 SHA-256
   지문이 남습니다.

워크플로는 intent 원문을 원격 셸 명령 문자열에 직접 넣지 않습니다. runner에서
base64 데이터로 바꾼 뒤 원격 도우미가 다시 디코딩합니다.

## 결과 해석

| 결과 | 의미 | 다음 단계 |
|------|------|----------|
| 정상 종료 + `PROPOSAL_ONLY` | 후보 파일과 `.proposal.json` 검증 보고서가 생성됨 | 기존 backtest → paper/forward → canary → 승인된 live 경로로 후보 승격 |
| `WAIT_DYNAMIC_VALIDATION` | 동적 증거가 아직 없음 | 백테스트와 paper/모의 검증을 별도 실행 |
| 실패 | 후보 생성 또는 정적 검증 실패 | 로그의 마지막 원인을 보고 의도·키·설정을 수정 |

## 비용

수동 실행할 때만 Anthropic API 호출 비용이 발생합니다. 예약 실행은 제거됐으므로
운영자가 트리거하지 않은 반복 비용은 발생하지 않습니다.

## 보안 메모

- GitHub Secrets 값은 로그에 출력하지 않습니다.
- GitHub에는 서버 root 개인키를 넣지 않습니다. root 접속 사용자는 워크플로에서 거부됩니다.
- deploy-on-merge와 셋업 검증은 서버 gateway의 `sync-units`, `start-deploy`,
  `deploy-journal`, `status` 같은 고정 명령만 호출합니다.
- SSH host key는 `VULTR_SSH_KNOWN_HOSTS`와 `StrictHostKeyChecking=yes`로 고정합니다.
- repo가 public이면 실행 로그도 노출될 수 있습니다. 워크플로는 의도 원문 대신
  길이와 SHA-256 지문만 남기지만, 생성 룰과 검증 결과에 민감한 계좌 정보나
  비밀값을 넣지 않습니다.
- 이 워크플로는 후보 생성용 SSH 실행만 수행합니다. live sentinel, 자본, caps,
  whitelist, 운영 서버 `.env`를 바꾸지 않습니다.

## 더 이상 지원하지 않는 동작

- 예약 design 실행
- 검증 후 자동 확인 입력
- design 결과에서 직접 실거래 프로세스 시작
- `design` 결과만으로 live 설정 변경
