# 실행 계약

`uv run python -m auto_invest.analytics.intraday_diagnostic_receipt --input <private-stdout> --output <new-json> --source-sha <40hex> --run-id <digits>`

표준라이브러리검증만실행한다. 현재관측코드의기존6운용파일지문을계산해진단identity와비교한다.
성공exit0/작은JSON; 실패exit1/DIAGNOSTIC_RECEIPT_INVALID이며원래예외/응답은출력하지않는다.
새파일만허용하며symlink/기존파일은거절한다. 실제서버조회는이CLI외부의기존제한된SSH명령이다.
pull_request 전체검사는키를받지않고observe job은실행하지않는다.
workflow_dispatch/schedule은기존관측후검증된단일JSON만artifact로보관한다.
artifact이름은sourceSHA/runID/attempt로각관측을구분하며소스평문/암호문·가격장부는없다.
