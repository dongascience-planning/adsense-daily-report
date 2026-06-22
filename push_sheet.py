"""구글시트에 하루 한 줄씩 누적 기록(일지).

- 이미 발급된 GA4 서비스계정(ga4-key.json)으로 시트에 쓴다(스코프만 spreadsheets).
- 같은 날짜 행이 있으면 데이터 칸(A~N)만 갱신하고, 일지 칸(O~Q: 계획/시도/결과)은 건드리지 않는다.
- 팀은 시트에서 일지 칸을 직접 편집/공유.

사전 준비:
  1) GCP 프로젝트에서 'Google Sheets API' 사용 설정
  2) 새 구글시트 생성 → 서비스계정 이메일을 '편집자'로 공유
  3) .env 에 SHEET_ID 설정 (시트 URL 의 /d/<여기>/edit)
"""
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

import common

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TAB = "일별"

HEADER = [
    "날짜", "어제수익($)", "월누적MTD($)", "월목표($)", "목표달성(%)", "월말예상($)",
    "광고요청", "매칭", "충족률(%)", "노출", "페이지뷰", "이탈률(%)", "평균참여(초)",
    "인사이트", "🧭 계획", "🔧 시도", "📈 결과",
]
DATA_COLS = 14  # A~N 까지 자동 기록, O~Q(15~17)는 일지(수동)


def _service():
    key_path = common.env("GA4_SERVICE_ACCOUNT_JSON", "./ga4-key.json")
    key_path = key_path if str(key_path).startswith(("/", "C:", "c:")) else (common.BASE_DIR / key_path)
    creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=SHEETS_SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_tab(svc, sheet_id):
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if TAB not in titles:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": TAB}}}]},
        ).execute()


def _ensure_header(svc, sheet_id):
    rng = f"{TAB}!A1:Q1"
    cur = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range=rng).execute().get("values", [])
    if not cur or cur[0][:1] != ["날짜"]:
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=rng,
            valueInputOption="RAW", body={"values": [HEADER]},
        ).execute()


# (제목, 차트종류, 시리즈 열 인덱스들, 좌축 제목) — 열 인덱스는 0-based(A=0)
CHARTS = [
    ("일별 수익 추이 ($)", "COLUMN", [1], "수익($)"),          # B: 어제수익
    ("월 누적 vs 목표 ($)", "LINE", [2, 3], "$"),               # C: MTD, D: 목표
    ("광고 충족률 & 이탈률 (%)", "LINE", [8, 11], "%"),         # I: 충족률, L: 이탈률
]


def _col_src(gid, c0, c1):
    # endRowIndex 를 비워 전체 열을 참조 → 행이 늘면 차트도 자동 확장
    return {"sheetId": gid, "startRowIndex": 0, "startColumnIndex": c0, "endColumnIndex": c1}


def _ensure_charts(svc, sheet_id):
    meta = svc.spreadsheets().get(
        spreadsheetId=sheet_id, fields="sheets(properties(sheetId,title),charts(chartId))"
    ).execute()
    tab = next((s for s in meta.get("sheets", []) if s["properties"]["title"] == TAB), None)
    if not tab:
        return "탭 없음"
    if tab.get("charts"):
        return "차트 이미 있음"
    gid = tab["properties"]["sheetId"]
    requests = []
    for i, (title, ctype, series_cols, left) in enumerate(CHARTS):
        requests.append({"addChart": {"chart": {
            "spec": {
                "title": title,
                "basicChart": {
                    "chartType": ctype,
                    "legendPosition": "BOTTOM_LEGEND",
                    "headerCount": 1,
                    "axis": [
                        {"position": "BOTTOM_AXIS", "title": "날짜"},
                        {"position": "LEFT_AXIS", "title": left},
                    ],
                    "domains": [{"domain": {"sourceRange": {"sources": [_col_src(gid, 0, 1)]}}}],
                    "series": [
                        {"series": {"sourceRange": {"sources": [_col_src(gid, c, c + 1)]}},
                         "targetAxis": "LEFT_AXIS"}
                        for c in series_cols
                    ],
                },
            },
            "position": {"overlayPosition": {
                "anchorCell": {"sheetId": gid, "rowIndex": 1 + i * 18, "columnIndex": 18},
                "widthPixels": 640, "heightPixels": 320,
            }},
        }}})
    svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": requests}).execute()
    return f"차트 {len(requests)}개 생성"


def _round(v, n=2):
    return round(v, n) if isinstance(v, (int, float)) else ""


def build_row(record):
    t = (record.get("adsense") or {}).get("total", {}) or {}
    ga = (record.get("ga4") or {}).get("total", {}) or {}
    st = record.get("monthly_stats") or {}
    cov = t.get("ad_requests_coverage")
    return [
        record.get("date", ""),
        _round(t.get("earnings")),
        _round(st.get("mtd")),
        _round(st.get("goal")) if st.get("goal") else "",
        _round(st.get("progress_pct"), 1) if st.get("goal") else "",
        _round(st.get("projection")),
        int(t["ad_requests"]) if isinstance(t.get("ad_requests"), (int, float)) else "",
        int(t["matched_ad_requests"]) if isinstance(t.get("matched_ad_requests"), (int, float)) else "",
        _round(cov * 100, 1) if isinstance(cov, (int, float)) else "",
        int(t["impressions"]) if isinstance(t.get("impressions"), (int, float)) else "",
        int(t["page_views"]) if isinstance(t.get("page_views"), (int, float)) else "",
        _round(ga.get("bounce_rate"), 1),
        _round(ga.get("avg_session_duration"), 0),
        record.get("insight", ""),
    ]


def upsert(svc, sheet_id, row):
    """같은 날짜 행이 있으면 A~N 갱신, 없으면 새 행 추가(일지 칸은 보존)."""
    col_a = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{TAB}!A:A").execute().get("values", [])
    dates = [r[0] if r else "" for r in col_a]
    date_str = row[0]
    if date_str in dates:
        r = dates.index(date_str) + 1  # 1-based
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{TAB}!A{r}:N{r}",
            valueInputOption="RAW", body={"values": [row]},
        ).execute()
        return f"갱신(행 {r})"
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id, range=f"{TAB}!A:N",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
    return "행 추가"


def main():
    sheet_id = common.env("SHEET_ID")
    if not sheet_id:
        print("[시트] SHEET_ID 미설정 — 시트 기록 건너뜀")
        return
    d = common.yesterday()
    record = common.load_json(common.daily_path(d))
    if not record:
        raise SystemExit(f"[시트오류] {common.daily_path(d)} 없음. analyze.py 를 먼저 실행하세요.")

    svc = _service()
    _ensure_tab(svc, sheet_id)
    _ensure_header(svc, sheet_id)
    action = upsert(svc, sheet_id, build_row(record))
    charts = _ensure_charts(svc, sheet_id)
    print(f"[시트] {d} {action} / {charts} → https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
