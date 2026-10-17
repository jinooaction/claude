# 재사용을 위해 보존한 인프라

운영자의 2026-10-17 지시에 따라 기존 자동매매 프로젝트의 실행 코드·데이터·자동화를 종료하고 제거했습니다. 이 GitHub 저장소와 Vultr 서버 인스턴스는 다른 프로젝트에서 사용할 수 있도록 남겼습니다.

## 서버

- 공급자/리전: Vultr / Tokyo
- 인스턴스: e8b0aeb6-9022-41e0-b005-93353769c3a8
- 기존 이름: auto-invest
- IP: 202.182.125.132
- 사양: Ubuntu 22.04 x64, 1 vCPU, RAM 1GB, SSD 25GB
- 관리자 화면: https://console.vultr.com/subs/?id=e8b0aeb6-9022-41e0-b005-93353769c3a8&sub_type=instances
- 관리자 SSH: root 사용자. 관리자 인증정보는 로그인한 Vultr 화면의 정상 제공 기능으로 이용하며, 이 문서나 채팅에 기록하지 않습니다.
- 기존 제한 SSH 사용자는 gh-deploy입니다. 등록된 키와 SSH 서비스는 유지했습니다. `/usr/local/sbin/auto-invest-deploy-gateway`는 `status`에 `AUTO_INVEST_RETIRED`만 반환하며, 과거 배포·거래 명령은 더 이상 실행하지 않습니다. 새 프로그램 배포 권한은 별도로 구성해야 합니다.

## GitHub 인증정보

이 저장소 Actions Secrets의 VULTR_SSH_HOST, VULTR_SSH_PORT, VULTR_SSH_USER, VULTR_SSH_PRIVATE_KEY, VULTR_SSH_KNOWN_HOSTS와 재사용 가능한 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID를 보존했습니다. 다른 저장소에 자동으로 상속되지 않습니다. 연구 자료 암호화 키와 공시 수집 연락정보, 기존 연구 변수는 삭제했습니다.

## 확인된 종료 상태

2026-10-17 22:43 KST 관리자 SSH 재확인:

- 기존 auto-invest 서비스·타이머가 등록/실행 목록에 없음.
- /opt/auto-invest 및 기존 /var/lib/auto-invest* 데이터 디렉터리 제거.
- 기존 배포·거래·관측 보조 프로그램과 sudo 권한 제거. 상태 확인 전용 SSH 게이트만 유지.
- SSH 서비스는 active이며 인스턴스는 유지.
- Mac의 기존 저장소·등록된 131개 작업 복사본·연구 자료·자동 실행 등록 제거. 별도 새 프로젝트와 LocalAIInvest 서비스는 보존.
- 기존 사용자 정의 GitHub Actions 60개 중단. 현재 파일 목록에 workflow나 실행 코드 없음.
- main 외 기존 브랜치 691개, 태그 29개, 릴리스 29개와 연구·검증 파일 정리.
- GitHub Pages 등록이 없어졌으며 기존 공개 주소는 HTTP 404.

## 보존된 기록과 주의점

저장소 자체를 지우거나 main 기록을 강제로 다시 쓰지 않았습니다. 따라서 과거 Git 커밋, PR/Actions 실행 기록, 서버의 공용 시스템 로그에는 이전 활동 기록이 남을 수 있습니다. 현재 작업 트리 제거와 과거 이력 완전 소거는 다른 작업입니다.

서버 인스턴스를 보존했으므로 기존 호스팅 요금은 계속됩니다. 기존 계좌 자산 매도·주문 취소·계좌 해지·새 프로그램 실거래 전환은 실행하지 않았습니다. 기존 프로젝트의 전략·운용 승인·미완료 과제를 새 프로젝트에 승계하지 않습니다.
