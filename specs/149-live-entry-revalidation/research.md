# Research: 최신 엣지 재검증과 병렬 탐색

## Decision: 첫 체결 전 주문 시점 재검증

**Rationale**: 단 1 진입 당시 PSR 0.827은 합격했지만 최신 PSR 0.60173은 기준 0.80보다 낮고 체결은 0건이다. 과거 센티넬만으로 첫 노출을 허용하면 오래된 승인이 된다.

**Alternatives considered**: 모든 보유 상태에서 즉시 무장 해제는 위험 축소 매도까지 막을 수 있어 제외했다. 첫 체결 전만 재검증하고, 이후에는 기존 라이브 낙폭·정합성 방어를 적용한다.

## Decision: 주문 차단과 사다리 강등을 이중 적용

**Rationale**: 주문 job 차단은 즉시 보호하고, 사다리 강등은 권위 상태를 다음 실행에도 일치시킨다.

## Decision: 관찰 패킷은 challenger를 막지 않는다

**Rationale**: 현재 구현은 profit evidence가 존재하면 광역 후보 생성을 건너뛰어 `OBSERVATION_WAIT`만 선택한다. 연구와 live 관찰은 독립 루프여야 한다.

## Decision: liveness 개별 fetch fallback

**Rationale**: 원격 branch와 파일이 존재하는데 와일드카드 shallow fetch 결과에서 빠졌다. 실제 누락 판정 전에 정확한 ref를 한 번 직접 가져오는 것이 가장 좁은 복구다.
