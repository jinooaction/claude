# 구현·검증 기록 — 2026-10-02

## 현재 상태

고정 공개 목록과 AMZN/NVDA raw 원본의 수동 원격 수집을 구현했다. 연구 취득 경로이며
자료 품질·과거 종목 포함 시점·전략 통과·실거래 준비는 판정하지 않는다. KIS 요청과 자금 배정은 0건이다.
현재 GitHub의 비밀 이름 목록에는 `HF_DATA_API_KEY`가 없다. 실제 인증 자료 취득은 미완료다.

## 구현 검사

- 구현 전 관련 검사는 새 모듈 부재로 수집 단계에서 실패했다(2026-10-02).
- 구현 후 `uv run pytest tests/unit/test_hf_research_ingest.py -q`: **35 passed / 0.76s**.
- `uv run ruff check src tests scripts/hf_research_ingest.py`: 통과.
- `uv run python scripts/agent_harness_probe.py --strict`: 14/14 통과.
- `uv run python scripts/check_handoff_facts.py`: 통과.
- 키 부재, 고정 주소/정리본 금지, 403 뒤 추가 요청 금지, 청크 경계의 키 반사,
  길이/용량/형식 거부, 원본별 실패 누적 분리, 이력 누락/취소/재시도 차단,
  숫자/날짜형 429 대기, 실제 느린 스트림 중단, 완료 쓰기 실패, 산출물 재검증,
  미완료 자료의 전체 성공 위조·비밀 메타데이터·실거래 자격 위조 거부를 확인했다.
- 정확한 코드 `0b51d99473d881768f60d170a24be25988b7e0a0`의 원격 전체 검사
  [37017956272](https://github.com/jinooaction/claude/actions/runs/37017956272)는
  **5263 passed / 13 skipped / 1511.49s**, 새 CLI 포함 린트 통과다.
  2026-10-02 14:35:28 UTC에 성공 종료했고 원문은
  `/tmp/205-hf-full-0b51d994.log`에 보존했다.
- PR 본문 품질 검사
  [37017956410](https://github.com/jinooaction/claude/actions/runs/37017956410)는 통과했다.
- 깨끗한 같은 코드에서 실제 CLI를 오프라인 재시도 이력(`run_attempt=2`)으로 호출했다.
  종료코드3, `HISTORY_UNVERIFIED`, 파일0, 주문0, 정확한 코드 지문을 확인했고
  모의 키는 출력되지 않았다. 실제 HTTP 접근이나 시장 원본 취득을 증명하는 검사는 아니다.
  로컬 임시 디렉터리는 먼저 정규 경로로 해석해야 하며 macOS `/var` 별칭 입력은
  의도한 심볼릭 링크 거부로 종료코드2였다.
- 후속 문서 커밋`a6ed6a5d0144d7167184feaeaea875511882ea8f`의 전체 검사
  [37021696280](https://github.com/jinooaction/claude/actions/runs/37021696280)도
  **5263 passed / 13 skipped / 1349.63s**, 린트 통과로 종료했다.
  로그는`/tmp/205-hf-full-a6ed6a5d.log`다. 두 코드 사이에는 인계·결과·출처 문서만 바뀌었다.

## 실제 공개 목록의 직접 접근

14:52:26.551987 UTC 시작,14:52:45.062612 UTC 완료의 한 요청에서
공식`/v1/symbols`의 실제HTTP200,161189바이트,1391종목을 같은 목록 검사기로 검증했다.
이메일·키·브라우저 쿠키·인증 요청·주문은0이다. 첫1초/경과20초/4MiB 상한과
리디렉션·환경 프록시 거부를 지켰다. 기존 익명 거부 원본은 보존했고1069156초 이후
한 번만 접근했다. 출력 예약이 남아 실제 재실행은 요청 전에`PUBLIC_PROBE_REFUSED`로 거부했다.
원본 재읽기 지문과1391개 목록 검증도 대조했다.

- 저장소 밖 원본/영수증/한계:
  `/Users/mason/Projects/claude-data-research/20261002-hf-public-catalogue/`.
- 원본 SHA-256:`947480773fae2e427f4c1492675a184ac48f589a43d73deb5bc9d965ef18d253`.
- 영수증 SHA-256:`9b6326def110f9fbe99e6eab62d1c788f8360719030f6d8741c7cf5bbfd0bdf2`.
- 직접 진단 소스 기준:`a6ed6a5d0144d7167184feaeaea875511882ea8f`.
- 별도 실행 코드:
  `/Users/mason/Projects/claude-data-research/probe_hf_public_catalogue_20261002.py`(린트 통과).

AMZN/NVDA 목록 항목은 확인했지만 이 목록은 raw 파일의 크기·기간·품질 인증이 아니다.
현재 위치의 공개 목록 접근만 증명하며 과거403의 원인·모든 실행 위치·main 작업의 이력 복원·
실제 인증 자료를 인증하지 않는다. T015–T016은 미완료이며 모의 가격 파일은 실제 자료가 아니다.

## 외부 입력과 남은 관찰

공식 API의 인증 자료는 기존 무료 계정의 키가 필요하다. 값은 채팅·커밋·로그에 넣지 않고
`HF_DATA_API_KEY` 비밀 저장소로만 제공한다. 공개 목록 직접 접근은 확인했으며
main 원격 수집과 인증 자료 취득은 별도 증거로 확인한다.
실제 두 원본 취득과 영구 보관이 끝나기 전 T016을 완료로 바꾸지 않는다.
이번 파일 취득 성공으로 181 T013–T016, 200 T017, 최종 성과 미개봉 경계를 닫지 않는다.
원본의 PiTrading/IEX 원천 전환은 이후 연구에서 따로 분리해야 한다.
