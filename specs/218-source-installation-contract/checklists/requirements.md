# Specification Quality Checklist: 소스·설치 입력 연결 계약
**Created**: 2026-10-17 KST  
**Feature**: [spec.md](../spec.md)

## Content Quality
- [x] 운영자 가치와 이번 문서 범위가 분명하다.
- [x] 구현 선택은 plan/contracts로 분리했다. Git ROOT/HEAD·HMAC는 보존할 기존 계약 식별자다.
- [x] 필수 사용자 시나리오·요구사항·성공 기준·가정이 있다.
## Requirement Completeness
- [x] NEEDS CLARIFICATION 없음. 실제 외부 증거 미확인은 거짓 합격이 아닌 후속 착수 조건이다.
- [x] FR-001~010은 계약과 후속 C01~16으로 추적 가능하다.
- [x] 성공 기준은 문서 계약 완료이며 설치·전략·실행 허가 완료가 아니다.
- [x] 기존 기능/새 조건, 독립 기대값/이미지 자체보고, 정확commit/같은tree를 구분했다.
- [x] 입력 한도·실패·되돌림·비목표가 있다.
## Feature Readiness
- [x] 우선순위와 각 독립 검토 방법을 정의했다.
- [x] 실제 시험16통과를 주장하지 않는다. 전체181·PR895 승인·goal 상태를 보존한다.
