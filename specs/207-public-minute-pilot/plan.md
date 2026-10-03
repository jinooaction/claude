# Implementation Plan: 가입 없는 공개 분봉 원본 검증

**Branch**: `codex/207-public-minute-pilot` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

익명 공개 원본 두 파일을 GitHub에서 전체 취득·지문 대조·품질 검사한다.
검토 코드별 영구 시도 기록을 네트워크 전에 만들고 자동 반복을 막는다.
전체 원본은 기존 연구 암호화 키로 새 nonce/별도 부가 인증 문맥을 사용해 보관한다.
지문/품질 요약만 공개하며 성과와 실주문 자격을 계산하지 않는다.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: 기존 httpx, DuckDB 1.4.1, exchange-calendars; 별도 연구 requirements의 cryptography 46.0.5
**Storage**: 원격 임시 원본, 추가 전용 GitHub release의 암호문·영수증
**Testing**: pytest/respx의 실패 반례, 작은 합성 Parquet; 전체 검사는 GitHub
**Target Platform**: GitHub Ubuntu 실행기, 로컬은 작은 합성 검사만
**Project Type**: 연구 전용 명령줄/수동 검토 코드 관문
**Performance Goals**: 전체15분·메모리2GB/검사2스레드·총514450366바이트
**Constraints**: HTTPS 허용 호스트2개·로그 비노출·1초 간격·최대3시도·단일 검토 코드 한 번 선점
**Scale/Scope**: 2014-01/2019-12 두 파일, 약43866907행; 전략·운용 연결은 후속 범위

## Constitution Check

I/II: 새 주문 호출 없음, 한도·허용목록 유지. III: LLM 호출 없음.
IV: 기존 감사 불변, 새 시도 기록 추가 전용. V: 입력 주소/오류/로그에 키 없음,
기존 키는 검토 코드 일치 확인 뒤 암호화 단계에만 전달. VI: 취득/품질은 전략 합격 아님.
VII: 요청1초 간격, 타임아웃, 일시 실패만 2/4초 뒤 최대3시도; 영구 선점으로
동일 소스 재실행 차단(900초 자동 해제보다 엄격). VIII.A: 생산 배포 없음.
IX/X: 커널/헌법/관문/실거래권한/자본/최소36시도/미개봉495세션 유지.
설계 후 재평가: 통과. 연구 데이터의 출처/조정/이용 권한 확인은 남겨 두며 승격은 거짓.

## Project Structure

`specs/207-public-minute-pilot/{spec,plan,research,data-model,quickstart,tasks}.md`,
`contracts/pilot.md`, `checklists/requirements.md`.
`src/auto_invest/market_data/public_minute.py`: 고정 입력, 익명 취득, 시간/품질 진단.
`scripts/public_minute_pilot.py`: 취득·안전 보고·암호화 보관 명령.
`tests/unit/test_public_minute.py`, `tests/integration/test_public_minute_pilot.py`.
`.github/workflows/public-minute-pilot.yml`: 전체 회귀와 검토 SHA 일치 시 단 한 번 실제 취득.

## Phase 0 / Phase 1

연구 결정은 [research.md](research.md), 자료는 [data-model.md](data-model.md),
경계/실행은 [contracts/pilot.md](contracts/pilot.md), 재현은 [quickstart.md](quickstart.md).
미해결 기술 선택 없음. 에이전트 문맥 갱신 스크립트는 이 저장소에 없으므로
`AGENTS.md`의 SPECKIT 포인터를 실제 계획으로 최소 변경한다. 자동 생성 영역 밖은 유지한다.

## Rollback / lost functions

제거 기능 없음. 기존205 인증 수집/기존1645세션을 대체하거나 완료로 표시하지 않는다.
`PUBLIC_MINUTE_SOURCE_SHA`를 비우면 새 취득은 차단된다. 기존 release/암호문은 지우지 않는다.
