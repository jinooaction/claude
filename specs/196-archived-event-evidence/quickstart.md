# 검사 절차

1. 세 gzip WARC와 목록·인용으로 data-model.md의 입력을 작성한다.
2. contracts/cli.md의 명령으로 새 보고서를 생성한다.
3. 지문·연결·조건부 시각·미확인 사항을 확인한다.
4. metadata 연결 ID를 바꾼 별도 사본은 실패해야 한다.
5. 실제 WMT 자료 결과와 원본 경로·지문을 release-evidence.md에 남긴다.

관련 pytest, 전체 ruff·pytest, agent_harness_probe.py --strict, check_handoff_facts.py를 실행한다. 이 기능 완성은 전체181 작업표 완료가 아니다.
