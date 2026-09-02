# 작업 목록: 읽기 전용 Flutter 운영자 앱

**입력**: `specs/178-flutter-operator-mobile/`의 설계 문서  
**전제**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

## Phase 1: 설정과 설계

- [x] T001 격리 worktree와 `codex/178-flutter-operator-mobile` 브랜치를 준비한다
- [x] T002 [P] `specs/178-flutter-operator-mobile/spec.md`에 목표·비목표·안전 경계·인수 조건을 기록한다
- [x] T003 [P] `specs/178-flutter-operator-mobile/plan.md`, `research.md`, `data-model.md`를 작성한다
- [x] T004 [P] `specs/178-flutter-operator-mobile/design-system.md`, `screen-blueprint.md`, `assets/home-concept.png`로 선택 디자인을 고정한다
- [x] T005 `specs/178-flutter-operator-mobile/contracts/mobile-status-v1.schema.json`과 `quickstart.md`를 작성한다
- [x] T006 개인 Flutter 스타터로 `/Users/mason/Documents/flutter-projects/auto_invest_mobile`을 만들고 별도 Git 저장소를 초기화한다

---

## Phase 2: 공통 기반

- [x] T007 공개 JSON 계약 시험을 `tests/integration/test_mobile_status_page.py`에 먼저 추가하고 실패를 확인한다
- [x] T008 `scripts/generate_mobile_status.py`에 버전이 붙은 읽기 전용 JSON 출력과 `--json-output`을 구현한다
- [x] T009 `.github/workflows/mobile-status-pages.yml`에서 기존 HTML과 함께 `status.json`을 발행한다
- [x] T010 Flutter 의존성과 앱 환경을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/pubspec.yaml` 및 `lib/core/config/app_environment.dart`에 구성한다
- [x] T011 Flutter 공통 상태 모델과 캐시·저장소 인터페이스를 `lib/features/status/domain/mobile_status.dart`, `data/status_cache.dart`, `data/status_repository.dart`에 구현한다

---

## Phase 3: 사용자 이야기 1 - 지금 상태를 한눈에 확인 (P1)

**목표**: 전체 판정, 다음 행동, 네 핵심 영역과 기준 시각을 5초 안에 찾는다.

**독립 시험**: 정상·주의·위험 자료를 주입해 홈의 최상단 판정과 요약이 정확한지 확인한다.

- [x] T012 [P] [US1] JSON 버전·필수 필드·운영자 요약 파싱 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/mobile_status_test.dart`에 추가한다
- [x] T013 [P] [US1] 정상·주의·위험 홈 위젯 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/widget_test.dart`에 추가한다
- [x] T014 [US1] 상태 로드 제어를 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/features/status/application/status_controller.dart`에 구현한다
- [x] T015 [US1] 홈 화면을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/features/status/presentation/home_screen.dart`에 구현한다
- [x] T016 [US1] 앱·라우터·셸을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/app/app.dart`, `router.dart`, `features/status/presentation/status_shell.dart`에 연결한다

---

## Phase 4: 사용자 이야기 2 - 자동화 세부 상태 확인 (P2)

**목표**: 핵심·보조 자동화를 위험도 순서로 보고 근거 기록을 읽기 전용으로 연다.

**독립 시험**: 정상·지연·누락 항목을 섞어 위험·핵심 우선 정렬과 상세 필드를 확인한다.

- [x] T017 [P] [US2] 자동화 파싱·정렬 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/mobile_status_test.dart`에 추가한다
- [x] T018 [P] [US2] 자동화 목록과 기록 버튼 위젯 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/widget_test.dart`에 추가한다
- [x] T019 [US2] 자동화 화면을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/features/status/presentation/automation_screen.dart`에 구현한다

---

## Phase 5: 사용자 이야기 3 - 오래되거나 끊긴 정보에 속지 않기 (P1)

**목표**: 30시간 초과·미래 시각·네트워크 실패·손상 자료가 신선한 정상으로 보이지 않는다.

**독립 시험**: 오프라인 캐시, 캐시 없는 실패, 오래된 자료와 미지원 버전을 각각 주입한다.

- [x] T020 [P] [US3] 캐시·네트워크·손상·30시간 신선도 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/status_repository_test.dart`에 추가한다
- [x] T021 [P] [US3] 오프라인·지연·확인 불가 배너 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/widget_test.dart`에 추가한다
- [x] T022 [US3] 마지막 성공 캐시와 실패 폐쇄 새로고침을 `lib/features/status/data/`와 `application/status_controller.dart`에 완성한다

---

## Phase 6: 사용자 이야기 4 - 친근하지만 정확한 금융 화면 (P2)

**목표**: 선택한 클레이모피즘을 작은 화면과 큰 글자에서도 정확하게 읽는다.

**독립 시험**: 320픽셀 폭과 200% 글자 크기에서 홈·자동화·설명의 핵심 문구가 잘리지 않는지 확인한다.

- [x] T023 [P] [US4] 색상·윤곽·그림자·타이포 토큰을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/app/theme.dart`에 구현한다
- [x] T024 [P] [US4] `ClayCard`, 상태 배지, 신선도 배너를 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/core/widgets/clay_card.dart`에 구현한다
- [x] T025 [US4] 설명 화면을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/lib/features/status/presentation/about_screen.dart`에 구현한다
- [x] T026 [US4] 3개 탭 접근성, 44×44 터치 영역과 큰 글자 반응형 시험을 `/Users/mason/Documents/flutter-projects/auto_invest_mobile/test/widget_test.dart`에 완성한다

---

## Phase 7: 검증·배포·인계

- [x] T027 `uv run pytest tests/integration/test_mobile_status_page.py`와 관련 Ruff 검사를 통과한다
- [x] T028 auto-invest 전체 `uv run pytest`와 `uv run ruff check src tests`를 통과한다
- [x] T029 등급 2 관문인 `uv run python scripts/agent_harness_probe.py --strict`와 `uv run python scripts/check_handoff_facts.py`를 통과한다
- [x] T030 Flutter `dart format`, `flutter analyze`, `flutter test`를 순차 통과한다
- [ ] T031 Flutter iOS 릴리스 빌드·서명·연결된 실제 iPhone 설치·실행을 확인한다
- [ ] T032 두 저장소의 변경을 커밋·푸시하고 auto-invest PR 본문 품질 관문을 검사한 뒤 조건 충족 시 merge 방식으로 자동 머지한다
- [ ] T033 `HANDOFF.md`에 JSON 발행·앱 저장소·검증·남은 위험을 기록하고 사실 검사와 후속 PR/머지를 닫는다

## 의존성과 실행 순서

- Phase 2는 T006 뒤에 시작하며 모든 사용자 이야기의 공통 기반이다.
- US1과 US3가 첫 안전 MVP이며, US2와 US4는 같은 모델·셸 위에 붙는다.
- 각 시험 작업은 해당 구현 전에 작성하고 실패를 확인한다.
- T027~T033은 모든 구현이 끝난 뒤 순서대로 수행한다.
- 실거래·주문·자본·전략·중단 해제 기능은 이 작업 목록에 존재하지 않으며 별도 명세와 운영자 승인이 필요하다.
