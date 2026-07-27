# CLAUDE.md — 동아사이언스닷컴 광고수익 자동 리포트

이 저장소에서 Claude Code가 일할 때 반드시 알아야 할 맥락. **작업 전 먼저 읽는다.**

## 이 프로젝트가 하는 일
`dongascience.com`(AdSense `pub-8747961643354099`)의 **일일 AdSense 수익 + GA4 독자반응**을 매일 아침 자동 수집·분석해서, "광고가 독자를 쫓아내고 있지 않은지"까지 짚은 인사이트를 **Jandi**로 보낸다. 비기술 직군(서비스기획팀)이 본다.

## ⛔ 절대 제약 (모든 결정에 우선)
> **광고를 과하게 가리거나 하는 건 절대 금지.**

기사 읽기를 방해하면 안 된다. 모바일(전체 유입 90%+) 본문 인아티클 광고 밀도는 **≤30%**, 광고 조정 시 **이탈률(bounceRate)을 항상 함께 본다**. 수익이 올라도 이탈률이 나빠지면 되돌린다.

## 매일 아침 파이프라인 — 두 러너 (역할 분리)
`collect_adsense`는 `www.dongascience.com` 필터(`ADSENSE_SITE_FILTER`) 기준.

- **클라우드 CI (`.github/workflows/daily.yml`, 매일 09:00 KST) = Jandi 정본 + 데이터 이력.**
  `collect_adsense.py` → `collect_ga4.py` → `analyze.py` → **`send_jandi.py`(Jandi 전송)** → `data/` 커밋.
  대시보드/원페이지 빌드·GitHub Pages는 **하지 않는다**(Pages 미사용). Jandi 링크는 사내 LAN 주소(`DASHBOARD_URL`).
- **로컬 (`run_daily.ps1`, Windows 스케줄러 08:00) = 사내 LAN 서빙용 리포트 생성.**
  `collect` → `analyze` → `build_dashboard.py` → `build_onepager.py` → `report/` 생성 → `serve.py`가 LAN 서빙.
  **`send_jandi`는 하지 않는다**(이중 전송 방지 — Jandi는 클라우드만).

> ⚠️ `send_jandi.py`는 실제 메시지를 보낸다. **테스트로 함부로 실행 금지.** Jandi 전송처를 옮길 땐 반드시 한쪽만 켠다.
> ⚠️ 로컬에서 `auth_adsense.py` 재인증하면 새 토큰 발급 → GitHub Secret `TOKEN_ADSENSE_JSON`도 **반드시 갱신**(안 하면 클라우드 `invalid_grant`).

## 원페이지 (회의용 월간 보고, `광고수익_원페이지.html`)
- **디자인 원본은 `templates/광고수익_원페이지.html`(git 추적).** `build_onepager.py`가 `/*@DATA_START@*/…/*@DATA_END@*/` 블록의 데이터만 갈아끼워 **`report/`(gitignore, 생성물)** 로 출력한다. **레이아웃은 report/ 파일이 아니라 templates/ 원본을 고친다.**
- 2026년 7월 광고 최적화 캠페인 전용(실행 7/6~7/7, before/after 경계 **7/8**). 7월 내내 매일 데이터가 채워지다 월말에 완성된다.
- 하우스 스타일: 흰 배경, 보라(#6d3bf0) 단일 액센트, 명조 제목/Pretendard 본문. **회색=과거 기준(4~6월 평균), 보라=7월 성과** 규칙을 색으로 일관되게 지킨다.
- `report/광고수익_성과보고_2주.html`도 `templates/`가 원본이며 build_onepager 가 report/로 복사한다.

## 인증·비밀 (⚠️ 절대 커밋 금지 — 이미 `.gitignore` 처리됨)
`.env`, `token_adsense.json`, `ga4-key.json` 은 **각자 로컬에만** 둔다. 새 환경에서:
1. `.env.example` → `.env` 복사 후 값 채우기 (`ADSENSE_ACCOUNT`, `MONTHLY_REVENUE_GOAL`, Jandi Webhook 등).
2. `python auth_adsense.py` — 본인 Google 계정으로 AdSense OAuth 1회 인증 → `token_adsense.json` 생성.
3. GA4 서비스계정 키 `ga4-key.json` 배치(공유 키 또는 본인 발급).

## git 규칙
- `report/`, `.venv/`, `__pycache__/`, 로그, 비밀키 = 커밋 안 함(gitignore).
- **`data/*.json`(일별/월별 실적)은 커밋한다** — 추세·누적 비교에 필요. **비공개(private) 저장소 전제.** 공개로 바꾸면 안 된다(수익 데이터).
- 원격: `dongascience-planning` 조직. (과거 `chans-ex` 개인 repo에서 이관)

## 사이트 사실 (기획/개발 요청 시)
- Next.js/Tailwind. 기사 URL `/ko/news/{id}`, 본문 컨테이너 `article_body`.
- 광고: `googletag`(GPT/Ad Manager) + AdSense. 본문 인아티클은 `data-ad-layout=in-article`, 반응형은 `data-ad-format=auto` + `data-full-width-responsive=true`.
- 효율 지표: **방문당 수익/RPM**(earnings/sessions×1000) — 트래픽 변동과 무관하게 광고 효율을 본다.

## 로컬 미리보기
`serve.py`(또는 `serve.ps1`)가 `report/`를 LAN에 서빙. 대시보드 상단 버튼으로 2주 성과보고·월간 원페이지로 이동.
