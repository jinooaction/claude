# 빠른 검증: 모바일 자금·전략 운영판

## 1. 백엔드 계약과 정적 발행물

```bash
cd /Users/mason/Projects/claude-worktrees/codex-183-mobile-capital-strategy
uv run pytest tests/unit/test_mobile_operator_snapshot.py tests/integration/test_mobile_status_page.py
uv run ruff check src tests scripts/generate_mobile_status.py
```

샘플 사이드카로 생성한 `status.json`과 HTML 내 `mobile-status-data`가 완전히 같고, 아래 문자열이
공개 출력에 없어야 한다: `kis_app_key`, `kis_app_secret`, `account_number`, `access_token`,
`ssh_key`. 계좌 총액은 집계 검증 전 `null`과 `UNVERIFIED`여야 한다.

## 2. Flutter 앱

```bash
cd /Users/mason/Documents/flutter-projects/auto_invest_mobile-183
flutter pub get
flutter analyze
flutter test
flutter build ios --release --no-codesign
```

시험은 네 탭, 누락된 확장 요약의 하위 호환, 자금 잠금, 인증 실패, 배경 보호막, 복귀·1분
갱신, 오프라인 캐시, 미래·오래된 원천, 200% 글자 크기를 포함한다.

## 3. 전체 저장소 품질 관문

```bash
cd /Users/mason/Projects/claude-worktrees/codex-183-mobile-capital-strategy
uv run pytest
uv run ruff check src tests
uv run python scripts/agent_harness_probe.py --strict
uv run python scripts/check_handoff_facts.py
```

## 4. 실제 iPhone

연결 상태를 `xcrun devicectl list devices`로 확인한 뒤, 앱 저장소의 기존 설치 스크립트가 있으면
그 스크립트를 사용한다. 없으면 release 서명 빌드 뒤 `xcrun devicectl device install app`으로
설치하고 `com.jinooaction.autoinvest` 프로세스 실행을 확인한다. 잠금 화면, 네 탭, 보호막은
실기기에서 별도 확인하며, 잠금 해제 여부와 화면 확인 여부를 각각 구분해 기록한다.

## 되돌림

백엔드 확장 필드와 `workflow_run` 발행 연결을 되돌리면 기존 필드·예약 발행·HTML은 남는다.
앱은 이전 출시 커밋으로 되돌릴 수 있다. 어느 되돌림도 자본 센티넬, 전략 설정, 주문,
허용목록, 비밀값, 감사 로그를 변경하지 않는다.
