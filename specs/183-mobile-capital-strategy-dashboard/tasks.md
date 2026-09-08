# 작업 목록: 모바일 자금·전략 운영판

**입력**: `/specs/183-mobile-capital-strategy-dashboard/`의 명세·계획·조사·데이터 모델·계약  
**시험 원칙**: 돈의 의미, 미확인 값, 읽기 전용 경계, 신선도와 사생활 보호는 구현 전에
실패 시험으로 고정하고 각 사용자 이야기를 독립 검증한다.

## 1단계: 준비

- [x] T001 백엔드 `/Users/mason/Projects/claude-worktrees/codex-183-mobile-capital-strategy`와 앱 `/Users/mason/Documents/flutter-projects/auto_invest_mobile-183`의 격리 브랜치·기준 커밋·작업 트리를 기록한다.
- [x] T002 앱 `pubspec.yaml`, iOS `Info.plist`, Android `AndroidManifest.xml`에 기기 인증 의존성과 설명을 추가하고 `flutter pub get`으로 잠금 파일을 갱신한다.
- [x] T003 [P] JSON 계약 파일 `specs/183-mobile-capital-strategy-dashboard/contracts/mobile-status-summary-v1.schema.json`의 구문과 하위 호환 필드를 검사한다.

## 2단계: 공통 기반

- [x] T004 `tests/unit/test_mobile_operator_snapshot.py`에 허용 필드, 미확인 계좌, 검증된 0, 손상 원천, 미래 시각과 금지 문자열 시험을 먼저 추가한다.
- [x] T005 `src/auto_invest/analytics/mobile_operator_snapshot.py`에 돈 경로·라이브 캐너리·단타 준비·연구 사이드카를 정제하는 실패 폐쇄형 요약 조립기를 구현한다.
- [x] T006 `tests/integration/test_mobile_status_page.py`에 HTML과 JSON 자금·전략 의미 일치 및 기존 최상위 계약 유지 시험을 추가한다.
- [x] T007 `scripts/generate_mobile_status.py`에 선택적인 자금·전략 요약 입력, 정적 HTML 카드와 임베디드 JSON을 추가하고 기존 생존 상태 생성은 독립 유지한다.

## 3단계: 사용자 이야기 1 - 자금 상태를 오해 없이 확인 (P1)

**목표**: 계좌 값, 준비 예산, 운용 한도, 실제 투자·손익과 위험 한도를 분리한다.  
**독립 시험**: 미확인 계좌+600달러 준비 예산+143달러 운용 한도+전략 범위 0달러를 동시에
렌더링하고 합산·대체 없이 읽히는지 확인한다.

- [x] T008 [US1] 앱 `test/mobile_status_test.dart`에 자금 요약의 유효·누락·손상·0 측정 범위 디코딩 시험을 추가한다.
- [x] T009 [US1] 앱 `lib/features/status/domain/mobile_status.dart`에 자금 요약과 원천 신선도 모델을 하위 호환 방식으로 추가한다.
- [x] T010 [US1] 앱 `lib/features/status/presentation/funds_screen.dart`와 공통 카드 위젯에 계좌 확인 대기, 준비 예산, 운용 한도, 실제 투자·손익, 위험 한도를 분리 구현한다.

## 4단계: 사용자 이야기 2 - 전략 단계를 구분 (P1)

**목표**: 운영 캐너리, 단타 준비, 연구 후보의 역할과 증거·차단 사유를 분리한다.  
**독립 시험**: 세 역할이 섞인 fixture에서 활성 전략 식별자, 알파 미확정, 주문 꺼짐과 승격
차단 사유를 찾아낸다.

- [x] T011 [US2] 앱 `test/mobile_status_test.dart`에 활성·준비·연구 전략과 실행 요약 디코딩 시험을 추가한다.
- [x] T012 [US2] 앱 `lib/features/status/domain/mobile_status.dart`에 전략·증거 진행·최근 실행 모델을 추가한다.
- [x] T013 [US2] 앱 `lib/features/status/presentation/strategy_screen.dart`에 역할별 블록, 자본 범위, 관측 현재/요구, 최근·다음 실행과 차단 사유를 구현한다.

## 5단계: 사용자 이야기 3 - 원천별 최신성 판단 (P1)

**목표**: 시작·복귀·수동·전면 1분 갱신과 원천별 오래됨·오프라인 표시를 제공한다.  
**독립 시험**: 가짜 시계·저장소로 네 갱신 경로, 중복 방지, 묶음은 최신이나 자금만 오래된
경우와 네트워크 실패 캐시를 검증한다.

- [x] T014 [US3] 앱 `test/status_controller_test.dart`에 1분 주기, 복귀, 중복 조회 방지와 중단 시험을 추가한다.
- [x] T015 [US3] 앱 `lib/features/status/application/status_controller.dart`와 `lib/features/status/presentation/status_shell.dart`에 전면 타이머·생명주기 갱신·중복 방지를 구현한다.
- [x] T016 [US3] 앱 공통 시간 위젯과 각 화면에 묶음·자금·전략·시스템 기준 시각, 미래/오래됨, 오프라인 캐시 표시를 구현한다.
- [x] T017 [US3] 백엔드 `.github/workflows/mobile-status-pages.yml`에 돈 경로·라이브 캐너리·첫 수익·전략 공장 완료 후 읽기 전용 재발행을 추가하고 기존 예약·수동·push를 보존한다.

## 6단계: 사용자 이야기 4 - 네 탭 작은 화면 운영판 (P2)

**목표**: `홈·자금·전략·시스템`과 별도 정보 화면을 Claymorphism 기반으로 제공한다.  
**독립 시험**: 작은 화면과 200% 글자에서 네 탭, 핵심 카드와 정보 화면이 가로 넘침 없이
탐색되는지 확인한다.

- [x] T018 [US4] 앱 `lib/app/theme.dart`와 `lib/core/widgets/`에 선택한 색·테두리·그림자·상태 칩 토큰을 정리한다.
- [x] T019 [US4] 앱 `lib/features/status/presentation/home_screen.dart`를 전체 상태→운용 한도→실제 투자금→활성 전략→단타 준비→시스템 순서로 재구성한다.
- [x] T020 [US4] 앱 `lib/features/status/presentation/automation_screen.dart`를 `system_screen.dart`로 전환하고 기존 자동화 상세를 보존한다.
- [x] T021 [US4] 앱 `lib/features/status/presentation/status_shell.dart`, `lib/app/router.dart`, `lib/features/status/presentation/about_screen.dart`를 네 탭+별도 정보 화면으로 연결한다.
- [x] T022 [US4] 앱 `test/widget_test.dart`에 네 탭, 정보 화면, 작은 화면과 200% 글자 크기 회귀 시험을 추가한다.

## 7단계: 사용자 이야기 5 - 금융 화면 사생활 보호 (P2)

**목표**: 자금 화면을 기기 인증으로 잠그고 배경 미리보기를 불투명 보호한다.  
**독립 시험**: 인증 성공·실패·취소·미지원과 앱 배경/복귀를 가짜 인증기로 재현해 보호 값이
한 번도 노출되지 않는지 확인한다.

- [x] T023 [US5] 앱 `test/privacy_gate_test.dart`와 `test/widget_test.dart`에 인증 상태·배경 보호막·복귀 재잠금 시험을 먼저 추가한다.
- [x] T024 [US5] 앱 `lib/core/privacy/device_authenticator.dart`와 `privacy_controller.dart`에 `local_auth` 어댑터와 메모리 전용 잠금 상태를 구현한다.
- [x] T025 [US5] 앱 `lib/features/status/presentation/funds_screen.dart`에 사용자 동작 기반 잠금 해제와 실패 폐쇄 화면을 연결한다.
- [x] T026 [US5] 앱 최상위 생명주기 래퍼에 전체 불투명 보호막과 배경 즉시 재잠금을 구현한다.

## 8단계: 통합 검증과 인계

- [x] T027 백엔드 관련 pytest와 Ruff를 실행하고 샘플 공개 산출물에서 비밀값·계좌번호·원시 감사 자료가 0건인지 검사한다.
- [x] T028 앱 `flutter analyze`, 전체 `flutter test`, `flutter build ios --release --no-codesign`를 순서대로 실행한다.
- [x] T029 백엔드 `uv run pytest`, `uv run ruff check src tests`, `agent_harness_probe.py --strict`, `check_handoff_facts.py` 전체 관문을 실행한다.
- [ ] T030 두 저장소 변경을 각각 커밋·푸시하고 품질 관문을 채운 풀 리퀘스트를 만든 뒤 통과 시 merge 방식으로 병합한다.
- [ ] T031 앱을 실제 iPhone에 서명 설치·실행하고 앱 레코드, 프로세스, 네 탭, 잠금·보호막을 확인한다.
- [ ] T032 백엔드 `HANDOFF.md`와 기능 183 완료 기록을 최신 main·검증·앱 배포 증거로 갱신하고 `/handoff` 관문을 수행한다.

## 의존 관계

- T001~T003 뒤에 공통 기반 T004~T007을 수행한다.
- US1과 US2 모델은 T005~T007 계약을 공통 전제로 한다.
- US3은 저장소/컨트롤러의 기존 캐시 동작을 보존하며 US1·US2 원천 시각을 소비한다.
- US4는 US1~US3 화면을 네 탭에 조립한다.
- US5는 자금 화면과 최상위 생명주기를 감싸며 거래 권한과 독립이다.
- T027~T032는 모든 사용자 이야기가 완료된 뒤 수행한다.

## 구현 전략

1. 백엔드가 기존 앱을 깨뜨리지 않는 추가 필드를 먼저 만든다.
2. 앱 모델과 fixture를 계약에 맞춘 뒤 자금·전략 화면을 붙인다.
3. 갱신·접근성·기기 인증을 통합하고 자동·실기기 시험으로 닫는다.
4. 어느 단계에서도 주문, 자본 센티넬, 전략 설정, 허용목록, 비밀값, 감사 로그는 수정하지 않는다.
