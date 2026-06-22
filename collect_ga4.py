"""GA4 Data API → 어제 독자 반응(전체 + deviceCategory별) 수집.

서비스 계정 JSON 키 사용(무인 실행). 출력: data/raw/ga4-YYYY-MM-DD.json
"""
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
        "user_engagement_duration": weighted("user_engagement_duration"),
        "screen_page_views": total_pv,
        "sessions": sum(d.get("sessions", 0) or 0 for d in devices),
    }


def main():
    property_id = common.env("GA4_PROPERTY_ID", required=True)
    d = common.yesterday()
    data = fetch(property_id, d)
    out = common.RAW_DIR / f"ga4-{d.isoformat()}.json"
    common.save_json(out, {"date": d.isoformat(), "ga4": data})
    t = data["total"]
    print(f"[GA4] {d} 수집 완료 → {out}")
    print(f"  이탈률 {t.get('bounce_rate')}, 평균참여 {t.get('avg_session_duration')}s")


if __name__ == "__main__":
    main()
