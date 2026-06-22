"""데이터 통합 + 변화 계산 + claude -p 인사이트 생성.

- raw/adsense-*.json, raw/ga4-*.json 을 합쳐 data/YYYY-MM-DD.json 일별 레코드 작성
- 어제 vs 전일 vs 최근 7일 평균 변화 계산
- claude -p 로 실무자용 한국어 인사이트 3~5줄 생성
- Jandi 전송용 payload(data/_jandi-YYYY-MM-DD.json) 작성
출력: data/YYYY-MM-DD.json (insight 포함), data/_jandi-*.json
"""
import os
import shutil
import subprocess
from datetime import timedelta

import requests

import common
import glossary

DEVICE_LABEL = {
    # AdSense PLATFORM_TYPE_NAME
    "High-end mobile devices": "모바일",
    "Mobile devices": "모바일",
    "Desktop": "데스크톱",
    "Tablets": "태블릿",
    "Connected TV": "커넥티드TV",
    "Other platforms": "기타",
    # GA4 deviceCategory
    "mobile": "모바일",
    "desktop": "데스크톱",
    "tablet": "태블릿",
    "smart tv": "커넥티드TV",
}


def build_record(d):
    ad = common.load_json(common.RAW_DIR / f"adsense-{d.isoformat()}.json") or {}
    ga = common.load_json(common.RAW_DIR / f"ga4-{d.isoformat()}.json") or {}
    return {
        "date": d.isoformat(),
        "adsense": ad.get("adsense", {}),
        "monthly": ad.get("monthly", {}),
        "ga4": ga.get("ga4", {}),
    }


_CURRENCY_SYMBOL = {"USD": "$", "KRW": "₩", "EUR": "€", "JPY": "¥", "GBP": "£"}


def currency_of(record):
    return get(record, ["adsense", "currency"], "USD")


def money(value, currency="USD"):
    if not isinstance(value, (int, float)):
        return "N/A"
    sym = _CURRENCY_SYMBOL.get(currency, currency + " ")
    return f"{sym}{value:,.2f}"


def goal_amount():
    raw = common.env("MONTHLY_REVENUE_GOAL")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def monthly_stats(record, goal):
    m = record.get("monthly") or {}
    mtd = (m.get("mtd") or {}).get("earnings")
    if not isinstance(mtd, (int, float)):
        return None
    days_elapsed = m.get("days_elapsed") or 0
    days_in_month = m.get("days_in_month") or 30
    daily_avg = mtd / days_elapsed if days_elapsed else 0.0
    projection = daily_avg * days_in_month
    lm_same = (m.get("last_month_same_period") or {}).get("earnings")
    lm_full = (m.get("last_month_full") or {}).get("earnings")

    stats = {
        "mtd": mtd,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "daily_avg": daily_avg,
        "projection": projection,
        "lm_same": lm_same,
        "lm_full": lm_full,
        "vs_lm_same_pct": common.pct_change(mtd, lm_same),
        "goal": goal,
    }
    if goal:
        days_left = max(0, days_in_month - days_elapsed)
        remaining = goal - mtd
        stats.update({
            "progress_pct": mtd / goal * 100,
            "projected_pct": projection / goal * 100,
            "remaining": remaining,
            "days_left": days_left,
            "needed_daily": (remaining / days_left) if (days_left > 0 and remaining > 0) else 0.0,
            "projected_gap": projection - goal,
        })
    return stats


def ad_funnel(record):
    t = get(record, ["adsense", "total"], {}) or {}
    req = t.get("ad_requests")
    matched = t.get("matched_ad_requests")
    imp = t.get("impressions")
    cov = t.get("ad_requests_coverage")
    fill = None
    if isinstance(imp, (int, float)) and isinstance(req, (int, float)) and req:
        fill = imp / req
    return {"requests": req, "matched": matched, "impressions": imp, "coverage": cov, "impr_per_req": fill}


def avg_of(records, path):
    """records 리스트에서 path(예: ['adsense','total','earnings']) 값들의 평균."""
    vals = []
    for r in records:
        cur = r
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, (int, float)):
            vals.append(cur)
    return sum(vals) / len(vals) if vals else None


def get(record, path, default=None):
    cur = record
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def compute_comparisons(record, d):
    prev = common.load_json(common.daily_path(d - timedelta(days=1)))
    week = common.load_history(d, days=7)

    def block(path):
        cur = get(record, path)
        prev_v = get(prev, path) if prev else None
        week_avg = avg_of(week, path)
        return {
            "current": cur,
            "prev": prev_v,
            "week_avg": week_avg,
            "vs_prev_pct": common.pct_change(cur, prev_v) if isinstance(cur, (int, float)) else None,
            "vs_week_pct": common.pct_change(cur, week_avg) if isinstance(cur, (int, float)) else None,
        }

    return {
        "earnings": block(["adsense", "total", "earnings"]),
        "ad_requests": block(["adsense", "total", "ad_requests"]),
        "impressions_rpm": block(["adsense", "total", "impressions_rpm"]),
        "page_views": block(["adsense", "total", "page_views"]),
        "bounce_rate": block(["ga4", "total", "bounce_rate"]),
        "avg_session_duration": block(["ga4", "total", "avg_session_duration"]),
        "sessions": block(["ga4", "total", "sessions"]),
    }


def device_earnings_summary(record):
    by = get(record, ["adsense", "by_device"], {}) or {}
    total = get(record, ["adsense", "total", "earnings"], 0) or 0
    parts = []
    for dev, m in sorted(by.items(), key=lambda kv: -(kv[1].get("earnings") or 0)):
        e = m.get("earnings") or 0
        share = (e / total * 100) if total else 0
        parts.append(f"{DEVICE_LABEL.get(dev, dev)} ${e:.2f} ({share:.0f}%)")
    return " / ".join(parts) if parts else "데이터 없음"


def build_prompt(record, comp, stats, funnel):
    cur = currency_of(record)

    def line(label, b, unit="", is_money=False):
        v = b["current"]
        if v is None:
            return f"- {label}: 데이터 없음"
        v_s = money(v, cur) if is_money else (f"{v:.2f}{unit}" if isinstance(v, float) else f"{v}{unit}")
        return (
            f"- {label}: {v_s} "
            f"(전일 {common.fmt_pct(b['vs_prev_pct'])}, 7일평균 {common.fmt_pct(b['vs_week_pct'])})"
        )

    lines = [
        f"날짜: {record['date']} (동아사이언스닷컴 dongascience.com)",
        line("어제 예상수익", comp["earnings"], is_money=True),
        f"- 기기별 수익: {device_earnings_summary(record)}",
        line("노출 RPM(단가)", comp["impressions_rpm"], is_money=True),
        line("페이지뷰", comp["page_views"]),
        line("이탈률", comp["bounce_rate"], unit="%"),
        line("평균 참여시간(초)", comp["avg_session_duration"], unit="s"),
        line("세션수", comp["sessions"]),
    ]

    # 광고 충족 깔때기
    if funnel.get("requests") is not None:
        cov = funnel.get("coverage")
        fill = funnel.get("impr_per_req")
        cov_pct = cov * 100 if isinstance(cov, (int, float)) else 0
        fill_pct = fill * 100 if isinstance(fill, (int, float)) else 0
        lines.append(
            f"- 광고 깔때기: 요청 {funnel['requests']:,.0f}"
            f" → 매칭 {(funnel.get('matched') or 0):,.0f} (충족률 {cov_pct:.0f}%)"
            f" → 노출 {(funnel.get('impressions') or 0):,.0f} (요청의 {fill_pct:.0f}%)"
        )

    # 월 누적 / 목표
    if stats:
        lines.append(
            f"- 월 누적(MTD): {money(stats['mtd'], cur)} "
            f"({stats['days_elapsed']}/{stats['days_in_month']}일), "
            f"지난달 동기 {money(stats.get('lm_same'), cur)} 대비 {common.fmt_pct(stats.get('vs_lm_same_pct'))}, "
            f"지난달 전체 {money(stats.get('lm_full'), cur)}"
        )
        lines.append(f"- 이 추세 월말 예상: {money(stats['projection'], cur)}")
        if stats.get("goal"):
            lines.append(
                f"- 월 목표: {money(stats['goal'], cur)} "
                f"(현재 달성 {stats['progress_pct']:.0f}%, 추세 도달 {stats['projected_pct']:.0f}%, "
                f"목표 대비 {'초과' if stats['projected_gap']>=0 else '부족'} {money(abs(stats['projected_gap']), cur)}); "
                f"남은 {stats['days_left']}일 동안 일 {money(stats['needed_daily'], cur)} 필요"
            )

    data_block = "\n".join(lines)

    return f"""너는 언론사 디지털광고 담당자를 돕는 분석가다. 아래 어제 데이터를 보고 인사이트를 작성하라.

{data_block}

[작성 규칙]
- 광고가 독자를 쫓아내고 있지 않은지 반드시 판정하라.
- 핵심 프레임: "광고 = (늘었나/줄었나), 독자 = (머무나/떠나나), 따라서 = (좋은 신호 / 주의 필요)".
- 월 목표가 있으면 목표 대비 현재 페이스(부족/초과)와 월말 예상치를 반드시 언급하라. 목표에 미달이면 무엇을 끌어올려야 하는지 한 가지 제시.
- 광고 깔때기(요청→매칭→노출): 충족률이 낮으면 "광고를 부르는 만큼 다 채워지지 않는다"는 뜻 → 채움 개선 여지를 짚어라.
- 이탈률↑·참여시간↓ 신호가 보이면 수익 변화와 연결해 해석.
- 어느 지표든 전일/7일평균 대비 ±20% 이상 급변이면 맨 앞에 "⚠️ 경고:" 한 줄 먼저.
- 모바일/데스크톱을 구분해 평가.
- 출력은 실무자용 평이한 한국어 4~6줄. 광고 전문용어 최소화. 불릿이나 머리말 없이 문장만.
- 데이터가 '데이터 없음'인 항목은 추측하지 말 것.

인사이트만 출력하라."""


def run_claude(prompt):
    claude = shutil.which("claude") or shutil.which("claude.cmd")
    if not claude:
        return None
    # .ps1 가 잡히면 같은 폴더의 .cmd 를 우선 사용(subprocess 직접 실행 호환)
    if claude.lower().endswith(".ps1"):
        cmd_alt = claude[:-4] + ".cmd"
        if shutil.os.path.exists(cmd_alt):
            claude = cmd_alt
    try:
        result = subprocess.run(
            [claude, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[claude 실행 실패] {e}")
        return None
    if result.returncode != 0:
        print(f"[claude 오류] rc={result.returncode}: {result.stderr.strip()[:300]}")
        return None
    return result.stdout.strip()


def call_anthropic_api(prompt):
    """claude CLI 가 없는 환경(클라우드 등)에서 Anthropic API 로 인사이트 생성.
    ANTHROPIC_API_KEY 가 있을 때만 동작. 모델은 ANTHROPIC_MODEL 로 변경 가능."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return text.strip() or None
    except Exception as e:  # noqa: BLE001
        print(f"[anthropic API 실패] {e}")
        return None


def generate_insight(prompt):
    """우선순위: 로컬 claude CLI → Anthropic API → 규칙기반 fallback(호출부에서)."""
    return run_claude(prompt) or call_anthropic_api(prompt)


def fallback_insight(comp):
    """claude -p 실패 시 규칙 기반 백업 인사이트."""
    ad = comp["ad_requests"]["vs_week_pct"]
    bounce = comp["bounce_rate"]["vs_week_pct"]
    ad_dir = "늘었" if (ad or 0) >= 0 else "줄었"
    reader = "떠나는" if (bounce or 0) > 0 else "머무는"
    earn = comp["earnings"]["current"]
    return (
        f"어제 예상수익은 ${earn:.2f} 수준입니다. "
        f"광고 요청은 7일평균 대비 {ad_dir}고, 이탈률 신호로는 독자가 {reader} 쪽입니다. "
        f"(자동 인사이트 생성에 실패해 규칙 기반 요약으로 대체했습니다.)"
        if isinstance(earn, (int, float))
        else "데이터 수집은 됐으나 인사이트 자동 생성에 실패했습니다. 원본 데이터를 확인하세요."
    )


def main():
    d = common.yesterday()
    record = build_record(d)
    comp = compute_comparisons(record, d)
    goal = goal_amount()
    stats = monthly_stats(record, goal)
    funnel = ad_funnel(record)

    prompt = build_prompt(record, comp, stats, funnel)
    insight = generate_insight(prompt) or fallback_insight(comp)

    record["insight"] = insight
    record["comparisons"] = comp
    record["monthly_stats"] = stats
    common.save_json(common.daily_path(d), record)

    # Jandi payload 미리 계산해 send 단계로 전달
    payload = build_jandi_payload(d, record, comp, stats, funnel)
    common.save_json(common.DATA_DIR / f"_jandi-{d.isoformat()}.json", payload)

    print(f"[분석] {d} 완료 → {common.daily_path(d)}")
    print("─" * 50)
    print(insight)


def build_jandi_payload(d, record, comp, stats, funnel):
    cur = currency_of(record)

    earn = comp["earnings"]
    earn_desc = (
        f"{money(earn['current'], cur)}  (전일 {common.fmt_pct(earn['vs_prev_pct'])} / 7일평균 {common.fmt_pct(earn['vs_week_pct'])})"
        if isinstance(earn["current"], (int, float))
        else "데이터 없음"
    )

    bounce = comp["bounce_rate"]
    dur = comp["avg_session_duration"]
    reader_desc = (
        f"이탈률 {bounce['current']:.0f}% (7일평균 {common.fmt_pct(bounce['vs_week_pct'])}) / "
        f"평균참여 {dur['current']:.0f}s (7일평균 {common.fmt_pct(dur['vs_week_pct'])})"
        if isinstance(bounce["current"], (int, float)) and isinstance(dur["current"], (int, float))
        else "데이터 없음"
    )

    # 광고 충족 깔때기
    if funnel.get("requests") is not None:
        cov = funnel.get("coverage")
        fill = funnel.get("impr_per_req")
        cov_pct = cov * 100 if isinstance(cov, (int, float)) else 0
        fill_pct = fill * 100 if isinstance(fill, (int, float)) else 0
        funnel_desc = (
            f"요청 {funnel['requests']:,.0f} → 매칭 {(funnel.get('matched') or 0):,.0f} "
            f"(충족률 {cov_pct:.0f}%) → 노출 {(funnel.get('impressions') or 0):,.0f} (요청의 {fill_pct:.0f}%)"
        )
    else:
        funnel_desc = "데이터 없음"

    info = [
        {"title": "어제 수익", "description": earn_desc},
        {"title": "기기별", "description": device_earnings_summary(record)},
    ]

    # 월 누적 / 목표
    if stats:
        mtd_desc = (
            f"{money(stats['mtd'], cur)} ({stats['days_elapsed']}/{stats['days_in_month']}일)  "
            f"· 지난달 동기 {money(stats.get('lm_same'), cur)} 대비 {common.fmt_pct(stats.get('vs_lm_same_pct'))}"
        )
        info.append({"title": "월 누적(MTD)", "description": mtd_desc})

        if stats.get("goal"):
            gap = stats["projected_gap"]
            goal_desc = (
                f"{money(stats['goal'], cur)}  · 현재 달성 {stats['progress_pct']:.0f}%  "
                f"· 이 추세 월말 {money(stats['projection'], cur)} ({'초과 +' if gap >= 0 else '부족 -'}{money(abs(gap), cur)})\n"
                f"남은 {stats['days_left']}일 동안 하루 {money(stats['needed_daily'], cur)} 필요"
            )
            info.append({"title": "🎯 월 목표", "description": goal_desc})

    info.append({"title": "광고 충족", "description": funnel_desc})
    info.append({"title": "독자 반응", "description": reader_desc})
    info.append({"title": "💡 인사이트", "description": record.get("insight", "")})

    # 인사이트에 쓰인 용어 풀이 (구글애드센스 이해도 ↑)
    tips = glossary.tips_for(record.get("insight", ""))
    if tips:
        tip_text = "\n".join(f"• {term} = {desc}" for term, desc in tips)
        info.append({"title": "📖 용어 팁", "description": tip_text})

    # 누적 리포트(일지) 대시보드 위치
    dashboard = common.BASE_DIR / "report" / "dashboard.html"
    info.append({
        "title": "📂 누적 리포트(일지)",
        "description": f"월별·일별 수익 추이 + 인사이트 일지 보기:\n{dashboard}",
    })

    return {
        "body": f"[동아사이언스닷컴 일일 광고 리포트] {d.isoformat()}",
        "connectColor": "#1d63d1",
        "connectInfo": info,
    }


if __name__ == "__main__":
    main()
