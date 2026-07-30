# -*- coding: utf-8 -*-
"""원페이지(광고수익_원페이지.html) 데이터 매일 갱신.

report/광고수익_원페이지.html 안의 /*@DATA_START@*/ ... /*@DATA_END@*/ 블록만
실제 AdSense 수치로 다시 써넣는다. 레이아웃/디자인/SVG 로직은 건드리지 않는다.

- 대상: 2026년 7월 광고 최적화 캠페인(before/after 경계 7/8) 원페이지.
  7월이 진행되는 동안 매일 아침 그날까지의 일별 수익이 곡선에 추가된다.
- 계산: 7월 일별(집계일까지) / 4~6월 일별평균 / 지난달(6월) 총수입 / 월 목표.
  숫자는 www.dongascience.com 필터 기준(collect_adsense._generate 와 동일).
"""
import calendar
import json
import re
import shutil
from datetime import date

import common
import collect_adsense as ca

TARGET_YEAR = 2026
TARGET_MONTH = 7

# 디자인 원본(git 추적) → 매일 데이터만 갈아끼워 생성물(report/, gitignore)로 출력.
TEMPLATE = common.BASE_DIR / "templates" / "광고수익_원페이지.html"
OUT = common.BASE_DIR / "report" / "광고수익_원페이지.html"
# 정적 발표자료(2주 성과보고)도 서빙되게 report/ 로 복사.
STATIC_PAGES = ["광고수익_성과보고_2주.html"]

_svc = ca.service()
_acct = common.env("ADSENSE_ACCOUNT", required=True)


def daily_earnings(year, month):
    """{일(int): 예상수익($)} — 데이터 없는 날은 빠짐."""
    last = calendar.monthrange(year, month)[1]
    rep = ca._generate(_svc, _acct, date(year, month, 1), date(year, month, last),
                       ["ESTIMATED_EARNINGS"], ["DATE"])
    heads = [h["name"] for h in rep.get("headers", [])]
    out = {}
    for row in rep.get("rows", []):
        rd = dict(zip(heads, [c.get("value") for c in row.get("cells", [])]))
        day = int(rd["DATE"].split("-")[2])
        out[day] = round(float(rd.get("ESTIMATED_EARNINGS") or 0), 2)
    return out


def prev_month(year, month, back):
    m = month - back
    y = year
    while m <= 0:
        m += 12
        y -= 1
    return y, m


def build_data():
    # 이번 달(7월) 일별 — 데이터 있는 마지막 날까지
    cur = daily_earnings(TARGET_YEAR, TARGET_MONTH)
    # AdSense 는 집계 중인 당일치도 돌려준다. 미완성 하루가 곡선 끝을 떨어뜨리고
    # 평균을 끌어내리므로, 이번 달을 그릴 때는 어제까지만 쓴다.
    today = date.today()
    if (TARGET_YEAR, TARGET_MONTH) == (today.year, today.month):
        cur = {d: v for d, v in cur.items() if d < today.day}
    if not cur:
        raise SystemExit("[원페이지] 이번 달 AdSense 데이터가 아직 없습니다.")
    as_of = max(cur)
    july = [cur.get(d, 0.0) for d in range(1, as_of + 1)]

    # 직전 3개월(4·5·6월) 일별 평균
    months = [daily_earnings(*prev_month(TARGET_YEAR, TARGET_MONTH, k)) for k in (1, 2, 3)]
    avg3 = []
    for d in range(1, 32):
        vals = [mo[d] for mo in months if d in mo]
        avg3.append(round(sum(vals) / len(vals), 1) if vals else 0.0)

    last_month_total = round(sum(months[0].values()), 2)  # 지난달(6월) 전체
    goal = float(common.env("MONTHLY_REVENUE_GOAL", "0") or 0)
    days_in_month = calendar.monthrange(TARGET_YEAR, TARGET_MONTH)[1]
    days_left = max(0, days_in_month - as_of)

    return {
        "year": TARGET_YEAR,
        "asOfDay": as_of,
        "daysLeft": days_left,
        "goal": goal,
        "lastMonth": last_month_total,
        "july": july,
        "avg3": avg3,
    }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)  # 클론 직후 report/ 없을 수 있음

    data = build_data()
    html = TEMPLATE.read_text(encoding="utf-8")
    block = "/*@DATA_START@*/\n  var DATA=%s;\n  /*@DATA_END@*/" % json.dumps(data, ensure_ascii=False)
    new_html, n = re.subn(r"/\*@DATA_START@\*/.*?/\*@DATA_END@\*/", lambda m: block, html, flags=re.S)
    if n != 1:
        raise SystemExit(f"[원페이지] 템플릿에서 DATA 마커를 찾지 못했습니다 (matched={n}).")
    OUT.write_text(new_html, encoding="utf-8")

    # 정적 발표자료 복사(대시보드 버튼 링크가 report/ 기준)
    for name in STATIC_PAGES:
        src = common.BASE_DIR / "templates" / name
        if src.exists():
            shutil.copyfile(src, OUT.parent / name)

    print(f"[원페이지] 갱신 완료 → {OUT.name}")
    print(f"  7/{data['asOfDay']} 기준 · MTD ${sum(data['july']):.2f} / 목표 ${data['goal']:.0f} "
          f"/ 지난달 ${data['lastMonth']:.2f} / 남은 {data['daysLeft']}일")


if __name__ == "__main__":
    main()
