# 구현 계획: 모바일 자금·전략 운영판

**브랜치**: `codex/183-mobile-capital-strategy` | **작성일**: 2026-09-08 | **명세**: [spec.md](spec.md)
**입력**: `/specs/183-mobile-capital-strategy-dashboard/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## 요약

기존 공개 `status.json`에 검증 상태와 원천 시각을 포함한 `capital_summary`와
`strategy_summary`를 하위 호환 방식으로 추가한다. Python 생성기는 이미 발행된 정제
사이드카와 확정된 단타 준비 계약만 읽으며, 계좌 집계가 아직 검증되지 않은 값은 숫자로
발행하지 않는다. 별도 Flutter 저장소의 앱은 `홈·자금·전략·시스템` 네 탭, 1분 전면 갱신,
생명주기 복귀 갱신, 기기 인증 자금 잠금, 앱 전환 보호막을 제공한다. 주문·자본·전략 변경
경로는 추가하지 않는다.

## 기술 배경

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**언어/버전**: Python 3.11+, Flutter 3.47.0, Dart 3.13.0  
**주요 의존성**: 기존 auto-invest 분석 모듈, GitHub Actions/Pages, Flutter Riverpod,
go_router, http, shared_preferences, local_auth  
**저장소**: GitHub automation 사이드카와 정적 Pages JSON/HTML, 앱의 마지막 성공 JSON 캐시  
**시험**: pytest, Ruff, Flutter unit/widget tests, `flutter analyze`, iOS release build와 실제 iPhone 설치·실행  
**대상 플랫폼**: GitHub Actions Ubuntu 발행 작업, iOS 우선 Flutter 앱(Android 설정도 안전하게 유지)  
**프로젝트 종류**: 두 저장소를 잇는 정적 상태 발행기 + 읽기 전용 모바일 앱  
**성능 목표**: 전면 사용 중 60초마다 중복 없이 조회, 핵심 원본 완료 뒤 5분 이내 발행 시작  
**제약**: 공개 결과에 계좌번호·키·토큰·SSH·원시 감사 자료 금지, 미검증 계좌 금액 금지,
앱에서 쓰기/주문 기능 금지, 기존 `status.json` 소비자 하위 호환  
**규모/범위**: 단일 운영자, 네 개 모바일 탭, 두 개 추가 요약 개체, 기존 정적 엔드포인트 한 개

## 헌법 점검

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

For money-path work, explicitly verify the rung-0 exploration contract, the unchanged
EDGE_CONFIRMED requirement before capital exceeds 20%, exact strategy fingerprint identity,
and fail-closed handling of missing holdout, forward, hardened-canary, broker, or NAV evidence.

- **I 포지션·위험 한도**: 기존 한도를 읽어 표시할 뿐 계산·변경하지 않는다. 통과.
- **II 허용 종목**: 정제된 현재 대상 종목을 표시만 하며 허용목록을 변경하지 않는다. 통과.
- **III 검증 단계**: `Backtest -> Canary -> Full` 상태를 역할별로 구분해 보여주고 승격하지 않는다. 통과.
- **IV 추가형 감사 기록**: 원시 감사 장부를 읽거나 수정하지 않는다. 기존 사이드카만 읽는다. 통과.
- **V 비밀값 분리**: 공개 JSON은 허용 필드만 새로 조립하고 금지 문자열 회귀 시험을 둔다. 통과.
- **VI 단계적 출시**: 기존 운영 캐너리 10%와 단타 준비 전용 상태를 그대로 표시한다. 통과.
- **VII 외부 API 장애**: 앱 조회 실패는 캐시+오프라인으로 실패 폐쇄하며 거래 상태를 바꾸지 않는다. 통과.
- **VIII.A 장중 배포 금지**: 이 기능은 Pages/UI 가시성 변경이며 worker 배포를 요청하지 않는다. 통과.
- **IX 한 세션 한 기능**: 기능 183 범위만 변경하고 다른 돈 경로 작업과 분리한다. 통과.
- **X 자본 사다리**: 단 1, 10%, 143달러를 관측값으로만 표시한다. 20% 초과 조건과
  `EDGE_CONFIRMED`를 바꾸지 않고, 전략 지문·holdout·forward·hardened-canary·broker·NAV
  증거가 누락되면 정상 또는 승격 가능으로 표시하지 않는다. 통과.

설계 후 재점검: 공개 자료에 `account_nav_usd` 참고값을 총자산으로 내보내지 않고 계좌 집계는
`UNVERIFIED`로 유지한다. 기기 인증은 화면 가림만 담당하며 서버 권한이나 주문 권한으로
재사용하지 않는다. 위 헌법 판단은 그대로 유효하다.

## 프로젝트 구조

### 이 기능의 문서

```text
specs/183-mobile-capital-strategy-dashboard/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### 소스 코드

```text
# auto-invest 저장소
src/auto_invest/analytics/
└── mobile_operator_snapshot.py
scripts/
└── generate_mobile_status.py
.github/workflows/
└── mobile-status-pages.yml
tests/
├── unit/test_mobile_operator_snapshot.py
└── integration/test_mobile_status_page.py

# 별도 Flutter 앱 저장소
/Users/mason/Documents/flutter-projects/auto_invest_mobile-183/
├── lib/core/
│   ├── privacy/
│   └── widgets/
├── lib/features/status/
│   ├── application/
│   ├── data/
│   ├── domain/
│   └── presentation/
├── ios/Runner/Info.plist
├── android/app/src/main/AndroidManifest.xml
└── test/
```

**구조 결정**: 거래 저장소는 정제·발행 계약의 권위이고, 앱 저장소는 소비·표시·기기 보호만
담당한다. 별도 API 서버나 앱 비밀값을 만들지 않는다. 두 저장소는 동일한 JSON 계약으로
독립 시험하며, 백엔드가 먼저 하위 호환 확장을 발행하도록 순서를 고정한다.

## 복잡성 추적

> **Fill ONLY if Constitution Check has violations that must be justified**

헌법 위반 없음. 별도 Flutter 저장소는 이미 출시된 앱의 소유 경계를 보존하기 위한 기존 구조다.
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
