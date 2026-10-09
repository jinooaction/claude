# Implementation Plan: 저장된 수집 시각의 같은 봉 연결

**Branch**: `codex/211-collection-record` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

새 수집기를 만들지 않는다. 기존210 국소 장부 검증에 선택적 투영 함수를 넣고 같은 잠금·같은 읽기에서 원래 수집 증명의 구조와 자료 지문만 확인한다. 기본210 호출과 결과는 그대로다. 고정 진단 래퍼는 새 결합 함수를 호출하고209 영수증은 선택적 `collection_record`를 검증한다.

## Technical Context

- Python3.11·표준 라이브러리만, 의존성 변경 없음.
- 기존 service.lock 공유 읽기·SQLite mode=ro&immutable·user_version181·최신2행·2초 조회·payload1MiB/meta16KiB 제한 재사용.
- 기존 운용6파일·지문f53f8b57·장부 세대·수집기·attestation/forward 검증기 불변.
- 키/네트워크/가격 파일 조회 없음; 출력4KiB 및 기존 영수증16KiB 한도.
- Mac에서 짧은 합성 검사만, 전체 pytest·린트는 GitHub Actions.

## Constitution Check

I~VII: 자본·종목·주문·감사·비밀·승격·API 호출 변경 없음. VIII.A 장중 배포 제한 보존.
IX.B-2 생산 검증·90초/60세션·등록/서명/체결 관문 불변. X 운영 근거 확인만 추가.
커널·헌법 변경 없음. 사전/설계 후 관문 모두 통과: 이 결과를 인증·자격으로 소비하는 경로가 없다.

## Project Structure

- `src/auto_invest/analytics/intraday_collection_record.py`: 국소 구조·자료 지문 투영/출력 재검증/결합 읽기.
- `src/auto_invest/analytics/intraday_timing.py`: 기본 동작 유지, 선택적 국소 투영 인자만 추가.
- `scripts/intraday_timing_status.py`: 기존 고정 service-status 진입점의 결합 읽기.
- `src/auto_invest/analytics/intraday_diagnostic_receipt.py`: 선택적 수집 결과 검증.
- `tests/unit/test_intraday_collection_record.py`: 합성 정상·부재·손상·재처리·잠금·영수증·읽기 보존.
- `.github/workflows/intraday-paper-status.yml`: 새 파일 경로와 필수 신규 반례 추가, SSH/키/명령/권한/예약 불변.

## Design and Failure Handling

기존 `_read_timing`에 projector 기본값을 유지한다. 새 결합 projector는 동일 event/status/hash로 timing과 collection_record를 만든다. 수집 연결 손상은 수집 결과만 UNAVAILABLE이며 유효한 timing은 보존한다. 기존 장부/잠금 실패는 두 결과 모두 UNAVAILABLE, 사유와 null을 유지한다.

같은 event의 `bars` 5종목/봉 및 `bar_digest`/proof payload bars_digest를 독립 계산과 대조한다. proof schema1/scope/collector_digest/시작·반환 시각/서명64hex를 확인하되 서명을 검증하지 않는다. 시작≤반환≤관측, 반환≥모형종료, 호출≤60초를 확인한다. 시작이 모형종료보다 이른 정상 수집은 허용한다. 출력은 원래 두 시각과 차이 및 event_hash만 제공하고 자료·서명은 제외한다.

외부 출력 재검증은 정확한 키·형식·시각·차이·timing 동일 봉/관측/hash를 확인한다. 단 출력 투영에서 삭제한 가격/서명을 다시 인증할 수 없다는 한계를 문서에 명시한다.

## Rollback and Preserved Features

제거되는 기능 없음. 새 결합 래퍼를 이전 `read_timed_status`로 되돌리면 기존 timing과 기본 진단 유지, 수집 연결만 빠진다. 장부/키/원래 기록 복구나 재생은 필요 없다. 오래된 producer의 선택 필드 부재는 호환 유지한다. 실패를 완료나 권한으로 바꾸지 않는다.

## Phases

0. 기존 코드 계약 조사: 새 연구 에이전트가 필요한 미확인 기술 선택 없음; 이미 확보한 정확한 코드/기록을 직접 읽는다.
1. research/data-model/contract/quickstart와 AGENTS 포인터를 고정한다.
2. 두 사용자 시나리오를 구현하고 필수 합성 반례·전체 원격 검사·린트·하네스·본문·병합을 확인한다.
3. 정상 예약 뒤 실제 원래 영수증에서 수집 부재/원래 시각을 확인한다. 합성을 실제 검증으로 확대하지 않는다.
