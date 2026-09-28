# Implementation Plan: 장 마감 전 단일 후보 검증

**Branch**: `codex/198-late-session-research` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

성과를 열기 전에 단일 후보 계약을 커밋한다. 완료된 5분봉으로 두 번의 직전 종가
대비 상승 여부를 비교한다. 기존 연구 체결 엔진에 `late_session` 계열만 추가하고
기존 계열 규칙은 유지한다. 개발·재계산 명령만 제공한다.

## Technical Context

**Language/Version**: Python 3.11 이상, 기존 uv 환경

**Primary Dependencies**: 기존 exchange_calendars·numpy, 새 의존성 없음

**Storage**: 고정 CSV 입력, 새 JSON 판정·JSONL 장부

**Testing**: pytest·ruff, 시간 경계·장부 보존 반례

**Target Platform**: 기존 Linux 연구/CI 환경, Mac은 가벼운 편집·검사만

**Project Type**: 연구 CLI와 분석 모듈

**Performance Goals**: 후보 1개 × 비용 2개, 별도 병렬 검색 없음

**Constraints**: 화면 조작·계좌 연결·최종 확인 자료 접근 금지, 덮어쓰기 거부

**Scale/Scope**: ETF 5개 × 개발 1,645거래일, 첫날 준비 후 평가 1,644일

## Constitution Check

설계 전후 점검 통과. I/II(한도·허용 대상)는 기존 연구 계약 유지.
III(모델 호출 제한)는 봉별 언어 모델 호출 없음. IV/V(감사·비밀값)는 무변경.
VI(과거검증→소액운영→확대)는 개발 통과만으로 승격하지 않는다.
VII(외부 장애 대응)는 재생 중 외부 접속 없음. VIII.A/B(장중 배포 제한과
검증된 배포)는 무변경. IX(안전 핵심 영역)는 kernel.toml 파일 목록 무접촉.
X(측정에 근거한 개선)는 과거 실패와 누적 시도 수 보존.

위험 등급 2: 연구 기능은 1등급이나 AGENTS·명세 포인터가 다음 세션 행동을 바꾼다.
제거 기능 없음. 197의 배포 미완료 기록은 HANDOFF에 보존한다. 실패 시 새 CLI 사용
중단 후 변경 커밋을 되돌리며 연구 출력은 삭제하지 않는다. 실자본 0,
`live_eligible=false`, `promotion_allowed=false`. 자본 확대의 `EDGE_CONFIRMED`
(검증된 우위)와 독립 확인·전진·체결·잔고 증거 요구 및 단계별 한도는 변경하지 않는다.

## Project Structure

- `specs/198-late-session-research/`: 명세·조사·자료 구조·계약·작업표·결과.
- `src/auto_invest/analytics/late_session_intraday.py`: 고정 계약·시간 신호·개발·재계산.
- `src/auto_invest/analytics/intraday_paper_challenger.py`: 명시적 계열 목록에
  late_session 추가, 매핑 전체 범위·하루 한 번 시도·청산 지속 동일 적용.
- `scripts/late_session_probe.py`: develop/verify, 깨끗한 코드·새 출력·과거 코드 연결.
- `tests/unit/test_late_session_intraday.py`: 시간·누락·미래 불변·비용·미청산 반례.
- `tests/integration/test_late_session_cli.py`: 계약·입력·출력·재계산 경계.
- `.github/workflows/intraday-research-checks.yml`: 관련 PR의 정확한 head 커밋에서
  잠금 의존성 설치·전체 pytest·ruff. 읽기 권한만 있고 증권사 비밀값·SSH·배포 단계가 없다.
  동일 PR의 새 커밋은 이전 검사만 취소하며 실행 제한은 40분이다.
- `research-fixtures/198/`: CC BY 4.0 출처 표시와 개발 자료만 있는 gzip 묶음.
- `scripts/unpack_late_session_input.py`: 크기·지문 검사 후 새 폴더에만 복원.
- `tests/integration/test_late_session_input.py`: 손상·과대 확장·덮어쓰기·기간 계약 검사.

## Design and Verification

1. 이전 177 계약과 새 계약 지문을 검사한다. 고정 manifest 지문을 확인한 뒤 가격을
   읽고 기간·1,645일·자료 지문을 재검사한다.
2. 실제 직전 거래일 마지막 봉, 당일 시작+30분과 종료-30분에 끝나는 완료 봉만 사용한다.
   연속 5분봉·달력 경계를 검사한다. 첫날 무신호, 1,644일 평가다.
3. 새 계열을 noise_band로 위장하지 않는다. 별도 계열만 추가하고 기존 비용·가격 산술과
   알 수 없는 계열 거부를 유지한다. 정상장 매수 가능 15:30, 청산 시작 15:55.
4. 모형 체결 시각 `open + 1 microsecond`는 정렬 값이며 실제 증거가 아님을 기록한다.
   봉 전체 거래량과 고정 일별 배정은 실제 체결·결제 장부와 동등함을 입증하지 않는다.
5. 기존 `select_development`로 두 비용 판정, 누적 시도 최소 32회. 원자료 재계산으로
   전체 판정과 장부 바이트를 비교한다. 봉인만 맞춘 가짜 결과도 거부한다.
6. 가벼운 표적 검사 후 원격 CI/연구 환경에서 전체 pytest·ruff·실자료 재생을 수행한다.
   실행 위치 확인 전 대규모 자료를 임의 업로드하지 않는다. 커밋·명령·종료 코드를 남긴다.
7. 하네스·HANDOFF·PR 검사 후 완성 시 병합한다. 배포 증거 없이 배포 완료라 쓰지 않는다.

원격 검증 추가는 기존 검증을 제거하지 않는다. 관련 파일·의존성 변경에만 반응하며,
문제 발생 시 이 워크플로 변경을 되돌리고 전체 검증 미완료 상태를 유지한다.
새로운 클라우드 상품 가입·유료 자료 구매·별도 서버 생성은 하지 않는다.

## 원격 실자료 실행 경로 보완

2026-09-28 UTC 확인: 공급자 license 페이지가 2022년 이전 자료의 편집·재배포를
CC BY 4.0으로 허용한다. 공개 저장소에 비밀값이나 계좌 자료를 올리지 않고,
기존 고정 개발 CSV만 출처·변환 내역과 함께 포장한다. 최종 확인 자료는 제외한다.
manifest 원본과 CSV 지문은 사전등록과 동일하다. 계약·비용·후보는 변경하지 않는다.

개발 재생은 원격 CI의 별도 30분 제한 작업에서 수행한다. 입력 복원→개발→원자료
재계산→결과 출력 순서이며, 결과·장부를 30일 보존한다. 실패 시 부분 결과가 있어도
검증 성공으로 취급하지 않는다. 결과 보존 기간 안에 영구 인계 기록을 남긴다.
문제 시 이 입력/실행 경로를 중단하고 연구 미완료를 유지한다. 기존 전략·주문 경로 영향은 없다.

## Complexity Tracking

헌법 위반·새 의존성 없음. 운영 주문 경로는 연결하지 않는다. 전체 프로그램의
181 T013~T016 완료는 별도 증거가 필요하며 이번 기능으로 대체하지 않는다.
