# Research

- 기존 `reconcile`은 불일치 때 halt를 만들지만 OK 때 해제하지 않는다.
- 기존 `resume --confirm`은 halt 이유를 구분하지 않아 자동화에 사용할 수 없다.
- `resume-readiness`는 최신 정합성·측정 계약을 읽지만 읽기 전용이다.
- 현재 money-path는 실제 halt를 입력으로 받지 않아 잘못된 `REAL_ORDER_PATH_ARMED`를 보고할 수 있다.
- production SSH 경계는 root 소유 helper와 고정 gateway 명령을 확장하는 방식이 기존 패턴과 맞다.

