# CGV 왕십리·홍대 — 명탐정 코난 예매 오픈 알리미

아이폰 텔레그램으로 새 회차를 받는 개인용 무료 알림 봇입니다. GitHub Actions에서 자동 실행되므로 본인 PC를 켜둘 필요가 없습니다.

- 극장: **왕십리(0074)**, **홍대(0191)**
- 영화: 제목에 **코난** 또는 **Detective Conan / Case Closed**가 들어간 영화
- 상영관: 전부(일반관, IMAX, SCREENX, 4DX 등)
- 시간표 확인: 기본 약 10분마다 실행 *요청*. GitHub 예약 실행은 지연/누락될 수 있습니다.
- 날짜: CGV가 현재 열어둔 날짜 중 향후 30일, 극장별 최대 14개 날짜를 확인.
- 첫 실행에 이미 있는 회차는 조용히 저장; 두 번째 실행부터 신규 회차 알림.
- 읽기만 하고 예매, 결제, 로그인은 자동으로 하지 않습니다.

> **주의**: 2026년 10월 현재 CGV가 쓰는 비공식 웹 예매 API 기반입니다. CGV에서 스키마를 변경하거나 GitHub IP에 HTTP 403을 주면 멈출 수 있습니다. 공개 코드 분석에 맞춰 작성하고 오프라인 테스트를 통과한 예제이지만, CGV 실제 연결은 이 환경에서 시험할 수 없었습니다. 반드시 실제 GitHub Actions의 `check`로 검증하세요.

## 준비물

1. [GitHub](https://github.com/) 회원가입 및 로그인
2. 아이폰에 [Telegram](https://apps.apple.com/app/telegram-messenger/id686449807) 설치 및 로그인
3. [공식 BotFather](https://t.me/BotFather)에서 `/newbot`으로 나만의 봇을 생성. 이름은 자유롭게, 사용자명은 영문 숫자로 만들고 `bot`으로 끝나야 함. 제공되는 **API Token은 절대로 공개하지 말 것**.
4. 만든 봇을 텔레그램에서 찾아 **시작 / Start**를 눌러주세요.
5. [@userinfobot](https://t.me/userinfobot)에 시작을 눌러 자신의 숫자 `Id`를 확인해 주세요. 이는 별도 제3자 봇이므로 개인정보 공유가 불편하다면 Telegram Bot API `getUpdates`로 본인 봇의 `/start` 메시지에 포함된 `chat.id`를 확인할 수도 있습니다. API 토큰이 포함된 주소는 공유하거나 스크린샷하지 마세요.

## 1. GitHub 저장소 만들기

1. GitHub 오른쪽 위 **+ → New repository**.
2. Repository name: `cgv-conan-alert`.
3. **Public** 선택 (표준 GitHub-hosted Actions가 공개 저장소에서 무료; 소스 파일에 토큰을 넣지 않습니다).
4. **Add a README file**은 체크하지 않고 **Create repository** 클릭.
5. 다운로드한 ZIP의 압축을 풀고, `cgv_conan_alert` 폴더 **안의 파일들을** 저장소 최상위에 올립니다. GitHub의 **uploading an existing file**에서 업로드하거나, 업로드가 어려우면 `Add file → Create new file`로 아래와 같은 경로에 내용을 넣으세요.

```text
.github/workflows/check.yml
watcher.py
state.json
README.md
tests/test_watcher.py   (테스트용, 없어도 본 실행은 가능)
```

**Mac 사용자는** Finder에서 `.github` 폴더가 숨겨질 수 있으니 `Command + Shift + .`(마침표)를 눌러 숨긴 파일을 표시하세요. **매우 중요**: `.github/workflows/check.yml`의 앞에 점(`.`)이 빠지면 자동 실행되지 않습니다. 업로드 후 저장소 코드 목록에 해당 파일이 있는지 확인하세요. ZIP 자체를 업로드하면 작동하지 않습니다.

## 2. GitHub Secrets 등록

저장소 화면에서 **Settings → Secrets and variables → Actions → New repository secret** 선택 후 2개를 각각 등록합니다.

| Name | Secret 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 받은 긴 API Token |
| `TELEGRAM_CHAT_ID` | 자신의 텔레그램 숫자 Id, 예: `123456789` |

**절대** `watcher.py`, `state.json`, README, Commit 메시지에 토큰을 적지 마세요. 토큰을 누군가 보았다면 BotFather에서 `/revoke`로 재발급하고 Secret을 변경하세요.

## 3. 아이폰 알림 활성화

- 아이폰의 **설정 → 알림 → Telegram → 알림 허용**.
- 만든 봇의 텔레그램 채팅에서 알림 끄기/음소거가 되지 않았는지 확인.
- 텔레그램 앱에서 봇에 `시작`을 눌러 먼저 대화를 연 상태여야 합니다. (`/start` 입력도 가능)

## 4. 알림 테스트 (CGV 접속 없이)

1. GitHub 저장소에서 **Actions** 탭을 클릭합니다.
2. 왼쪽 **CGV 코난 새 예매 회차 감시** 워크플로를 선택합니다.
3. **Run workflow** → `mode: test` → 초록색 **Run workflow**를 누릅니다.
4. 실행 내역을 클릭해서 결과가 ✅ 초록색인지 확인합니다.
5. 아이폰 텔레그램으로 `✅ CGV 코난 알림 연결 테스트 성공!`이 오면 성공입니다.

## 5. CGV 실연결/첫 기준선 만들기

1. 같은 **Run workflow**에서 `mode: check`로 바꾼 뒤 실행합니다.
2. `Check notification or CGV` 로그에서 `CGV 왕십리: 확인할 상영일 ...`, `CGV 홍대: ...` 출력이 있는지 확인하세요.
3. 첫 실행은 이미 열린 회차를 기준선으로 저장하므로 **새 회차 알림이 안 오는 게 정상**입니다.
4. 저장소 `state.json` 안의 `"initialized": true`가 되었는지 확인하세요.
5. 이후 약 10분 간격으로 새 회차를 검사하도록 등록되어 있습니다. (실제 시작 시간은 지연될 수 있습니다.)

## 운영할 때 알아둘 점

- `403` 또는 `429`: CGV 측에서 접근을 제한한 것일 수 있습니다. 강제로 우회하거나 주기를 급격히 늘리지 마세요. Actions 로그를 확인하세요. 하루에 한 번 오류 알림을 시도합니다.
- GitHub 예약 실행이 제때 실행되지 않거나 아예 빠질 수도 있어, 인기 회차의 즉각적인 예매를 보장하지 않습니다.
- 공개 저장소의 예약 워크플로는 60일 활동이 없으면 자동 비활성화될 수 있습니다. 이를 줄이기 위해 상태 파일에 약 25일마다 활동 기록을 남기지만, 주기적으로 Actions 탭에서 정상 작동하는지 확인해 주세요.
- 30일 뒤 날짜는 대상 밖이고, 날짜가 14개를 넘는 경우 먼저 열리는 날짜부터 감시합니다. `DAYS_AHEAD`, `MAX_DATES_PER_THEATER` 값을 조정할 수 있지만 요청량이 많아지지 않도록 주의하세요.
- 아이폰 알림은 Telegram 자체 푸시 알림에 의존합니다. iOS 집중 모드·알림 요약·텔레그램 채팅 음소거 설정을 확인하세요.
- 멈추려면 **Actions → 워크플로 선택 → ⋯ → Disable workflow**를 누르면 됩니다.
- 이 프로그램은 소스코드가 공개된 개인 학습/사용 목적 예시이며, CGV 공식 서비스가 아닙니다.

## 오프라인 자동 테스트

Python 3.12 이상에서 `python -m unittest discover -s tests -v`를 실행하면 네트워크 없이 내부 로직을 검증합니다.
