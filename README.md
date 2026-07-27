# 동아사이언스닷컴 일일 AdSense + GA4 자동 보고

매일 아침 **AdSense 수익 + GA4 독자 반응**을 수집·분석하고, *광고가 독자를 쫓아내고 있지 않은지*까지 짚은 인사이트를 **Jandi**로 전송합니다. 사람 개입 0.

```
AdSense API ─┐
             ├─→ analyze.py (변화 계산 + claude -p 인사이트) ─→ Jandi Webhook
GA4 API ─────┘
```

## 파일 구성

| 파일 | 역할 |
|------|------|
| `common.py` | 환경변수/경로/날짜/변화율 공통 유틸 |
| `auth_adsense.py` | AdSense OAuth 최초 1회 인증 → `token_adsense.json` |
| `collect_adsense.py` | AdSense v2 API → 어제·기기별 수익/광고요청 등 |
| `collect_ga4.py` | GA4 Data API → 어제·기기별 이탈률/참여시간 등 |
| `analyze.py` | 데이터 통합 + 전일/7일평균 비교 + 월목표/충족 깔때기 + `claude -p` 인사이트 |
| `glossary.py` | 용어 사전 (인사이트에 쓰인 단어 풀이) |
| `build_dashboard.py` | 누적 리포트(일지) `report/dashboard.html` 생성 |
| `build_onepager.py` | 월간 원페이지 갱신 (`templates/` 원본 → `report/` 생성) |
| `send_jandi.py` | Jandi Incoming Webhook 전송 |
| `serve.py` / `serve.ps1` | `report/` 를 사내 LAN 에 서빙 |
| `run_daily.ps1` / `run_daily.sh` | 전체 파이프라인 (Win / mac·Linux) |
| `setup.ps1` | venv 생성 + 의존성 설치 |
| `register_schedule.ps1` | Windows 작업 스케줄러 매일 08:00 등록 |
| `CLAUDE.md` | Claude Code 용 프로젝트 맥락·규칙 (작업 전 자동 로딩) |
| `templates/` | 손수 만든 발표용 HTML 원본(원페이지·2주 성과보고) — git 추적 |

`data/YYYY-MM-DD.json` 에 일별 결과가 누적되어 추세 비교에 쓰입니다. (`report/` 는 생성물이라 커밋하지 않음)

## 최초 설정 (회사 PC, Windows)

### 0. 사전 발급물 (웹 콘솔에서 수동)
1. **Google Cloud 프로젝트** 생성 → API 라이브러리에서 `AdSense Management API`, `Google Analytics Data API` 둘 다 사용 설정
2. **AdSense용 OAuth**: 동의화면(외부) → 테스트 사용자에 본인 계정 추가 → 사용자 인증정보 → OAuth 클라이언트 ID → **데스크톱 앱** → `client_id` / `client_secret`
3. **GA4용 서비스 계정**: JSON 키 다운로드 → 그 서비스계정 이메일을 **GA4 속성 → 속성 액세스 관리 → 뷰어**로 추가
4. **GA4 속성 ID** (숫자): GA4 관리 → 속성 설정
5. **Jandi Incoming Webhook URL**: 토픽 → 커넥트 → Incoming Webhook 추가

### 1. 의존성 설치
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### 2. 자격증명 입력
- `.env` 에 `ADSENSE_CLIENT_ID`, `ADSENSE_CLIENT_SECRET`, `GA4_PROPERTY_ID`, `JANDI_WEBHOOK_URL` 채우기
- GA4 서비스계정 JSON 키를 이 폴더에 **`ga4-key.json`** 으로 저장 (`.env` 의 `GA4_SERVICE_ACCOUNT_JSON` 경로와 일치)

### 3. AdSense 최초 인증 (1회)
```powershell
.\.venv\Scripts\python.exe auth_adsense.py
```
브라우저가 열리면 본인 Google 계정으로 동의 → `token_adsense.json` 생성. 이후 무인 갱신됩니다.

### 4. 1회 수동 테스트
```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1
```
Jandi 토픽에 리포트가 도착하는지 확인하세요.

### 5. 매일 아침 자동 실행 등록 (08:00)
```powershell
powershell -ExecutionPolicy Bypass -File .\register_schedule.ps1
```

## 개별 실행 (디버깅)
```powershell
.\.venv\Scripts\python.exe collect_adsense.py   # → data/raw/adsense-*.json
.\.venv\Scripts\python.exe collect_ga4.py       # → data/raw/ga4-*.json
.\.venv\Scripts\python.exe analyze.py           # → data/*.json + 인사이트 출력
.\.venv\Scripts\python.exe send_jandi.py        # → Jandi 전송
```

## 리포트 구성 (Jandi)
1. **어제 수익** — 전일/7일평균 대비
2. **기기별** — 모바일/데스크톱/태블릿/커넥티드TV 수익·비중
3. **월 누적(MTD)** — 이번 달 1일~어제 누적, 지난달 동기간 대비 ±%
4. **🎯 월 목표** — 목표 대비 현재 달성률, 이 추세 월말 예상치, 부족/초과액, 남은 기간 일 필요액
5. **광고 충족** — 요청 → 매칭(충족률) → 노출 깔때기 ("부른 광고가 얼마나 실제로 채워지나")
6. **독자 반응** — 이탈률 / 평균 참여시간
7. **💡 인사이트** — `claude -p` 생성

## 인사이트 로직
- 어제 수익을 **전일 / 최근 7일 평균**과 비교, 모바일·데스크톱 분리 평가
- **월 목표 대비 페이스** — 목표 미달이면 월말 예상 부족액 + 무엇을 끌어올려야 하는지
- **월 누적·지난달 대비** — 수익은 월 단위로 보므로 MTD와 전월 동기 비교
- **광고 충족 깔때기(요청→매칭→노출)** — 충족률이 낮으면 "광고를 부르는 만큼 다 채워지지 않음" → 채움 개선 여지
- **이탈률↑·참여시간↓** 신호를 수익과 연결 → "광고는 늘었는데 독자가 떠나는지" 판정
- ±20% 이상 급변 시 맨 앞에 **⚠️ 경고** 한 줄
- `claude -p` 실패 시 규칙 기반 백업 인사이트로 대체 (파이프라인 중단 없음)

## 월간 원페이지 (회의용 보고)
`build_onepager.py` 가 매일 아침(파이프라인 6번째 best-effort 스텝) **7월 광고 최적화 캠페인 원페이지**를 갱신한다.
- **디자인 원본**: `templates/광고수익_원페이지.html` (git 추적) — 레이아웃은 여기를 고친다.
- **생성물**: `report/광고수익_원페이지.html` (gitignore) — 원본에 그날까지의 실적 데이터만 주입해 출력.
- 대시보드 상단 버튼(📈)으로 열 수 있고, `templates/광고수익_성과보고_2주.html`(2주 성과보고)도 함께 report/로 복사된다.

## 협업 (dongascience-planning 조직) · Claude Code
이 저장소는 **`dongascience-planning` 조직**의 **비공개(private)** repo다. (과거 개인 repo `chans-ex` 에서 이관 — 이제 조직 repo에서만 작업)

Claude Code는 "프로젝트" 개념 없이 **저장소 폴더 단위**로 동작한다. 협업은 곧 **Git 협업**이다:
1. `git clone` 후 각자 로컬에서 `claude` 실행 → 루트의 **`CLAUDE.md` 가 자동 로딩**되어 두 사람의 Claude가 같은 규칙·맥락으로 일한다.
2. **인증·비밀키는 공유하지 않는다** — 각자 위 *최초 설정* 절차로 본인 `.env` / `token_adsense.json` / `ga4-key.json` 을 로컬에 만든다. (`.gitignore` 로 커밋 차단됨)
3. 코드 변경은 브랜치 → PR 로 주고받는다. (실시간 세션 공유가 아니라 Git 으로 동기화)

### 새 팀원 온보딩 요약
```powershell
git clone https://github.com/dongascience-planning/adsense-daily-report.git
cd adsense-daily-report
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # venv + 의존성
copy .env.example .env                                  # 값 채우기
.\.venv\Scripts\python.exe auth_adsense.py              # 본인 Google 인증(1회)
# ga4-key.json 배치 후
.\.venv\Scripts\python.exe build_dashboard.py           # 리포트 로컬 생성 확인
claude                                                  # CLAUDE.md 자동 로딩됨
```

> ⚠️ **최우선 규칙**: 광고를 과하게 가려 기사 읽기를 방해하지 않는다(모바일 인아티클 ≤30%, 이탈률 함께 감시). 자세한 맥락은 `CLAUDE.md` 참고.

### 월 목표 변경
`.env` 의 `MONTHLY_REVENUE_GOAL`(USD) 값을 바꾸면 됩니다. 비우면 목표 라인이 생략됩니다.
(현재 $2,850 = 지난달 실적 $1,422.77의 약 2배)

### 📖 용어 팁
`glossary.py` 의 용어 사전에서, 그날 인사이트에 실제로 등장한 단어를 골라 리포트 하단에 풀이로 붙입니다(최대 4개). 새 용어를 추가하려면 `glossary.py` 의 `GLOSSARY` 리스트에 `(표시명, 별칭들, 설명)` 한 줄을 더하면 됩니다.

### 📂 누적 리포트(일지) 대시보드
`build_dashboard.py` 가 매일 `report/dashboard.html`(=`index.html`) 을 다시 그립니다. 외부 라이브러리 없이 자체 완결된 HTML이라 브라우저로 바로 열면 됩니다(즐겨찾기 권장).
- **월별/일별 수익 그래프** — `data/monthly_history.json` 에 월별 실적을 누적(지난달=확정, 이번달=진행)
- **인사이트 일지** — 날짜별 인사이트 + `🧭 계획 / 🔧 시도 / 📈 결과` 입력칸
  - 입력은 그 브라우저(localStorage)에 자동 저장됩니다.
  - **💾 일지 내보내기** 버튼 → `journal.json` 다운로드. 그 파일을 `data/journal.json` 으로 저장하면 다음 생성 때도 일지가 유지되고 PC/브라우저가 바뀌어도 살아남습니다.
- **용어 사전** — 전체 용어 풀이
- 회사 PC라 Jandi에서 클릭 가능한 URL은 아니고 로컬 파일 경로로 안내됩니다. 클라우드 이전 시 진짜 공유 URL이 됩니다.

## 보안
- `.env`, `*.json`(서비스계정 키), `token_adsense.json`, `data/` 는 `.gitignore` 로 커밋 차단
- 자격증명은 로컬에만 저장. GitHub 사용 시 **private 저장소**

## 한계 / 다음 단계
- 작업 스케줄러는 **PC가 켜져 있어야** 실행됩니다. (`-WakeToRun`, `-StartWhenAvailable` 로 절전/지각 실행은 일부 보완)
- 검증 후 **GitHub Actions / 클라우드**로 이전하면 완전 무인화 가능 (별도 단계).
