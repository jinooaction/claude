# 구현 계획: 읽기 전용 Flutter 운영자 앱

**브랜치**: `codex/178-flutter-operator-mobile` | **작성일**: 2026-09-02 | **명세**: [spec.md](spec.md)  
**입력**: `/specs/178-flutter-operator-mobile/spec.md`

## 요약

기존 모바일 HTML 상태판과 운영자 상태 sidecar를 그대로 유지하면서, 같은 실행에서
버전이 붙은 `status.json`을 함께 발행한다. 별도 비공개 Flutter 앱은 이 공개·정제 자료만 읽고
마지막 성공 자료를 기기에 캐시한다. 홈에서는 전체 판정과 다음 행동을 먼저, 자동화 화면에서는
핵심·보조 상태와 신선도를, 설명 화면에서는 출처와 읽기 전용 안전 경계를 보여준다.

첫 버전은 주문·자본·전략·중단 해제 명령을 전혀 제공하지 않는다. 공개 자료에 없는 실제 잔고,
보유종목, 손익도 표시하지 않는다. 선택한 `Claymorphism + Vibrant & Block-based` 스타일은
`Friendly Clay Finance` 디자인 토큰으로 고정하되 경고의 의미를 색상 하나에 의존하지 않는다.

## 기술 배경

**언어/버전**: Python 3.11 이상, Flutter 3.47.0, Dart 3.13.0  
**주요 의존성**: 기존 Python 표준 라이브러리·상태 분석 모듈, Flutter Material 3,
Riverpod, go_router, `http`, `shared_preferences`, `url_launcher`  
**저장소**: GitHub Pages의 정적 `status.json`, 앱 기기의 마지막 성공 JSON 캐시  
**시험**: pytest 통합 시험, Dart 단위 시험, Flutter 위젯 시험, `flutter analyze`, Ruff  
**대상 환경**: GitHub Actions Linux 발행기, iOS 15 이상 우선, Android 8 이상 호환  
**프로젝트 형식**: 기존 Python 저장소의 상태 계약 + 별도 비공개 Flutter 모바일 앱  
**성능 목표**: 캐시 화면 1초 이내, 일반 네트워크에서 최신 상태 3초 이내 표시, 스크롤 60fps  
**제약**: 원격 쓰기 0건, 자격증명 0건, 30시간 초과 자료는 신선한 정상 금지,
예제 자료의 실제값 오인 금지, 44×44 최소 터치 영역  
**규모/범위**: 단일 운영자, 홈·자동화·설명 3개 화면, 현재 약 30개 자동화 상태

## 헌법 확인

*관문: Phase 0 전에 통과했으며 Phase 1 설계 뒤 다시 확인했다.*

- **I 포지션 한도**: 앱과 JSON 발행기는 주문을 만들지 않으며 기존 한도 코드를 읽거나 바꾸지 않는다.
- **II 기본 거부**: 거래 명령이 없고 허용 종목·계좌·세션·주문 종류를 노출하거나 변경하지 않는다.
- **III LLM 판단점**: 앱 실행과 상태 발행 중 LLM 호출은 0건이다. 생성 시안은 개발 참고 자료이며
  운영 판단 입력이 아니다.
- **IV 감사**: 기존 추가 전용 주문 감사 로그를 읽거나 쓰지 않는다. 공개 sidecar와 HTML을
  대신하지 않고 동일 자료의 읽기 전용 표현만 추가한다.
- **V 비밀값**: KIS 키, 계좌번호, GitHub 토큰, SSH 값과 원시 데이터베이스를 입력 계약에서 금지한다.
- **VI 단계 출시**: 전략·자본·승격 동작이 없으므로 단계 출시 경로를 바꾸지 않는다.
- **VII 외부 API**: 앱의 유일한 네트워크 호출은 공개 정적 JSON GET이다. 시간 제한을 두고
  마지막 성공 캐시로 강등하며 자동 재시도 폭주를 만들지 않는다.
- **VIII.A 장중 배포 금지**: 상태 발행과 앱 코드는 거래 로직을 바꾸지 않는다. Python 변경의
  production 배포는 기존 off-hours 관문을 그대로 따른다.
- **IX 안전 경계**: 헌법, 커널, 위험 게이트, 브로커, 주문, 비밀 경로를 건드리지 않는다.
- **X 측정 기반 성장**: 앱은 원문 상태를 표시할 뿐 엣지·자본 판정을 재계산하거나 승격하지 않는다.
- **누락 증거**: JSON 누락·손상·미래 시각·30시간 초과·모순은 모두 정상 이외로 실패 폐쇄한다.

Phase 1 재점검 결과 헌법 위반과 예외 승인 항목은 0건이다. 위험 등급은 새 운영 표면과 Pages
발행 흐름을 추가하는 등급 2이며, 실제 주문이나 안전 경계를 바꾸는 등급 3·4 작업은 없다.

## 프로젝트 구조

### 이 기능의 문서

```text
specs/178-flutter-operator-mobile/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── design-system.md
├── screen-blueprint.md
├── quickstart.md
├── tasks.md
├── assets/home-concept.png
├── checklists/requirements.md
└── contracts/mobile-status-v1.schema.json
```

### auto-invest 공개 상태 계약 저장소

```text
scripts/generate_mobile_status.py
.github/workflows/mobile-status-pages.yml
tests/integration/test_mobile_status_page.py
```

### 별도 비공개 Flutter 앱 저장소 `auto_invest_mobile`

```text
lib/
├── app/
│   ├── app.dart
│   ├── router.dart
│   └── theme.dart
├── core/
│   ├── config/app_environment.dart
│   └── widgets/clay_card.dart
└── features/status/
    ├── application/status_controller.dart
    ├── data/status_cache.dart
    ├── data/status_repository.dart
    ├── domain/mobile_status.dart
    └── presentation/
        ├── status_shell.dart
        ├── home_screen.dart
        ├── automation_screen.dart
        └── about_screen.dart

test/
├── mobile_status_test.dart
├── status_repository_test.dart
└── widget_test.dart
```

**구조 결정**: 거래 시스템 저장소는 공개 상태 계약만 소유하고, 앱은 별도 비공개 저장소에 둔다.
앱이 실패하거나 배포가 중단돼도 기존 HTML, 텔레그램, worker와 돈 경로는 영향을 받지 않는다.

## 구현 단계

1. 기존 HTML과 동일한 자료를 가진 `mobile-status-v1` JSON 계약과 실패 폐쇄 규칙을 고정한다.
2. 상태 생성기에 JSON 직렬화를 추가하고 HTML·JSON 의미 일치와 비밀값 부재를 시험한다.
3. Pages 발행물에 `status.json`을 포함하고 기존 `index.html`·`status.html`을 유지한다.
4. 개인 Flutter 스타터로 `auto_invest_mobile`을 만들고 불필요한 인증 흐름을 제거한다.
5. 도메인 모델, 버전 검사, 30시간 신선도, 마지막 성공 캐시와 네트워크 저장소를 구현한다.
6. `Friendly Clay Finance` 토큰과 공통 카드, 상태 배지, 3개 화면을 구현한다.
7. 정상·주의·위험·오프라인·손상·큰 글자 위젯 및 단위 시험을 통과한다.
8. Python 전체 시험·린트·엄격 하네스·HANDOFF 사실 검사와 Flutter 분석·시험을 통과한다.
9. iOS 릴리스 빌드와 서명을 확인하고 연결된 iPhone에 설치·실행해 첫 화면을 확인한다.
10. 두 저장소의 커밋과 원격 상태를 기록하고 auto-invest PR 품질 관문과 인계를 닫는다.

## 복잡성 추적

헌법 위반이 없어 별도 예외는 없다. 두 저장소를 쓰는 이유는 거래 엔진과 모바일 배포 수명주기를
분리하고 앱 장애가 worker 배포에 영향을 주지 않게 하기 위해서다.
