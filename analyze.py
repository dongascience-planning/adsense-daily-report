"""데이터 통합 + 변화 계산 + claude -p 인사이트 생성.

- raw/adsense-*.json, raw/ga4-*.json 을 합쳐 data/YYYY-MM-DD.json 일별 레코드 작성
- 어제 vs 전일 vs 최근 7일 평균 변화 계산
- claude -p 로 실무자용 한국어 인사이트 3~5줄 생성
- Jandi 전송용 payload(data/_jandi-YYYY-MM-DD.json) 작성
출력: data/YYYY-MM-DD.json (insight 포함), data/_jandi-*.json
"""
import json
import os
import re
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
        "diagnostics": ad.get("diagnostics", {}),
        "ga4": ga.get("ga4", {}),
    }


def diagnostics_brief(record):
    """충족률 진단(기기/국가/광고단위)을 프롬프트용 텍스트로."""
    diag = record.get("diagnostics") or {}
    out = []
    for key, label in [("by_device", "기기"), ("by_country", "국가"), ("by_ad_unit", "광고단위")]:
        rows = diag.get(key) or []
        if not rows:
            continue
        out.append(f"[{label}별 — 요청/충족률/미충족/수익]")
        for r in rows[:6]:
            cov = r.get("coverage")
            covp = f"{cov*100:.0f}%" if isinstance(cov, (int, float)) else "?"
            req = int(r.get("requests") or 0)
            unf = int(r.get("unfilled") or 0)
            out.append(f"- {r.get('name')}: 요청 {req:,}, 충족 {covp}, 미충족 {unf:,}, 수익 ${r.get('earnings')}")
    return "\n".join(out)


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
    diag = diagnostics_brief(record)

    return f"""너는 언론사 디지털광고 담당자를 돕는 분석가다. 아래 어제 데이터를 보고 인사이트를 작성하라.

{data_block}

[충족률 진단 — 부른 광고가 어디서 안 채워지나]
{diag or '진단 데이터 없음'}

[작성 규칙]
- 위 '충족률 진단'을 활용해 충족률이 낮은 **진짜 원인 세그먼트**를 수치로 지목하라(요청은 많은데 충족·수익이 낮은 국가/기기/광고단위). 예: "충족률 저하의 대부분은 ○○(요청 N건, 충족 1%, 수익 거의 0)에서 발생" / "△△ 광고단위가 요청만 많고 충족 8%".
- 수익이 이미 잘 나오는(충족률 높은) 세그먼트는 굳이 손대라고 하지 말 것.
- 광고가 독자를 쫓아내고 있지 않은지 반드시 판정하라.
- 핵심 프레임: "광고 = (늘었나/줄었나), 독자 = (머무나/떠나나), 따라서 = (좋은 신호 / 주의 필요)".
- 월 목표가 있으면 목표 대비 현재 페이스(부족/초과)와 월말 예상치를 반드시 언급하라. 목표에 미달이면 무엇을 끌어올려야 하는지 한 가지 제시.
- 광고 깔때기(요청→매칭→노출): 충족률이 낮으면 "광고를 부르는 만큼 다 채워지지 않는다"는 뜻 → 채움 개선 여지를 짚어라.
- 이탈률↑·참여시간↓ 신호가 보이면 수익 변화와 연결해 해석.
- 어느 지표든 전일/7일평균 대비 ±20% 이상 급변이면 그 내용을 "⚠️ 경고: ..." 포인트로 맨 앞에.
- 모바일/데스크톱을 구분해 평가.

[출력 형식]
- 모든 줄을 '- '로 시작하는 한 문장 포인트로. 번호·머리말 금지. 평이한 한국어.
- 먼저 **핵심 진단 2~4개**(수익/목표 페이스/광고 충족/독자 반응).
- 그다음, 수익을 끌어올릴 **가장 중요한 기회 1가지의 실행 방안 2~4개**를 덧붙여라. 각 실행 방안은 아래 태그로 시작:
   [관리자] = 구글 AdSense 콘솔에서 코드 없이 바로 (예: 자동광고 켜기, 광고 게재율 100% 확인, 광고 형식 모두 허용, 차단관리 완화)
   [사이트] = 사이트·소스 수정 필요 (예: ads.txt 게시/수정, 반응형 광고단위로 교체, 빈 슬롯 자동 접기, 본문 광고 위치 추가, 페이지 속도·뷰어빌리티 개선)
   [확인] = 먼저 점검할 것 (예: ads.txt 경고 여부, 광고 게재율 값, 국가·시간대별 수요)
- 실제로 존재하는 AdSense 기능만 제시(없는 기능 추측 금지). 원인을 데이터로 단정 못 하면 [확인]으로.
- 단, 충족률(채움률)이 낮을 때는 [확인]만 나열하지 말고 **[관리자]와 [사이트] 실행 방안을 각각 최소 1개씩 반드시 포함**하라(충족률을 올리는 일반 조치는 데이터 없이도 권할 수 있다).
- '데이터 없음' 항목은 추측하지 말 것.

포인트 목록만 출력하라."""


def to_points(text):
    """인사이트 텍스트를 말머리(포인트) 리스트로 분해."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    points = []
    for l in lines:
        for pre in ("- ", "• ", "* ", "· "):
            if l.startswith(pre):
                l = l[len(pre):].strip()
                break
        l = re.sub(r"^\d+[.)]\s*", "", l)  # "1. " 번호 제거
        if l:
            points.append(l)
    if len(points) <= 1:  # 불릿이 아니면 문장 단위로 분해
        points = [s.strip() for s in re.split(r"(?<=[.!?。])\s+", (text or "").strip()) if s.strip()]
    return points[:8]


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


# ---------- 액션 추적 (계획·실행 → 효과 자동 판정) ----------
TRACKING_PATH = common.DATA_DIR / "tracking.json"


def daily_series(n=21):
    """최근 n일 핵심 지표를 한 줄씩 — 효과 판정용 컨텍스트."""
    rows = []
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"))[-n:]:
        rec = common.load_json(f) or {}
        t = (rec.get("adsense") or {}).get("total", {}) or {}
        ga = (rec.get("ga4") or {}).get("total", {}) or {}
        cov = t.get("ad_requests_coverage")
        def s(v, suf="", pct=False):
            if not isinstance(v, (int, float)):
                return "?"
            return f"{round(v * 100) if pct else round(v)}{suf}"
        rows.append(
            f"{rec.get('date')}: 수익 ${t.get('earnings')}, 충족률 {s(cov, '%', pct=True)}, "
            f"노출 {s(t.get('impressions'))}, 이탈률 {s(ga.get('bounce_rate'), '%')}, "
            f"참여 {s(ga.get('avg_session_duration'), 's')}"
        )
    return "\n".join(rows)


def judge_item(item, series):
    """추적 항목의 효과를 데이터로 판정 → {'verdict':..., 'stop_suggested':bool}."""
    prompt = f"""너는 광고 운영 분석가다. 아래 '개선 액션'의 효과를 데이터로 판정하라.
- 원래 인사이트({item.get('date')}): {item.get('insight')}
- 계획: {item.get('plan') or '(미입력)'}
- 실행: {item.get('exec') or '(미입력)'}

일별 지표 추이:
{series}

규칙:
- 실행에 날짜가 있으면 그 이후 관련 지표 변화를 본다.
- 관련 지표(충족률/수익/노출/이탈률 등)가 개선/악화/무변화인지 수치로 판단.
- 데이터가 부족하면 "관찰 필요".
- verdict: 한국어 한 문장(수치 변화 포함, 예 "충족률 28%→41%, 효과 있음").
- stop_suggested: 효과가 분명해 더 추적 안 해도 되면 true, 아니면 false.

JSON만 출력: {{"verdict":"...","stop_suggested":true}}"""
    out = generate_insight(prompt)
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def judge_tracking_items(today):
    """tracking.json 의 active 항목 효과를 갱신하고 active 목록 반환."""
    data = common.load_json(TRACKING_PATH)
    if not data:
        return []
    series = daily_series()
    active = []
    for iid, item in data.items():
        if item.get("status") == "stopped":
            continue
        if not (item.get("plan") or item.get("exec")):
            continue
        if item.get("exec"):  # 실행이 있으면 효과 판정
            res = judge_item(item, series)
            if res:
                item["verdict"] = res.get("verdict")
                item["stop_suggested"] = bool(res.get("stop_suggested"))
                item["verdict_date"] = today.isoformat()
        active.append((iid, item))
    common.save_json(TRACKING_PATH, data)
    return active


def main():
    d = common.yesterday()
    record = build_record(d)
    comp = compute_comparisons(record, d)
    goal = goal_amount()
    stats = monthly_stats(record, goal)
    funnel = ad_funnel(record)

    prompt = build_prompt(record, comp, stats, funnel)
    raw_insight = generate_insight(prompt) or fallback_insight(comp)
    points = to_points(raw_insight)

    record["insight_points"] = points
    record["insight"] = "\n".join("• " + p for p in points)
    record["comparisons"] = comp
    record["monthly_stats"] = stats
    common.save_json(common.daily_path(d), record)

    # 추적 중인 액션(계획·실행)의 효과를 데이터로 판정
    active = judge_tracking_items(d)

    # Jandi payload 미리 계산해 send 단계로 전달
    payload = build_jandi_payload(d, record, comp, stats, funnel, active)
    common.save_json(common.DATA_DIR / f"_jandi-{d.isoformat()}.json", payload)

    print(f"[분석] {d} 완료 → {common.daily_path(d)}")
    print("─" * 50)
    print(record["insight"])


def _words(s):
    return set(re.findall(r"[가-힣A-Za-z0-9]+", (s or "").lower()))


def _is_similar(p, others, thresh=0.55):
    """단어 겹침(Jaccard)으로 어제 인사이트와 사실상 같은지 판단."""
    pw = _words(p)
    if not pw:
        return False
    for q in others:
        qw = _words(q)
        if qw and len(pw & qw) / len(pw | qw) >= thresh:
            return True
    return False


def new_insights_text(record, d):
    """어제와 겹치지 않는 '신규' 인사이트만 골라 Jandi용 텍스트로."""
    today = record.get("insight_points") or [
        ln.lstrip("•- ").strip() for ln in (record.get("insight", "") or "").split("\n") if ln.strip()
    ]
    prev = common.load_json(common.daily_path(d - timedelta(days=1)))
    prev_points = (prev or {}).get("insight_points", []) if prev else []
    new = [p for p in today if not _is_similar(p, prev_points)]
    # ⚠️ 경고를 앞으로, 그다음 최대 4줄만 (나머지는 대시보드에서)
    new.sort(key=lambda p: 0 if "경고" in p else 1)
    shown = new[:4]
    if not shown:
        return "오늘 신규 인사이트 없음 — 대시보드에서 전체 확인"
    extra = len(new) - len(shown)
    text = "\n".join("• " + p for p in shown)
    if extra > 0:
        text += f"\n…외 {extra}건은 대시보드에서"
    return text


def track_signal(item):
    """추적 항목 상태를 신호등 이모지로: 🟩효과 / 🟥중지제안 / ⬜관찰 / ⏳실행대기."""
    if item.get("stop_suggested"):
        return "🟥"
    if not (item.get("exec") or "").strip() or (item.get("exec") or "").strip() == "-":
        return "⏳"  # 실행 미입력 = 실행 대기
    v = item.get("verdict") or ""
    if not v:
        return "⏳"  # 실행은 있으나 아직 판정 전
    if "효과 있음" in v:
        return "🟩"
    return "⬜"  # 관찰 필요/혼재/판정 불가 등


def build_jandi_payload(d, record, comp, stats, funnel, active=None):
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
    info.append({"title": "💡 신규 인사이트", "description": new_insights_text(record, d)})

    # 추적 중인 액션의 효과 판정 (신호등: 🟩효과 🟥중지제안 ⬜관찰 ⏳실행대기)
    if active:
        rows = []
        for _iid, item in active[:6]:
            plan = (item.get("plan") or "").strip()
            exv = (item.get("exec") or "").strip()
            if exv in ("-", "—"):
                exv = ""
            label = plan or exv or (item.get("insight", "") or "").strip()
            rows.append(f"{track_signal(item)} {label}")
        rows.append("(🟩효과 🟥중지제안 ⬜관찰 ⏳대기 · 자세한 건 대시보드)")
        info.append({"title": "📌 추적 현황", "description": "\n".join(rows)})

    # 누적 리포트(일지) 대시보드 링크
    dash_url = os.getenv("DASHBOARD_URL")
    if dash_url:
        dash_desc = f"월별·일별 수익 추이 + 인사이트 일지:\n{dash_url}"
    elif os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
        dash_desc = "월별·일별 수익 추이 + 인사이트 일지 (공유 링크 준비 중 — Cloudflare 설정 후 표시)"
    else:
        dash_desc = f"월별·일별 수익 추이 + 인사이트 일지(로컬에서 열기):\n{common.BASE_DIR / 'report' / 'dashboard.html'}"
    info.append({"title": "📂 누적 리포트(일지)", "description": dash_desc})

    return {
        "body": f"[동아사이언스닷컴 일일 광고 리포트] {d.isoformat()}",
        "connectColor": "#1d63d1",
        "connectInfo": info,
    }


if __name__ == "__main__":
    main()
