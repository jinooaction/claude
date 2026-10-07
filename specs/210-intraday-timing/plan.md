# 구현 계획: 모의 장부 관측·게시 시각

**Branch**: `codex/210-intraday-timing` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

기존 고정 관측 명령이 쓰는 service-status만 읽기 전용 래퍼로 감싼다.
기존6개 운용 지문 파일은 바꾸지 않아 모의 장부 세대를 새로 만들지 않는다.

## Technical Context

Python3.11 표준 라이브러리·기존 서비스 읽기 함수/209 영수증 재사용.
고정 `/var/lib/auto-invest-intraday/status.json`, 기존 service.lock 공유 잠금, 지문 하위 paper.db.
SQLite mode=ro/immutable, 쓰기 잠금 중 실패, 전체 사슬 대신 마지막2개/개수/메타 조회.
기록1MiB/메타16KiB/SQLite2초/보고서4KiB 한도. Mac 짧은 합성, 전체pytest/린트/XML은 GitHub.

## Constitution Check

설계 전후 PASS. 위험 등급2: 같은 읽기 전용 관측 도구와 기록 변화다.
명령 허용목록/키/계좌/주문/위험/배포 경계·Kernel목록 불변.
I한도/II종목/IV추가기록/V비밀격리/VI검증단계/VIII.A장중배포/IX수정기록/X성과측정 유지.
전체181·최소36시도·495미개봉·기존1645세션·60전진·90초 관문 유지.

## Project Structure

- `src/auto_invest/analytics/intraday_timing.py`: 안전 읽기·잠금·마지막 기록 연결·타입/시각 투영. 표준 라이브러리.
- `scripts/intraday_timing_status.py service-status`: 고정 경로 래퍼, 같은 공유 잠금에서 원래 read_service_status 호출.
- `deploy/observe-on-instance.sh`: 기존 분기 래퍼 호출, 헤더/인자 거절/권한 유지.
- `src/auto_invest/analytics/intraday_diagnostic_receipt.py`: 선택적 timing 검증/보관.
- `tests/unit/test_intraday_timing.py`: 임시 합성 DB/동시 쓰기/변조/불일치/원본 보존/노출/90초 반례.
- `.github/workflows/intraday-paper-status.yml`: 같은 PR회귀의 새40개 이상 반례 무생략, 관측명령/예약/키 유지.
- 210 SDD·209 T008 실제완료·HANDOFF 현재07932/예약배포 근거.

## Failure / rollback / replacement

최신 상태 age로 처리 지연을 추정하는 방법을 원래 관측/게시 시각으로 대체한다.
기존 상태는 남고 연결 실패는 고정 미확인 이유와 null 시각만 출력한다.
이전 helper 호출로 정상 revert 가능; 원래 장부/상태/영수증 보존.
처리 완료/API 수신/자료원 게시/서명/전체 사슬/정식 전진 자격은 미평가다.

## Validation / deployment

합성 반례 미구현 실패→구현/합성/린트→하네스·인계·본문→PR 정확SHA 전체XML/필수반례/린트→본문 증거→merge.
서버는 정상 장외 예약 뒤 고정 명령으로 별도 확인한다. 그 전 현장 시각 연결은 미관측이며 문서·전체검사 반복을 만들지 않는다.
