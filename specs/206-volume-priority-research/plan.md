# Implementation Plan: 동시 신호의 개장 거래량 우선 처리 검증

**Branch**: `codex/206-volume-priority-research` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

194의 연구 현금·체결 계산을 재사용하고 새206에서만 같은 시각의 준비된 신호를
상대거래량 내림차순/종목명 오름차순으로 처리한다. 성과 조회 전에 계약을 커밋한다.
공개 저장소에는 새 평문 원본을 넣지 않고 인증된 암호문으로 원격 연구에 전달한다.
통과 전략을 찾는 단계이며 수익이나 전체 프로그램 완료를 보장하지 않는다.

## Technical Context

- Python3.11, 기존 exchange-calendars·pytest·ruff. 새 연구 개발 의존성은 cryptography AES-256-GCM이며 직접 암호를 구현하지 않는다.
- 입력은194의30종목 CSV와 고정 manifest. 원본 최대64MiB/파일·1536MiB/묶음, 암호문 최대64MiB/파일·512MiB/묶음.
- 스트리밍 gzip/지문 준비는 nice19와1MiB마다 최소0.05초 휴식으로 제한한다. 실제 가격 재생·전체 검사는 원격에서 수행한다.
- 새256비트 연구 키 `SPARSE_RESEARCH_INPUT_KEY`는 비밀 설정에서만 읽는다. 증권사·계좌·SEC·이메일 비밀값은 주입하지 않는다.
- 새 출력만 허용하고 완료 영수증을 마지막에 남긴다. 기존 원본·장부를 덮어쓰거나 삭제하지 않는다.
- 원격 작업은 검토된 정확한 코드·신뢰된 실행 주체와 봉인 자료를 확인한 뒤 연구 키를 사용한다. 운영 워커와 증권사를 호출하지 않는다.

## Constitution Check

위험 등급3: 새 연구 키/암호문 경계를 추가하며 기존 안전 경계는 줄이지 않는다.

- I·II: 실제 주문0, 연구 현금/노출 한도와 기존 실행 허용 목록 유지.
- III: 재생 중 LLM 호출 없음, 유료 서비스·가입 추가 없음.
- IV: 연구 장부 추가 기록, 기존 원본·결과·실거래 감사 보존.
- V: 키는 비밀 설정에서만 읽고 평문 원본·키·자유 예외를 공개하지 않음.
- VI: 개발 양수도 독립 검증 필요. Backtest→Canary→Full 단계 유지.
- VII: 새 연구 도구는 외부 API/증권사 호출 없음. 기존 요청 제한·재시도·냉각 유지.
- VIII.A/B: 장중 배포 요청 없음, 기존 배포 검증·되돌림 유지.
- IX: 헌법·kernel.toml·주문 제한·운영 승인·돈 경로 변경 없음.
- X: 177 통계·시간 분리·실행 동등성·181 전진/실주문 관문 유지. 최소36은 시도 하한이며 통계 합격 인증이 아님.

설계 뒤 재점검: 새 키는 연구 복호화 전용이고 계좌/주문 권한이 없다. 헌법 위반 없음.

## Project Structure

- `src/auto_invest/analytics/sparse_opening_research.py`: 내부 재생기 분리, 기존 공개 재생은 알파벳순 유지.
- `src/auto_invest/analytics/volume_priority_research.py`: 새 봉인 계약·신호 순서·최소36·결과 정체성.
- `scripts/volume_priority_research.py`: 제한된 자료 준비/복호화/재생/독립 장부 검증.
- `tests/unit/test_volume_priority_research.py`, `tests/integration/test_volume_priority_research_cli.py`: 순서·기존194 호환·현금/체결·암호문/키/크기/기간/덮어쓰기 반례.
- `.github/workflows/volume-priority-checks.yml`: 정확한 코드의 원격 전체 회귀와 개발 재생·재계산·산출물 보존.
- `research-fixtures/206/`: 가격 없는 원본 지문과 암호문. 키·평문 가격 없음.

## Phases

0. 기존194 계약·신호·현금·재생과 최소35시도·논문 본문·공개 저장소를 조사했다. 결정과 대안은 [research.md](research.md).
1. [data-model.md](data-model.md), [봉인 계약](contracts/preregistration.json), [전달 경계](contracts/transfer.md), [검증 순서](quickstart.md)를 작성한다. AGENTS.md 계획 참조만206으로 갱신한다.
2. 작은 반례→기존194 호환→자료 준비→원격 재생/재계산→전체 회귀·린트·하네스·인계·PR 품질 검증. 비용·한도·순서를 결과 뒤 조정하지 않는다.

## 제거·대체·되돌림

기존 기능 제거 없음. 새 후보에서만 동시 신호의 알파벳순을 상대거래량 순으로 대체한다.
실패 시206 호출 중단과 코드 되돌림 커밋으로 복구한다. 기존194·원본·연구 결과는 삭제하지 않는다.
연구 키 제거는 새 복호화만 거부하며 기존 수집·계좌·운영 워커에는 영향이 없다.

## Complexity Tracking

암호문 전달은 공개 원본 추가 없이 원격 연구를 수행할 최소 경계다. 현금·체결 모형을
복제하지 않으며 새 전략 실주문 경로는 만들지 않는다.
