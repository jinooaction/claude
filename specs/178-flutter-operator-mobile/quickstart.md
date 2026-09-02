# 빠른 확인 안내

## 공개 상태 계약

격리된 auto-invest 작업 공간에서 구조화 상태를 생성한다.

```bash
uv run python scripts/generate_mobile_status.py \
  --output /tmp/mobile-status.html \
  --json-output /tmp/status.json
```

관련 시험과 정적 검사를 먼저 실행한다.

```bash
uv run pytest tests/integration/test_mobile_status_page.py
uv run ruff check scripts/generate_mobile_status.py tests/integration/test_mobile_status_page.py
```

발행 뒤 기본 주소는 다음과 같다.

```text
https://jinooaction.github.io/claude/status.json
```

## Flutter 앱

```bash
cd /Users/mason/Documents/flutter-projects/auto_invest_mobile
flutter pub get
flutter analyze
flutter test
flutter build ios --release
```

앱은 위 공개 주소를 기본으로 사용한다. 시험에서는 네트워크와 캐시 구현을 주입해 실제 외부
상태와 무관하게 정상·주의·위험·오프라인·손상 상황을 재현한다.

## 실패 상황 확인

- 네트워크를 끄고 재실행하면 마지막 성공 자료와 오프라인 배너가 함께 보인다.
- 앱 자료 생성 시각을 30시간보다 과거로 바꾸면 전체 상태가 신선한 정상으로 보이지 않는다.
- 필수 필드나 형식 버전을 바꾸면 “상태를 확인할 수 없음” 또는 지원하지 않는 버전으로 보인다.
- 자료에 알 수 없는 상태값을 넣으면 원문을 유지한 “알 수 없음”으로 보인다.
- 캐시를 지우고 첫 조회를 실패시키면 빈 대시보드 대신 실패 안내가 보인다.

## iPhone 확인

1. `xcrun devicectl list devices`로 연결·신뢰·개발자 모드 상태를 확인한다.
2. 서명된 릴리스 앱을 실제 iPhone에 설치하고 실행한다.
3. 홈의 판정·다음 행동·신선도, 세 탭 이동, 수동 새로고침과 외부 기록 링크를 확인한다.
4. 글자 크기를 키워 카드 겹침과 잘림이 없는지 확인한다.

빌드 통과만으로 기기 검증 완료라고 보지 않는다. 잠금, 신뢰, 개발자 모드나 서명이 막으면
정확한 외부 관문을 남긴다.
