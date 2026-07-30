"""GA4 Data API → 독자 반응(전체 + deviceCategory별) 수집.

GA4 는 해당 일자가 끝난 뒤 하루 이상 지나야 지표가 확정된다. 아침 실행 시점의
전날(D-1) 데이터는 참여 세션이 덜 잡혀 이탈률이 실제의 2~3배로 부풀려진다.
(실측: D-1 +9시간 → 99%, +12시간 → 33%, 확정 후 재조회와 일치)

그래서 D-2 이후만 신뢰하고, 최근 며칠을 매일 다시 받아 덮어쓴다(자기 치유).
출력: data/raw/ga4-YYYY-MM-DD.json
"""
from datetime import date, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account

import common

METRICS = [
    "bounceRate",
    "averageSessionDuration",
    "userEngagementDuration",
    "screenPageViews",
    "sessions",
]
METRIC_KEY = {
    "bounceRate": "bounce_rate",
    "averageSessionDuration": "avg_session_duration",
    "userEngagementDuration": "user_engagement_duration",
    "screenPageViews": "screen_page_views",
    "sessions": "sessions",
}


def _client():
    key_path = common.env("GA4_SERVICE_ACCOUNT_JSON", required=True)
    key_path = (common.BASE_DIR / key_path) if not str(key_path).startswith(("/", "C:", "c:")) else key_path
    creds = service_account.Credentials.from_service_account_file(
        str(key_path), scopes=common.GA4_SCOPES
    )
    return BetaAnalyticsDataClient(credentials=creds)


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def fetch(property_id, target_date):
    client = _client()
    date_str = target_date.isoformat()
    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=date_str, end_date=date_str)],
        dimensions=[Dimension(name="date"), Dimension(name="deviceCategory")],
        metrics=[Metric(name=m) for m in METRICS],
    )
    resp = client.run_report(request)

    metric_headers = [h.name for h in resp.metric_headers]

    by_device = {}
    for row in resp.rows:
        device = row.dimension_values[1].value  # date, deviceCategory
        vals = {
            METRIC_KEY[metric_headers[i]]: _to_number(cell.value)
            for i, cell in enumerate(row.metric_values)
        }
        # GA4 bounceRate 는 0~1 비율 → 퍼센트(%)로 정규화
        if isinstance(vals.get("bounce_rate"), (int, float)):
            vals["bounce_rate"] *= 100.0
        by_device[device] = vals

    # 전체 = 가중 합산/평균. sessions 가중으로 비율 지표 평균.
    total = _aggregate(by_device)
    return {"total": total, "by_device": by_device}


def _aggregate(by_device):
    devices = list(by_device.values())
    if not devices:
        return {}
    total_sessions = sum(d.get("sessions", 0) or 0 for d in devices) or 1
    total_pv = sum(d.get("screen_page_views", 0) or 0 for d in devices)
    # 비율/기간 지표는 세션 가중 평균
    def weighted(key):
        num = sum((d.get(key, 0) or 0) * (d.get("sessions", 0) or 0) for d in devices)
        return num / total_sessions
    return {
        "bounce_rate": weighted("bounce_rate"),
        "avg_session_duration": weighted("avg_session_duration"),
        # 합계 지표 — 가중평균이 아니라 단순 합. (기기별 합이 전체보다 커지는 오류 수정)
        "user_engagement_duration": sum(d.get("user_engagement_duration", 0) or 0 for d in devices),
        "screen_page_views": total_pv,
        "sessions": sum(d.get("sessions", 0) or 0 for d in devices),
    }


SETTLE_DAYS = 2      # D-2 부터 확정본으로 본다
BACKFILL_DAYS = 4    # D-2 ~ D-5 를 매일 다시 받아 덮어쓴다


def main():
    property_id = common.env("GA4_PROPERTY_ID", required=True)
    today = date.today()
    for back in range(SETTLE_DAYS, SETTLE_DAYS + BACKFILL_DAYS):
        d = today - timedelta(days=back)
        try:
            data = fetch(property_id, d)
        except Exception as e:  # noqa: BLE001
            print(f"[GA4] {d} 수집 실패 (건너뜀): {str(e)[:120]}")
            continue
        out = common.RAW_DIR / f"ga4-{d.isoformat()}.json"
        common.save_json(out, {"date": d.isoformat(), "ga4": data})
        t = data["total"]
        print(f"[GA4] {d} 수집 완료 → {out}")
        print(f"  이탈률 {t.get('bounce_rate')}, 평균참여 {t.get('avg_session_duration')}s")


if __name__ == "__main__":
    main()
