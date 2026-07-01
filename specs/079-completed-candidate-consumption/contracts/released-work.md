# 계약: released-work sidecar

## JSON 출력

`released_work.json`은 다음 최상위 필드를 가진다.

```json
{
  "schema_version": "1.0",
  "run_id": "local",
  "commit": "unknown",
  "timestamp_utc": "2026-07-02T09:05:00Z",
  "overall_status": "OK",
  "scanned_specs": 79,
  "released_work": [
    {
      "entry_id": "released-...",
      "candidate_id": "candidate-fd04772a23c5",
      "status": "released",
      "source_spec": "specs/078-money-gate-alignment-loop",
      "source_file": "specs/078-money-gate-alignment-loop/contracts/money-gate-alignment.md",
      "reason_ko": "완료된 spec 산출물이 이 후보를 출시 완료 작업으로 기록했다.",
      "released_at_utc": "2026-07-02T09:05:00Z"
    }
  ],
  "safety_invariants": []
}
```

## Markdown 출력

`LAST_RUN.md`는 사람이 읽는 요약, 완료 후보 표, 스캔한 spec 수, 안전 경계, 결정 JSON을 포함한다.

## 자율 작업 실행 입력

`autonomous-work-execution`은 `released-work` evidence를 읽는다.

- 입력이 정상 JSON이면 `released_work` 목록의 `candidate_id`를 완료 후보로 본다.
- 입력이 없거나 malformed이면 기존 후보 선택을 계속한다.
- 완료 후보는 `RELEASED` 상태로 suppress되고 선택 대상에서 제외된다.

## 안전 계약

- 출력은 보고 전용이다.
- workflow는 브로커, 주문, 라이브 전환, 원격 서버 명령, 외부 비용 명령을 포함하지 않는다.
- 실패해도 기존 돈 경로 게이트 상태를 변경하지 않는다.
