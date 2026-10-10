# Implementation Plan: 재검증 시각과 연구 내용 지문 분리

**Branch**: `codex/212-stable-research-identity` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

## Summary

원래 archive lineage 전체 지문으로 합성 결합 자료의 내용 지문을 계산하고, 연구 지문은 generated_at_utc만 제외한 엄격한 정규 표현을 새 버전 문맥에 묶는다. 보고서/결합 원본 생성 시각은 실제 now로 남기며 원본 수집 시각은 제외하지 않는다. 기존 register→select_research→verify_registration 경로를 그대로 사용한다.

## Technical Context

- Python3.11/기존 json/hashlib/dataclasses/pytest/freezegun, 새 의존성 없음.
- 저장: 원래 불변 archive와 파생 review 출력. 원본 수정/이전 등록 변환 없음.
- 플랫폼: Linux GitHub 전체검사/서버; Mac 작은 합성 검사만.
- 범위: intraday_archive.py/새 내용지문 모듈/intraday_selection.py/합성 반례/검사 워크플로/SDD 인계.
- 핵심 성능: 기존 가격 평가 횟수 증가 없음; lineage≤2000/기존 출력 크기 안에서 해시.
- 실제 가격/495미개봉/전략 성과/서버키/자금·주문 읽기나 실행 없음.

## Constitution Check

- I/II: 자본/종목/주문 한도 불변. IV/V: 원본/감사 보존, 키 분리.
- VI/IX.B-2: 과거검증→60전진→제공자/체결·강화 캐너리·별도권한 유지. 관문을 합격시켜주는 변경이 아니다.
- VII/VIII.A: 외부 API 새 호출/배포 우회 없음. 코드가 병합되면 정상 배포만 관측한다.
- IX: 등급3 풀 SDD와 커밋의 this changes the safety perimeter 기록. 헌법/Kernel 자체는 수정 없음.
- X: 기존1645/최소36시도/495미개봉·비용31/40bp·200거래와 현금/정산/부분체결 유지.
- 설계 후 재점검: 원본 또는 내용 변경은 기존 등록 거절. 이전 등록 자동 변환 없음. 문서SHA도 정확 코드 변경으로 유지한다.

## Project Structure

- specs/212-stable-research-identity/{spec,plan,research,data-model,quickstart,tasks,results}.md
- contracts/research-identity.md, checklists/requirements.md
- src/auto_invest/analytics/intraday_research_identity.py
- src/auto_invest/analytics/intraday_archive.py
- src/auto_invest/execution/intraday_selection.py
- src/auto_invest/execution/intraday_identity.py (새 계산 의존성도 실행 지문에 추가)
- tests/unit/test_intraday_research_identity.py
- .github/workflows/stable-research-identity-checks.yml

## Implementation and Validation

1. 원래 작은 합성1세션/390행·동일원본/동일코드 재계산의 지문 변경 반례부터 고정한다.
2. archive 입력의 날짜/rawSHA/manifestSHA/출처/합성/조정 범위를 안정적인 자료 지문으로 사용한다. 파생 manifest 지문은 원래 파일에 남는다.
3. 결과 전체 내용에 생성 시각만 제외하고 새 버전 문맥으로 해시한다. 원본시각/코드/비용/평가/판정/후보/거래/사전등록/알 수 없는 필드는 모두 유지한다.
4. 새 모듈도 기존 실행 소스 지문 목록에 추가한다. 기존 등록 발급/검증의 합성 연결, clock-only 안정성, 내용변경/이전등록 거절을 확인한다. 합성 등록은 실제 합격·서버인증이 아니다.
5. GitHub 전체검사/필수반례/린트, 하네스/인계/본문/merge/실제 배포 범위를 확인한다.
6. 되돌림: 기존 코드로 회귀하면 현재 내용지문 등록은 거절되며, 원래 기록을 덮거나 다시 서명하지 않는다.

## Complexity Tracking

위반 없음. 안전 관문을 줄이지 않고 파생검증 시각 때문에 생기던 불일치만 제거한다. 별도 캐시/서명 재발급/합격 파일 입력은 추가하지 않는다.
