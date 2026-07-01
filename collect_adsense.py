"""AdSense Management API v2 → 어제 데이터(전체 + 기기별) + 월 누적 수집.

출력: data/raw/adsense-YYYY-MM-DD.json
- adsense: 어제 전체/기기별 (수익, 광고요청→매칭→노출 깔때기 포함)
- monthly: 이번달 누적(MTD), 지난달 동기간, 지난달 전체
"""
import calendar
from datetime import date

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import common

# 어제 상세용 지표 (기기별)
METRICS = [
    "ESTIMATED_EARNINGS",
    "PAGE_VIEWS",
    "IMPRESSIONS",
    "IMPRESSIONS_RPM",
    "CLICKS",
    "PAGE_VIEWS_CTR",
    "AD_REQUESTS",            # 광고 요청 (광고 자리가 광고를 부른 횟수)
    "MATCHED_AD_REQUESTS",    # 그중 실제로 광고가 채워진 요청
    "AD_REQUESTS_COVERAGE",   # 충족률 = 매칭/요청
]
DIMENSIONS = ["DATE", "PLATFORM_TYPE_NAME"]

METRIC_KEY = {
    "ESTIMATED_EARNINGS": "earnings",
    "PAGE_VIEWS": "page_views",
    "IMPRESSIONS": "impressions",
    "IMPRESSIONS_RPM": "impressions_rpm",
    "CLICKS": "clicks",
    "PAGE_VIEWS_CTR": "page_views_ctr",
    "AD_REQUESTS": "ad_requests",
    "MATCHED_AD_REQUESTS": "matched_ad_requests",
    "AD_REQUESTS_COVERAGE": "ad_requests_coverage",
}

# 월 누적용 지표 (합계만, 기기 구분 X)
MONTHLY_METRICS = ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "AD_REQUESTS"]
MONTHLY_KEY = {
    "ESTIMATED_EARNINGS": "earnings",
    "PAGE_VIEWS": "page_views",
    "AD_REQUESTS": "ad_requests",
}


def service():
    if not common.TOKEN_ADSENSE.exists():
        raise SystemExit(
            "[인증필요] token_adsense.json 이 없습니다. 먼저 `python auth_adsense.py` 를 실행하세요."
        )
    creds = Credentials.from_authorized_user_file(str(common.TOKEN_ADSENSE), common.ADSENSE_SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            common.TOKEN_ADSENSE.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise SystemExit("[인증오류] 토큰이 유효하지 않습니다. `python auth_adsense.py` 재실행.")
    return build("adsense", "v2", credentials=creds, cache_discovery=False)


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


# 메인 사이트만 집계 (m./m2/ncdev(개발) 등 서브도메인 제외). 비우면 전체.
SITE_FILTER = common.env("ADSENSE_SITE_FILTER", "DOMAIN_NAME==www.dongascience.com")


def _generate(svc, account, start, end, metrics, dimensions=None):
    params = {
        "dateRange": "CUSTOM",
        "startDate_year": start.year,
        "startDate_month": start.month,
        "startDate_day": start.day,
        "endDate_year": end.year,
        "endDate_month": end.month,
        "endDate_day": end.day,
        "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if SITE_FILTER:
        params["filters"] = [SITE_FILTER]
    return (
        svc.accounts().reports().generate(account=f"accounts/{account}", **params).execute()
    )


def _currency(report):
    for h in report.get("headers", []):
        if h.get("currencyCode"):
            return h["currencyCode"]
    return "USD"


def _row_metrics(values_by_name, key_map):
    return {out: _to_number(values_by_name.get(api)) for api, out in key_map.items()}


def _totals_dict(report):
    headers = [h["name"] for h in report.get("headers", [])]
    cells = [c.get("value") for c in report.get("totals", {}).get("cells", [])]
    return dict(zip(headers, cells))


def fetch_daily(svc, account, target_date):
    report = _generate(svc, account, target_date, target_date, METRICS, DIMENSIONS)
    headers = [h["name"] for h in report.get("headers", [])]

    by_device = {}
    for row in report.get("rows", []):
        cells = [c.get("value") for c in row.get("cells", [])]
        row_dict = dict(zip(headers, cells))
        device = row_dict.get("PLATFORM_TYPE_NAME", "Unknown")
        by_device[device] = _row_metrics(row_dict, METRIC_KEY)

    total = _row_metrics(_totals_dict(report), METRIC_KEY)
    return {"total": total, "by_device": by_device, "currency": _currency(report)}


def _range_total(svc, account, start, end):
    report = _generate(svc, account, start, end, MONTHLY_METRICS)
    return _row_metrics(_totals_dict(report), MONTHLY_KEY)


def fetch_monthly(svc, account, y):
    """이번달 누적(1일~어제) / 지난달 동기간 / 지난달 전체."""
    lm_year = y.year if y.month > 1 else y.year - 1
    lm_month = y.month - 1 if y.month > 1 else 12
    lm_days = calendar.monthrange(lm_year, lm_month)[1]
    same_day = min(y.day, lm_days)
    cur_days = calendar.monthrange(y.year, y.month)[1]

    return {
        "days_elapsed": y.day,
        "days_in_month": cur_days,
        "mtd": _range_total(svc, account, date(y.year, y.month, 1), y),
        "last_month_same_period": _range_total(
            svc, account, date(lm_year, lm_month, 1), date(lm_year, lm_month, same_day)
        ),
        "last_month_full": _range_total(
            svc, account, date(lm_year, lm_month, 1), date(lm_year, lm_month, lm_days)
        ),
        "last_month_label": f"{lm_year}-{lm_month:02d}",
    }


# 충족률 진단용: 어디서 광고가 안 채워지는지 (요청→매칭→노출 + 충족률)
DIAG_METRICS = ["AD_REQUESTS", "MATCHED_AD_REQUESTS", "AD_REQUESTS_COVERAGE", "IMPRESSIONS", "ESTIMATED_EARNINGS"]
DIAG_DIMS = [
    ("by_device", "PLATFORM_TYPE_NAME"),
    ("by_country", "COUNTRY_NAME"),
    ("by_ad_unit", "AD_UNIT_NAME"),
    ("by_format", "AD_FORMAT_NAME"),
]


def fetch_diagnostics(svc, account, target_date, top=10):
    out = {}
    for key, dim in DIAG_DIMS:
        try:
            report = _generate(svc, account, target_date, target_date, DIAG_METRICS, [dim])
        except Exception as e:  # noqa: BLE001
            print(f"[진단 {key}] 수집 실패: {str(e)[:120]}")
            out[key] = []
            continue
        headers = [h["name"] for h in report.get("headers", [])]
        rows = []
        for row in report.get("rows", []):
            rd = dict(zip(headers, [c.get("value") for c in row.get("cells", [])]))
            req = _to_number(rd.get("AD_REQUESTS"))
            matched = _to_number(rd.get("MATCHED_AD_REQUESTS"))
            rows.append({
                "name": rd.get(dim),
                "requests": req,
                "matched": matched,
                "coverage": _to_number(rd.get("AD_REQUESTS_COVERAGE")),
                "impressions": _to_number(rd.get("IMPRESSIONS")),
                "earnings": _to_number(rd.get("ESTIMATED_EARNINGS")),
                "unfilled": (req - matched) if isinstance(req, (int, float)) and isinstance(matched, (int, float)) else None,
            })
        rows.sort(key=lambda x: (x["requests"] or 0), reverse=True)
        out[key] = rows[:top]
    return out


def main():
    account = common.env("ADSENSE_ACCOUNT", required=True)
    d = common.yesterday()
    svc = service()

    daily = fetch_daily(svc, account, d)
    monthly = fetch_monthly(svc, account, d)
    diagnostics = fetch_diagnostics(svc, account, d)

    out = common.RAW_DIR / f"adsense-{d.isoformat()}.json"
    common.save_json(out, {"date": d.isoformat(), "adsense": daily, "monthly": monthly, "diagnostics": diagnostics})

    t = daily["total"]
    print(f"[AdSense] {d} 수집 완료 → {out}")
    print(f"  어제 수익 ${t.get('earnings')}, 광고요청 {t.get('ad_requests')}, "
          f"충족률 {t.get('ad_requests_coverage')}")
    print(f"  월 누적(MTD) ${monthly['mtd'].get('earnings')} "
          f"/ 지난달 전체 ${monthly['last_month_full'].get('earnings')}")


if __name__ == "__main__":
    main()
