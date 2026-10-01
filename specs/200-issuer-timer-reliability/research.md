# 설계 근거와 반례

2026-10-02 GitHub workflow `collect-filing-observations.yml`의13회 실제schedule은
2026-09-29T06:49:14Z~10-01T21:17:14Z였고간격173.78~437.68분이다.
첫증분복구는원격49파일과일치,최신18run/145파일의사슬도검증했다.
GitHub는[공식이벤트안내](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)에서
정기이벤트가고부하에지연되거나누락될수있다고명시한다.설정분을바꾸는것만으로
15분관측을보증할근거가없다.

기존서버에는`auto-invest-intraday-paper.timer`의1분진단과
`auto-invest-deploy.timer`의장외30분배포안전망이실제운용된다.
[systemd 공식타이머설명](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml)은
달력시각·정확도·누락후한번의재개를구분한다.
[공식시간형식](https://github.com/systemd/systemd/blob/main/man/systemd.time.xml)은
분의쉼표목록과반복표기를허용한다.서버타이머도가동/시간동기검사가필요하며
놓친모든시각을자동보충한다고보면안된다.

원격18run의관측은목록18개·본문54개다.목록은동일blob1개,본문54개는각기
다른blob이었다.8198113바이트/145파일이며매15분무조건본문3개를받으면
512MiB제한이장기운용에서끝난다.목록불변시본문생략은선택검증결과로명시하고
24시간마다새본문을받아목록은같은데본문만바뀐경우를유한하게다룬다.

서버내사슬만있으면장애때증거가사라진다.서버에GitHub쓰기비밀값을새로넣는
대신기존GitHubActions의제한SSH읽기권한으로고정서버사본을전달하고별도
추가전용브랜치에검증후게시한다.그백업일정도지연될수있으므로실시간관측의
주체는서버이며원격사본의마지막보존시각을별도로보고한다.
