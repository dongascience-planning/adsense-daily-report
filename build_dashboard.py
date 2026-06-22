"""누적 리포트(일지) 대시보드 생성 → report/dashboard.html (자체 완결 HTML).

- 월별/일별 수익 추이 그래프 (외부 라이브러리 없이 인라인 SVG)
- 매일 받은 인사이트 로그
- 날짜별 일지: 계획 → 시도 → 결과 (브라우저 localStorage 저장 + journal.json 내보내기/씨드)
- 용어 사전
data/*.json 누적분으로 매일 다시 그린다.
"""
import json

import common
import glossary

REPORT_DIR = common.BASE_DIR / "report"
MONTHLY_HISTORY = common.DATA_DIR / "monthly_history.json"
JOURNAL = common.DATA_DIR / "journal.json"


def load_days():
    days = []
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json")):
        rec = common.load_json(f)
        if not rec or "date" not in rec:
            continue
        t = (rec.get("adsense") or {}).get("total", {}) or {}
        ga = (rec.get("ga4") or {}).get("total", {}) or {}
        days.append({
            "date": rec["date"],
            "earnings": t.get("earnings"),
            "ad_requests": t.get("ad_requests"),
            "matched": t.get("matched_ad_requests"),
            "coverage": t.get("ad_requests_coverage"),
            "impressions": t.get("impressions"),
            "page_views": t.get("page_views"),
            "rpm": t.get("impressions_rpm"),
            "bounce_rate": ga.get("bounce_rate"),
            "avg_session_duration": ga.get("avg_session_duration"),
            "sessions": ga.get("sessions"),
            "insight": rec.get("insight", ""),
        })
    return days


def update_monthly_history(days):
    """월별 수익 시계열을 누적 유지. 지난달은 API의 last_month_full(확정), 이번달은 mtd(진행)."""
    hist = common.load_json(MONTHLY_HISTORY) or {}
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json")):
        rec = common.load_json(f)
        m = (rec or {}).get("monthly") or {}
        if not m or "date" not in (rec or {}):
            continue
        cur_label = rec["date"][:7]
        mtd = (m.get("mtd") or {}).get("earnings")
        if isinstance(mtd, (int, float)):
            hist[cur_label] = round(mtd, 2)
        lm_label = m.get("last_month_label")
        lm_full = (m.get("last_month_full") or {}).get("earnings")
        if lm_label and isinstance(lm_full, (int, float)):
            hist[lm_label] = round(lm_full, 2)
    common.save_json(MONTHLY_HISTORY, hist)
    return [{"month": k, "earnings": v} for k, v in sorted(hist.items())]


def latest_monthly_stats(days):
    """가장 최근 일별 레코드의 monthly_stats(목표 진행 등)."""
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"), reverse=True):
        rec = common.load_json(f)
        if rec and rec.get("monthly_stats"):
            return rec["monthly_stats"], (rec.get("adsense") or {}).get("currency", "USD")
    return None, "USD"


def build():
    REPORT_DIR.mkdir(exist_ok=True)
    days = load_days()
    months = update_monthly_history(days)
    stats, currency = latest_monthly_stats(days)
    journal_seed = common.load_json(JOURNAL) or {}

    payload = {
        "days": days,
        "months": months,
        "stats": stats,
        "currency": currency,
        "goal": (stats or {}).get("goal"),
        "journal": journal_seed,
        "glossary": [[term, desc] for term, _aliases, desc in glossary.GLOSSARY],
        "generated": days[-1]["date"] if days else "",
    }

    html = HTML_TEMPLATE.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False))
    out = REPORT_DIR / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    # 폴더를 그냥 열어도 보이도록 index.html 도 같이 생성
    (REPORT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[대시보드] 생성 완료 → {out}  (일별 {len(days)}건 / 월별 {len(months)}건)")
    return out


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>동아사이언스닷컴 광고 리포트 일지</title>
<style>
  :root{
    --bg:#0f1420; --card:#161d2e; --card2:#1d2638; --line:#2a3550;
    --txt:#e8edf7; --muted:#94a3c4; --accent:#4f8cff; --good:#3ecf8e; --warn:#f5a623; --bad:#ff6b6b;
    --mobile:#4f8cff; --desktop:#a78bfa; --tablet:#3ecf8e;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic","맑은 고딕",sans-serif;
    line-height:1.6;padding:24px;max-width:1100px;margin:0 auto;}
  h1{font-size:22px;margin:0 0 4px}
  h2{font-size:16px;color:var(--muted);margin:32px 0 12px;font-weight:600;
     border-bottom:1px solid var(--line);padding-bottom:8px}
  .sub{color:var(--muted);font-size:13px;margin-bottom:8px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:16px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .kpi .label{color:var(--muted);font-size:12px}
  .kpi .val{font-size:24px;font-weight:700;margin-top:4px}
  .kpi .note{font-size:12px;color:var(--muted);margin-top:4px}
  .good{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;overflow-x:auto}
  .bar-track{height:10px;background:var(--card2);border-radius:6px;overflow:hidden;margin-top:8px}
  .bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--good))}
  table{width:100%;border-collapse:collapse;font-size:13px;min-width:520px}
  .log{margin-top:8px}
  .entry{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
  .entry .top{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
  .entry .date{font-weight:700;font-size:15px}
  .entry .earn{color:var(--good);font-weight:700}
  .entry .insight{margin:10px 0;color:var(--txt);font-size:14px}
  .journal{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
  .journal label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}
  .journal textarea{width:100%;min-height:64px;resize:vertical;background:var(--card2);
    color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;font-size:13px}
  .journal textarea:focus{outline:none;border-color:var(--accent)}
  .gloss{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
  .gloss .t{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
  .gloss .term{font-weight:700;color:var(--accent)}
  .gloss .desc{font-size:13px;color:var(--muted);margin-top:2px}
  .toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}
  button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;
    font:inherit;cursor:pointer;font-weight:600}
  button.ghost{background:transparent;border:1px solid var(--line);color:var(--muted)}
  .saved{color:var(--good);font-size:12px;opacity:0;transition:opacity .3s}
  .axis{font-size:10px;fill:var(--muted)}
  .empty{color:var(--muted);font-size:13px;padding:12px}
</style>
</head>
<body>
  <h1>📊 동아사이언스닷컴 광고 리포트 일지</h1>
  <div class="sub" id="sub"></div>

  <div class="kpis" id="kpis"></div>

  <h2>🎯 월 목표 진행</h2>
  <div class="card" id="goalCard"></div>

  <h2>월별 수익</h2>
  <div class="card" id="monthChart"></div>

  <h2>일별 수익 (최근 60일)</h2>
  <div class="card" id="dayChart"></div>

  <h2>📝 인사이트 일지 <span style="font-size:12px;color:var(--muted)">— 계획·시도·결과를 적으면 이 브라우저에 자동 저장됩니다</span></h2>
  <div class="toolbar">
    <button id="exportBtn">💾 일지 내보내기 (journal.json)</button>
    <span class="ghost" style="padding:8px 12px;border-radius:8px">내보낸 파일을 data\journal.json 으로 저장하면 다음 생성 때도 유지됩니다</span>
    <span class="saved" id="savedMsg">저장됨</span>
  </div>
  <div class="log" id="log"></div>

  <h2>📖 용어 사전</h2>
  <div class="gloss" id="gloss"></div>

<script>
const DATA = /*__DATA__*/;
const SYM = {USD:"$",KRW:"₩",EUR:"€",JPY:"¥",GBP:"£"}[DATA.currency] || (DATA.currency+" ");
const money = v => (typeof v==="number") ? SYM + v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) : "—";
const num = v => (typeof v==="number") ? Math.round(v).toLocaleString() : "—";
const el = (h)=>{const t=document.createElement("template");t.innerHTML=h.trim();return t.content.firstChild;};

/* ---------- KPI ---------- */
const s = DATA.stats;
const lastDay = DATA.days[DATA.days.length-1] || {};
document.getElementById("sub").textContent = "마지막 갱신: " + (DATA.generated||"-") + "  ·  통화 " + DATA.currency;

const kpis = [];
if(s){
  kpis.push(["이번 달 누적(MTD)", money(s.mtd), `${s.days_elapsed}/${s.days_in_month}일 경과`]);
  if(s.goal){
    const pct = s.progress_pct||0;
    kpis.push(["월 목표 달성률", pct.toFixed(0)+"%", "목표 "+money(s.goal)]);
    const gap = s.projected_gap||0;
    kpis.push(["이 추세 월말 예상", money(s.projection),
      (gap>=0?"초과 +":"부족 -")+money(Math.abs(gap)).slice(SYM.length-SYM.length)]);
  }
}
kpis.push(["어제 수익", money(lastDay.earnings), lastDay.date||""]);
document.getElementById("kpis").innerHTML = kpis.map(k=>
  `<div class="kpi"><div class="label">${k[0]}</div><div class="val">${k[1]}</div><div class="note">${k[2]||""}</div></div>`
).join("");

/* ---------- Goal bar ---------- */
const gc = document.getElementById("goalCard");
if(s && s.goal){
  const prog = Math.min(100, s.progress_pct||0);
  const proj = Math.min(100, s.projected_pct||0);
  const ok = (s.projected_gap||0) >= 0;
  gc.innerHTML =
    `<div style="display:flex;justify-content:space-between"><span>현재 달성 ${ (s.progress_pct||0).toFixed(0) }%</span>`+
    `<span class="${ok?'good':'warn'}">이 추세 월말 ${ (s.projected_pct||0).toFixed(0) }% (${money(s.projection)})</span></div>`+
    `<div class="bar-track"><div class="bar-fill" style="width:${prog}%"></div></div>`+
    `<div class="note" style="margin-top:8px;color:var(--muted);font-size:13px">`+
    `목표 ${money(s.goal)} · ${ok?'목표 초과 예상 🎉':'남은 '+s.days_left+'일 동안 하루 '+money(s.needed_daily)+' 필요'}`+
    (typeof s.vs_lm_same_pct==="number" ? ` · 지난달 동기 대비 ${s.vs_lm_same_pct>=0?'+':''}${s.vs_lm_same_pct.toFixed(1)}%`:"")+
    `</div>`;
} else {
  gc.innerHTML = `<div class="empty">월 목표가 설정되지 않았습니다. .env 의 MONTHLY_REVENUE_GOAL 을 채우면 진행률이 표시됩니다.</div>`;
}

/* ---------- bar chart (SVG) ---------- */
function barChart(container, items, opts){
  opts = opts||{};
  if(!items.length){ container.innerHTML = `<div class="empty">데이터가 쌓이면 그래프가 표시됩니다.</div>`; return; }
  const W = Math.max(container.clientWidth, items.length*16, 320), H = 220, pad = {l:48,r:8,t:12,b:34};
  const max = Math.max(...items.map(d=>d.value||0), 1);
  const bw = (W-pad.l-pad.r)/items.length;
  const y = v => H-pad.b - (v/max)*(H-pad.t-pad.b);
  let bars="", labels="";
  const everyN = Math.ceil(items.length/12);
  items.forEach((d,i)=>{
    const h = (d.value||0)/max*(H-pad.t-pad.b);
    const x = pad.l + i*bw;
    bars += `<rect x="${x+bw*0.12}" y="${y(d.value||0)}" width="${bw*0.76}" height="${Math.max(0,h)}" rx="2" fill="${opts.color||'var(--accent)'}"><title>${d.label}: ${money(d.value)}</title></rect>`;
    if(i%everyN===0) labels += `<text class="axis" x="${x+bw/2}" y="${H-pad.b+14}" text-anchor="middle">${d.short||d.label}</text>`;
  });
  let grid="";
  for(let g=0;g<=3;g++){ const v=max*g/3; const yy=y(v);
    grid += `<line x1="${pad.l}" y1="${yy}" x2="${W-pad.r}" y2="${yy}" stroke="var(--line)" stroke-width="1"/>`;
    grid += `<text class="axis" x="${pad.l-6}" y="${yy+3}" text-anchor="end">${SYM}${Math.round(v)}</text>`;
  }
  container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="xMinYMid meet">${grid}${bars}${labels}</svg>`;
}

barChart(document.getElementById("monthChart"),
  DATA.months.map(m=>({label:m.month, short:m.month.slice(2), value:m.earnings})), {color:"var(--desktop)"});

const recentDays = DATA.days.slice(-60).map(d=>({label:d.date, short:d.date.slice(5), value:d.earnings}));
barChart(document.getElementById("dayChart"), recentDays, {color:"var(--accent)"});

/* ---------- insight log + journal ---------- */
const FIELDS = [["plan","🧭 계획 (이 부분을 이렇게 해결하려 한다)"],["tried","🔧 시도 (무엇을 해봤나)"],["result","📈 결과"]];
function jkey(date,field){ return "journal:"+date+":"+field; }
function jval(date,field){
  const ls = localStorage.getItem(jkey(date,field));
  if(ls!==null) return ls;
  return ((DATA.journal[date]||{})[field])||"";
}
const log = document.getElementById("log");
DATA.days.slice().reverse().forEach(d=>{
  const e = el(`<div class="entry"></div>`);
  e.innerHTML =
    `<div class="top"><span class="date">${d.date}</span>`+
    `<span class="earn">${money(d.earnings)}</span></div>`+
    `<div class="insight">${(d.insight||"").replace(/</g,"&lt;")||"<span class='empty'>인사이트 없음</span>"}</div>`+
    `<div class="journal">`+FIELDS.map(f=>
      `<div><label>${f[1]}</label><textarea data-date="${d.date}" data-field="${f[0]}"></textarea></div>`
    ).join("")+`</div>`;
  log.appendChild(e);
});
document.querySelectorAll(".journal textarea").forEach(t=>{
  t.value = jval(t.dataset.date, t.dataset.field);
  t.addEventListener("input", ()=>{
    localStorage.setItem(jkey(t.dataset.date,t.dataset.field), t.value);
    const m=document.getElementById("savedMsg"); m.style.opacity=1; clearTimeout(window.__st);
    window.__st=setTimeout(()=>m.style.opacity=0,800);
  });
});

/* ---------- export journal ---------- */
document.getElementById("exportBtn").addEventListener("click", ()=>{
  const out={};
  document.querySelectorAll(".journal textarea").forEach(t=>{
    if(!t.value.trim()) return;
    out[t.dataset.date]=out[t.dataset.date]||{};
    out[t.dataset.date][t.dataset.field]=t.value;
  });
  const blob=new Blob([JSON.stringify(out,null,2)],{type:"application/json"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="journal.json"; a.click();
});

/* ---------- glossary ---------- */
document.getElementById("gloss").innerHTML = DATA.glossary.map(g=>
  `<div class="t"><div class="term">${g[0]}</div><div class="desc">${g[1]}</div></div>`
).join("");
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
