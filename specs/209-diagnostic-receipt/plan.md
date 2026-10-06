# 구현 계획: 읽기 전용 진단 원본 영수증

**Branch**: `codex/209-diagnostic-receipt` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

## Summary

로그 비밀값 가림을 원본으로 오인하는 경로를 줄이고 서버 stdout의 허용 필드만 타입 검증해
작은 JSON artifact로 보관한다. 같은 제한된 읽기 명령과 기존 진단 범위를 유지한다.

## Technical Context

**Language/Version**: Python3.11·기존GitHub Actions
**Primary Dependencies**: 표준 라이브러리·기존uv/pytest/ruff
**Storage**: runner 임시 입력·단일 추가 전용JSON·GitHub artifact
**Testing**: 가림/중복/형식/미래/노출 합성·전체pytest XML·린트·실제artifact digest
**Target Platform**: GitHub Linux runner, Mac은 짧은 합성만
**Project Type**: 순수검증함수와CLI/읽기전용관측
**Performance Goals**: 64KiB입력, 영수증16KiB이하, 계산1초이내
**Constraints**: 계좌/가격/키/원래전문 비노출, 실제주문/승격/자본0
**Scale/Scope**: 한관측당 한영수증, 기존예약/수동관측유지

## Constitution Check

설계 전후 PASS. I한도/II종목/IV추가기록/V비밀격리/VI단계/VIII.A장중배포/IX자율/X측정불변.
위험 등급2: 기존SSH비밀과제한명령/서버코드변경없음. 새실거래권한이나암호서명검증아님.
기존1645/최소36/495미개봉/31·40bp/현금·정산·부분체결/한도·감사를변경하지않는다.

## Project Structure

- `src/auto_invest/analytics/intraday_diagnostic_receipt.py`: 입력/타입/신선도/모형범위 검증·CLI
- `tests/unit/test_intraday_diagnostic_receipt.py`: 안전실패/원본값/투영·덮어쓰기 반례
- `.github/workflows/intraday-paper-status.yml`: 기존관측 + 안전JSON artifact, PR전체회귀는키없음
- `.github/workflows/filing-observation-checks.yml`: 함께 발동하는 기존 전체 검사의 암호화 런타임 누락을 기존 고정 requirements로 보정, 실제XML 보관/필수 명령 무생략 확인
- 이 폴더 research/data-model/contracts/quickstart/tasks/results·포인터
- 208 결과/작업·HANDOFF의지난병합/예약배포 사실을이번정당한후속변경에서닫는다.

## Failure / rollback / replacement

새JSON이 로그로부터 값을 추측하는 방법을 대체한다. 기존읽기명령/로그/실패/예약은남는다.
추가필드는출력하지않고실패시영수증없음/일반사유만출력한다. 정상revert로되돌리고기록은보존한다.
자료원성능/가격재생/미개봉구간/원본재취득/서버설정/주문함수 호출없음.

## Validation

합성반례실패→구현→짧은합성/린트/하네스·인계·본문→커밋/PR→정확SHA전체XML/린트
→같은검토코드의제한관측한번→원래artifactZIP/JSON 크기·SHA대조→본문최종근거→병합.
결과증거만본문에추가해문서/전체검사반복을만들지않는다.
