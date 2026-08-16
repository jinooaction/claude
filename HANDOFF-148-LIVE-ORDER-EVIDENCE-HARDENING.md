# HANDOFF-148 - Live Order Evidence Hardening

## 결론

#622로 첫 실주문이 실패했는데 성공처럼 보일 수 있는 워크플로 결함을 제거했다. 주문 직후 KIS
체결 동기화와 감사 장부·잔고 증거를 같은 production 실행에 연결했고 서버 배포와 KIS 읽기 점검도
통과했다. 실제 주문·체결·수익은 아직 0이며 T012와 목표는 완료가 아니다.

## 현재 사실

- main: `d6bda48` (#622), 안전 경계 커밋 `9ff629a`
- deploy run: `31920536032`, success
- KIS smoke run: `31920565098`, success 5/5
- 서버 smoke checkout: `d6bda48`
- 센티넬: `armed:true`, rung 1, `capital_usd:293`
- KIS: 현금 934.27달러, 총자산 1466.83달러, ORANY 28주
- 최근 주문: 0건, 열린 미체결: 0건
- 마지막 미리보기: `SPYM` 1주 + `GLDM` 1주, 계획 매수 178.32달러
- 실제 주문·체결·수익: 0

## #622가 보강한 경로

1. 실주문 SSH 종료 코드를 `LIVE` 단계에 그대로 전파한다.
2. 실주문 성공·실패 뒤 모두 KIS `fills --sync`를 최대 세 번 실행한다.
3. 체결 동기화는 주문·취소 없이 기존 열린 주문의 체결만 추가-전용 장부에 반영한다.
4. 사후 NAV·forward 측정도 자체 종료 코드를 전파한다.
5. 어느 단계가 실패해도 sidecar 발행은 실행해 단계별 결과, 주문 JSON, stderr, 열린 주문,
   최근 체결, 사후 측정 로그를 보존한다.

## 다음 실행

- 예약: `0 15 * * 1-5`, 다음 실행은 2026-08-18 00:00 KST.
- production 환경은 `main`만 허용하고 required reviewer `jinooaction` 승인을 요구한다.
- 승인 뒤 run의 production sidecar에서 다음을 대조한다.
  - `LIVE 스텝=success`와 주문 결과의 KIS 주문 식별자·상태
  - 체결 동기화 결과의 열린 주문·최근 체결
  - 사후 잔고·NAV와 추가-전용 감사 로그
  - ORANY 자동 매도 0건
- 지정가가 즉시 체결되지 않으면 목표 완료로 판정하지 않는다. 다음 KIS smoke와 후속 동기화에서
  체결 또는 명시적 미체결 상태를 계속 확인한다.

## 검증과 되돌림

- focused 49 passed
- 전체 2828 passed, 6 skipped
- ruff, YAML parse, diff, HANDOFF 사실 검사, 엄격 하네스 14/14, PR 품질 관문 통과
- 이상 주문·수량·비관리 보유 매도·캡 위반이 보이면 센티넬을 `armed:false`로 내려 신규 주문을
  차단한다. 코드 되돌림은 #622 merge commit `d6bda48`을 새 PR에서 revert하되 감사 로그와 계좌
  기록은 삭제하지 않는다.
