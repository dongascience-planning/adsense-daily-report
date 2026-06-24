"""누적 리포트(일지) 대시보드 생성 → report/dashboard.html (+ index.html).

- 맨 위: 월 목표 진행을 그래프로(현재 채움 + 이 추세 월말 예상)
- 최근 7일 수익 꺾은선
- 인사이트 일지: 인사이트를 말머리 단위로, 각 항목에 계획/피드백 메모(브라우저 저장 + journal.json 내보내기)
- 용어는 본문에 마우스오버 풀이 + 맨 아래 접이식
data/*.json 누적분으로 매일 다시 그린다. 외부 라이브러리 없음.
"""
import json

import common
import glossary

REPORT_DIR = common.BASE_DIR / "report"
JOURNAL = common.DATA_DIR / "journal.json"
TRACKING = common.DATA_DIR / "tracking.json"


def load_days():
    days = []
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json")):
        rec = common.load_json(f)
        if not rec or "date" not in rec:
            continue
        t = (rec.get("adsense") or {}).get("total", {}) or {}
        points = rec.get("insight_points")
        if not points:
            txt = rec.get("insight", "") or ""
            points = [p.lstrip("•- ").strip() for p in txt.split("\n") if p.strip()]
        days.append({
            "date": rec["date"],
            "earnings": t.get("earnings"),
            "points": points,
            "stats": rec.get("monthly_stats"),
            "diagnostics": rec.get("diagnostics", {}),
        })
    return days


def latest_monthly_stats():
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"), reverse=True):
        rec = common.load_json(f)
        if rec and rec.get("monthly_stats"):
            return rec["monthly_stats"], (rec.get("adsense") or {}).get("currency", "USD")
    return None, "USD"


def build():
    REPORT_DIR.mkdir(exist_ok=True)
    days = load_days()
    stats, currency = latest_monthly_stats()
    journal_seed = common.load_json(JOURNAL) or {}
    tracking = common.load_json(TRACKING) or {}
    diagnostics = {}
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json"), reverse=True):
        r = common.load_json(f)
        if r and r.get("diagnostics"):
            diagnostics = r["diagnostics"]
            break

    gloss_ref = [[t, d] for t, _a, d in glossary.GLOSSARY]
    gloss_map = []
    for term, aliases, desc in glossary.GLOSSARY:
        for a in aliases:
            gloss_map.append([a, desc])
    gloss_map.sort(key=lambda x: -len(x[0]))  # 긴 단어 우선 매칭

    payload = {
        "headline": common.env("GOAL_HEADLINE", "🎯 이번 달 목표 : 일단 매출부터 올려보자"),
        "generated": days[-1]["date"] if days else "",
        "currency": currency,
        "stats": stats,
        "days": days,
        "journal": journal_seed,
        "tracking": tracking,
        "diagnostics": diagnostics,
        "glossRef": gloss_ref,
        "glossMap": gloss_map,
    }

    html = HTML_TEMPLATE.replace("/*__DATA__*/", json.dumps(payload, ensure_ascii=False))
    (REPORT_DIR / "dashboard.html").write_text(html, encoding="utf-8")
    (REPORT_DIR / "index.html").write_text(html, encoding="utf-8")
    npts = sum(len(d["points"]) for d in days)
    print(f"[대시보드] 생성 완료 → {REPORT_DIR / 'dashboard.html'}  (일별 {len(days)}건 / 인사이트 {npts}개)")
    return REPORT_DIR / "dashboard.html"


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>동아사이언스닷컴 광고 리포트 일지</title>
<style>
  :root{
    --bg:#f6f8fc; --card:#ffffff; --card2:#eef2f8; --line:#e1e7f0;
    --txt:#1b2333; --muted:#5b6780; --accent:#2563eb; --accent2:#3b82f6;
    --proj:#c7b3f5; --proj2:#ddd0f8; --good:#0f9d58; --warn:#d98300; --bad:#e5484d;
    --shadow:0 1px 3px rgba(16,24,40,.07), 0 1px 2px rgba(16,24,40,.04);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic","맑은 고딕",sans-serif;
    line-height:1.6;padding:24px;max-width:1000px;margin:0 auto;}
  h1{font-size:22px;margin:0 0 4px}
  h2{font-size:16px;margin:30px 0 12px;font-weight:700}
  h2 small{font-weight:500;color:var(--muted);font-size:12px}
  .sub{color:var(--muted);font-size:13px;margin-bottom:8px}
  .goal-banner{background:linear-gradient(90deg,var(--accent),#3b82f6);color:#fff;border-radius:14px;padding:18px 22px;font-size:20px;font-weight:800;margin:10px 0 12px;box-shadow:var(--shadow);line-height:1.45;letter-spacing:-.2px}
  @media(max-width:680px){ .goal-banner{font-size:17px;padding:15px 17px} }
  .datebar{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0;box-shadow:var(--shadow);font-weight:600}
  .datebar select{font:inherit;font-weight:700;color:var(--accent);background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:5px 9px;cursor:pointer}
  h2 small{font-weight:500;color:var(--muted);font-size:12px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;
    box-shadow:var(--shadow);overflow-x:auto}
  .good{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}

  /* 목표 진행 그래프 */
  .goalnum{font-size:15px;color:var(--muted)} .goalnum b{font-size:22px;color:var(--txt)}
  .goalbar{position:relative;height:30px;background:var(--card2);border-radius:8px;overflow:hidden;display:flex;margin:14px 0 12px}
  .goalbar .seg{height:100%}
  .goalbar .cur{background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .goalbar .proj{background:repeating-linear-gradient(45deg,var(--proj),var(--proj) 7px,var(--proj2) 7px,var(--proj2) 14px)}
  .legend{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--muted)}
  .legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:middle}
  .i-cur{background:var(--accent)} .i-proj{background:var(--proj)} .i-rem{background:var(--card2);border:1px solid var(--line)}
  .goalnote{font-size:13px;color:var(--muted);margin-top:10px;border-top:1px dashed var(--line);padding-top:10px}
  .moodrow{display:flex;align-items:center;gap:16px;margin-bottom:12px}
  .mood{font-size:48px;line-height:1}
  .moodmsg{font-weight:700;font-size:16px;margin-bottom:2px}
  @keyframes bob{0%,100%{transform:translateY(0) rotate(-6deg)}50%{transform:translateY(-8px) rotate(6deg)}}
  .mood-dance{display:inline-block;animation:bob .7s ease-in-out infinite}

  .axis{font-size:10px;fill:var(--muted)}
  .empty{color:var(--muted);font-size:13px;padding:10px}

  /* 인사이트 일지 */
  .loghdr{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:10px;font-size:12px;color:var(--muted);
    padding:0 4px 6px;font-weight:600}
  .daygrp{margin-bottom:8px}
  .dayhdr{font-weight:700;color:var(--accent);margin:16px 0 6px;font-size:14px}
  .pt{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:10px;align-items:start;
    padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--card);margin-bottom:8px;box-shadow:var(--shadow)}
  .pt-text{font-size:14px}
  .pt-text .bullet{color:var(--accent);font-weight:700;margin-right:4px}
  .pt textarea{width:100%;min-height:54px;resize:vertical;background:var(--card2);color:var(--txt);
    border:1px solid var(--line);border-radius:8px;padding:7px;font:inherit;font-size:13px}
  .pt textarea:focus{outline:none;border-color:var(--accent);background:#fff}
  .pt .ml{font-size:11px;color:var(--muted);margin-bottom:3px;display:block}
  @media(max-width:680px){
    .loghdr{display:none}
    .pt{grid-template-columns:1fr}
  }

  abbr.gl{text-decoration:none;border-bottom:1px dashed var(--accent);color:var(--accent);cursor:help}
  .tag{display:inline-block;font-size:11px;font-weight:700;padding:1px 8px;border-radius:6px;margin-right:5px;white-space:nowrap}
  .tag-admin{background:#e7f7ee;color:#0f7a43}
  .tag-site{background:#e7effd;color:#1d4ed8}
  .tag-check{background:#fdf3e0;color:#9a6700}
  .tag-warn{background:#fde8e8;color:#c0392b}

  /* 추적 중인 액션 */
  .track-item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px;box-shadow:var(--shadow)}
  .track-item.stopflag{border-color:var(--good);background:#f4fbf7}
  .track-ins{font-size:13px;color:var(--muted)}
  .track-pe{font-size:14px;margin:7px 0}
  .track-pe b{color:var(--txt)}
  .track-verdict{font-size:14px;font-weight:700;margin-top:4px}
  .badge{display:inline-block;font-size:11px;padding:2px 9px;border-radius:20px;background:#e7f7ee;color:var(--good);margin-left:8px;font-weight:600}
  .stopbtn{background:transparent;border:1px solid var(--line);color:var(--muted);padding:5px 12px;font-size:12px;font-weight:600;float:right}
  .empty2{color:var(--muted);font-size:13px;padding:14px;background:var(--card);border:1px dashed var(--line);border-radius:12px}

  /* 충족률 진단 */
  .diagblock{margin-bottom:16px}
  .diagttl{font-weight:700;font-size:13px;margin-bottom:6px}
  .diagtbl{width:100%;border-collapse:collapse;font-size:13px;min-width:420px}
  .diagtbl th{text-align:right;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:5px 7px}
  .diagtbl th:first-child,.diagtbl td:first-child{text-align:left}
  .diagtbl td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:right}
  .cov-bad{color:var(--bad);font-weight:700}
  .cov-mid{color:var(--warn);font-weight:600}
  .cov-good{color:var(--good);font-weight:600}

  .toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 4px}
  button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer;font-weight:600}
  .saved{color:var(--good);font-size:12px;opacity:0;transition:opacity .3s}
  .hint{font-size:12px;color:var(--muted)}
  .qcard textarea{width:100%;min-height:60px;resize:vertical;background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;font-size:13px;margin:8px 0}
  .qrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .qrow input{flex:0 0 140px;background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:7px;font:inherit;font-size:13px}
  .qbtn{background:transparent;border:1px solid var(--line);color:var(--muted);border-radius:6px;padding:2px 7px;font-size:12px;cursor:pointer;margin-left:6px}
  .qbtn:hover{border-color:var(--accent);color:var(--accent)}

  /* 인사이트 체크리스트 */
  .ins{display:flex;align-items:flex-start;gap:10px;justify-content:space-between;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--card);margin-bottom:7px;box-shadow:var(--shadow);cursor:pointer;transition:border-color .15s}
  .ins:hover{border-color:var(--accent)}
  .ins-text{font-size:14px;flex:1}
  .ins-text .bullet{color:var(--accent);font-weight:700;margin-right:5px}
  .ins-status{flex:0 0 auto;white-space:nowrap;font-size:12px;align-self:center}
  .b-track{background:#fde8e8;color:#c0392b;font-weight:700;border-radius:20px;padding:4px 10px}
  .b-add{color:var(--muted);border:1px dashed var(--line);border-radius:20px;padding:4px 10px}
  /* 모달 */
  .modal-ov{position:fixed;inset:0;background:rgba(16,24,40,.45);display:flex;align-items:center;justify-content:center;padding:16px;z-index:50}
  .modal-box{background:var(--card);border-radius:14px;max-width:560px;width:100%;max-height:88vh;overflow-y:auto;padding:22px;box-shadow:0 12px 44px rgba(0,0,0,.28);position:relative}
  .modal-x{position:absolute;top:12px;right:14px;background:transparent;border:0;color:var(--muted);font-size:18px;cursor:pointer}
  .modal-date{font-size:12px;color:var(--accent);font-weight:700}
  .modal-ins{font-size:15px;font-weight:600;margin:4px 0 12px;line-height:1.55}
  .modal-verdict{font-size:13px;background:var(--card2);border-radius:8px;padding:9px 11px;margin-bottom:12px}
  .modal-box textarea{width:100%;min-height:56px;resize:vertical;background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit;font-size:13px;margin:4px 0 10px}
  .modal-box .ml{font-size:12px;color:var(--muted);font-weight:600}
  .modal-hr{border:0;border-top:1px solid var(--line);margin:14px 0}
  button.ghost{background:transparent;border:1px solid var(--line);color:var(--muted)}

  details.gloss{margin-top:24px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 16px;box-shadow:var(--shadow)}
  details.gloss summary{cursor:pointer;font-weight:700;padding:6px 0}
  details.gloss .row{font-size:13px;padding:6px 0;border-top:1px solid var(--line)}
  details.gloss .t{font-weight:700;color:var(--accent)}
</style>
</head>
<body>
  <h1>📊 동아사이언스닷컴 광고 리포트 일지</h1>
  <div class="goal-banner" id="banner"></div>
  <div class="sub" id="sub"></div>

  <div class="datebar">📅 날짜별 보기: <select id="datesel"></select> <span class="hint" id="datehint"></span></div>

  <h2>🎯 이번 달 목표 <small id="goalday"></small></h2>
  <div class="card" id="goalCard"></div>

  <h2>최근 7일 수익</h2>
  <div class="card" id="weekChart"></div>

  <h2>🔍 충족률 진단 <small>— 부른 광고가 어디서 안 채워지나 (빨강 = 낮음)</small></h2>
  <div class="card" id="diag"></div>

  <h2>📝 인사이트 체크리스트 <small>— 🔴 = 진행 중인 액션 있음 · 인사이트를 클릭하면 계획·실행·질문 입력</small></h2>
  <div id="log"></div>

  <details class="gloss" id="gloss"><summary>📖 용어 사전 (펼치기)</summary></details>

  <h2>💬 질문 / 요청 남기기</h2>
  <div class="card qcard">
    <div class="hint">자동 답변이 아니라, 담당자(광고팀)가 Jandi로 받아 확인 후 답합니다. (특정 인사이트 질문은 그 인사이트를 클릭하세요)</div>
    <textarea id="qbox" placeholder="인사이트와 무관한 일반 질문·요청을 적어주세요..."></textarea>
    <div class="qrow"><input id="qname" placeholder="이름(선택)"><button id="qsend">보내기</button><span class="saved" id="qmsg">접수됐어요 ✅</span></div>
  </div>

  <!-- 인사이트 상세/입력 모달 -->
  <div id="modal" class="modal-ov" style="display:none">
    <div class="modal-box">
      <button class="modal-x" id="mClose">✕</button>
      <div class="modal-date" id="mDate"></div>
      <div class="modal-ins" id="mIns"></div>
      <div class="modal-verdict" id="mVerdict" style="display:none"></div>
      <label class="ml">🧭 계획</label>
      <textarea id="mPlan" placeholder="이 인사이트에 대해 무엇을 할 계획인지..."></textarea>
      <label class="ml">🔧 실행</label>
      <textarea id="mExec" placeholder="언제 무엇을 실행했는지 (날짜 포함 권장: 예 6/24 본문 광고 2개 추가)..."></textarea>
      <div class="qrow"><button id="mSave">💾 저장 (추적 시작)</button><button class="ghost" id="mStop">⏹ 추적 중지</button><span class="saved" id="mSaved">저장됨 ✅</span></div>
      <hr class="modal-hr">
      <label class="ml">💬 이 인사이트에 질문</label>
      <textarea id="mQ" placeholder="궁금한 점을 적으면 담당자(광고팀)에게 전달됩니다..."></textarea>
      <div class="qrow"><input id="mQName" placeholder="이름(선택)"><button id="mQSend">질문 보내기</button><span class="saved" id="mQMsg">전송됨 ✅</span></div>
    </div>
  </div>

<script>
const DATA = /*__DATA__*/;
const SYM = {USD:"$",KRW:"₩",EUR:"€",JPY:"¥",GBP:"£"}[DATA.currency] || (DATA.currency+" ");
const money = v => (typeof v==="number") ? SYM + v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) : "—";
const esc = s => (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

document.getElementById("banner").textContent = DATA.headline || "🎯 이번 달 목표";
document.getElementById("sub").textContent = "마지막 갱신: " + (DATA.generated||"-") + "  ·  통화 " + DATA.currency;

/* ---------- 용어 마우스오버 ---------- */
const GMAP = DATA.glossMap || [];
const GRE = GMAP.length ? new RegExp("(" + GMAP.map(g=>g[0].replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|") + ")","g") : null;
const GDEF = {}; GMAP.forEach(g=>{ if(!(g[0] in GDEF)) GDEF[g[0]]=g[1]; });
function withTips(text){
  const e = esc(text);
  if(!GRE) return e;
  return e.replace(GRE, m => `<abbr class="gl" title="${esc(GDEF[m]||"")}">${m}</abbr>`);
}
function tagify(html){
  return html
    .replace(/\[관리자\]/g, '<span class="tag tag-admin">🟢 관리자</span>')
    .replace(/\[사이트\]/g, '<span class="tag tag-site">🔵 사이트·코드</span>')
    .replace(/\[확인\]/g, '<span class="tag tag-check">🟡 확인</span>')
    .replace(/⚠️\s*경고[:：]?/g, '<span class="tag tag-warn">⚠️ 경고</span>');
}
function richText(text){ return tagify(withTips(text)); }

/* ---------- 목표 진행 그래프 ---------- */
const gc = document.getElementById("goalCard");
function renderGoal(s){
  if(s && s.goal){
  const cur = Math.max(0, Math.min(100, s.progress_pct||0));
  const proj = Math.max(0, Math.min(100, s.projected_pct||0));
  const projExtra = Math.max(0, proj - cur);
  const ok = (s.projected_gap||0) >= 0;
  const projPct = s.projected_pct || 0;
  const vs = (typeof s.vs_lm_same_pct === "number") ? s.vs_lm_same_pct : null;
  const beatLast = vs != null && vs >= 0;

  // 기분 이모지: 목표 80%+ 예상 → 신남, 지난달 넘으면 → 안도, 둘 다 아니면 → 슬픔
  let mood, msg, dance = "";
  if(projPct >= 80){ mood = "🥳"; dance = "mood-dance"; msg = "목표가 손에 잡혀요 — 신나서 춤춰요!"; }
  else if(beatLast){ mood = "😌"; msg = "휴~ 그래도 지난달보다는 앞서 있어요"; }
  else { mood = "😢"; msg = "목표도 지난달도 아직… 분발이 필요해요"; }

  const lastLine = (vs != null)
    ? ` · 지난달 동기 ${money(s.lm_same)} 대비 <b class="${beatLast?'good':'bad'}">${vs>=0?'+':''}${vs.toFixed(1)}%</b>`
    : "";
  const remNote = ok
    ? `이 추세면 목표를 <b class="good">초과</b> 달성할 것으로 보입니다 🎉`
    : `이 추세면 월말 <b>${money(s.projection)}</b>, 목표까지 <b class="warn">${money(s.goal - s.projection)}</b> 부족`;
  gc.innerHTML =
    `<div class="moodrow">
       <div class="mood ${dance}">${mood}</div>
       <div>
         <div class="moodmsg">${msg}</div>
         <div class="goalnum">이번 달 목표 <b>${money(s.goal)}</b>${lastLine}</div>
       </div>
     </div>
     <div class="goalbar">
       <div class="seg cur" style="width:${cur}%"></div>
       <div class="seg proj" style="width:${projExtra}%"></div>
     </div>
     <div class="legend">
       <span><i class="i-cur"></i>지금까지 ${money(s.mtd)} (${cur.toFixed(0)}%)</span>
       <span><i class="i-proj"></i>월말 예상 ${money(s.projection)} (${proj.toFixed(0)}%)</span>
       <span><i class="i-rem"></i>목표 ${money(s.goal)} (100%)</span>
     </div>
     <div class="goalnote">${remNote}${ s.days_left!=null ? ` · 남은 <b>${s.days_left}일</b> 동안 하루 <b>${money(s.needed_daily)}</b> 벌면 목표 도달` : "" }</div>`;
} else {
  gc.innerHTML = `<div class="empty">월 목표가 설정되지 않았습니다. .env 의 MONTHLY_REVENUE_GOAL 을 채우면 진행 그래프가 표시됩니다.</div>`;
}
}

/* ---------- 최근 7일 꺾은선 ---------- */
function lineChart(container, items){
  if(!items.length){ container.innerHTML = `<div class="empty">데이터가 쌓이면 그래프가 표시됩니다.</div>`; return; }
  const W = Math.max(container.clientWidth, 320), H = 240, pad = {l:52,r:18,t:18,b:34};
  const max = Math.max(...items.map(d=>d.value||0), 1);
  const n = items.length;
  const X = i => pad.l + (n===1 ? (W-pad.l-pad.r)/2 : i*(W-pad.l-pad.r)/(n-1));
  const Y = v => H-pad.b - (v/max)*(H-pad.t-pad.b);
  let grid="";
  for(let g=0; g<=3; g++){ const v=max*g/3, yy=Y(v);
    grid += `<line x1="${pad.l}" y1="${yy}" x2="${W-pad.r}" y2="${yy}" stroke="var(--line)"/>`;
    grid += `<text class="axis" x="${pad.l-6}" y="${yy+3}" text-anchor="end">${SYM}${Math.round(v)}</text>`; }
  const poly = items.map((d,i)=>`${X(i)},${Y(d.value||0)}`).join(" ");
  let dots="", xl="";
  items.forEach((d,i)=>{
    dots += `<circle cx="${X(i)}" cy="${Y(d.value||0)}" r="4" fill="var(--accent)"><title>${d.label}: ${money(d.value)}</title></circle>`;
    dots += `<text x="${X(i)}" y="${Y(d.value||0)-9}" text-anchor="middle" font-size="10" fill="var(--muted)">${SYM}${Math.round(d.value||0)}</text>`;
    xl += `<text class="axis" x="${X(i)}" y="${H-pad.b+16}" text-anchor="middle">${d.short}</text>`;
  });
  container.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">${grid}<polyline fill="none" stroke="var(--accent)" stroke-width="2.5" points="${poly}"/>${dots}${xl}</svg>`;
}
lineChart(document.getElementById("weekChart"),
  DATA.days.slice(-7).map(d=>({label:d.date, short:d.date.slice(5), value:d.earnings})));

/* ---------- 서버 저장 헬퍼 ---------- */
const ID2INFO = {};
function flashSaved(){ const m=document.getElementById("savedMsg"); m.style.opacity=1; clearTimeout(window.__st); window.__st=setTimeout(()=>m.style.opacity=0, 900); }
function tval(id, field){ const t=document.querySelector(`textarea[data-id="${id}"][data-field="${field}"]`); return t?t.value:""; }
async function postTrack(payload){
  try{ const r=await fetch("/api/track",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); return r.ok; }
  catch(e){ return false; }  // 로컬 파일로 열었거나 서버 꺼짐
}

/* ---------- 충족률 진단 ---------- */
function covClass(c){ if(typeof c!=="number") return ""; if(c<0.3) return "cov-bad"; if(c<0.6) return "cov-mid"; return "cov-good"; }
function diagTable(title, rows){
  if(!rows || !rows.length) return "";
  const body = rows.slice(0,6).map(r=>{
    const cov = r.coverage;
    const covp = (typeof cov==="number") ? (cov*100).toFixed(0)+"%" : "?";
    return `<tr>
      <td>${esc(r.name||"-")}</td>
      <td>${(r.requests||0).toLocaleString()}</td>
      <td class="${covClass(cov)}">${covp}</td>
      <td>${(r.unfilled||0).toLocaleString()}</td>
      <td>${money(r.earnings)}</td>
    </tr>`;
  }).join("");
  return `<div class="diagblock"><div class="diagttl">${title}</div>
    <table class="diagtbl"><thead><tr><th>구분</th><th>요청</th><th>충족률</th><th>미충족</th><th>수익</th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
}
function renderDiag(D){
  D = D || {};
  const html = diagTable("기기별", D.by_device) + diagTable("국가별 (요청 많은 순)", D.by_country) + diagTable("광고단위별", D.by_ad_unit);
  document.getElementById("diag").innerHTML = html || `<div class="empty">진단 데이터가 아직 없습니다 (다음 수집부터 표시).</div>`;
}

/* ---------- 인사이트 체크리스트 (한 줄씩 + 🔴 배지 + 클릭→모달) ---------- */
const log=document.getElementById("log");
function statusBadge(id){
  const t=(DATA.tracking||{})[id];
  if(t && t.status!=="stopped" && (t.plan||t.exec)){
    return `<span class="b-track">🔴 액션 추적중</span>`;
  }
  return `<span class="b-add">＋ 계획·실행·질문</span>`;
}
function renderLog(){
  log.innerHTML="";
  DATA.days.slice().reverse().forEach(d=>{
    if(!d.points||!d.points.length) return;
    const grp=document.createElement("div"); grp.className="daygrp";
    grp.innerHTML=`<div class="dayhdr">${d.date}</div>`;
    d.points.forEach((p, idx)=>{
      const id=d.date+"#"+idx; ID2INFO[id]={date:d.date, insight:p};
      const row=document.createElement("div"); row.className="ins"; row.dataset.id=id;
      row.innerHTML=`<div class="ins-text"><span class="bullet">•</span>${richText(p)}</div><div class="ins-status">${statusBadge(id)}</div>`;
      row.addEventListener("click", ()=> openModal(id));
      grp.appendChild(row);
    });
    log.appendChild(grp);
  });
  if(!log.children.length) log.innerHTML=`<div class="empty">아직 인사이트가 없습니다. 내일부터 쌓입니다.</div>`;
}
renderLog();

/* ---------- 인사이트 상세/입력 모달 (계획·실행·질문) ---------- */
let MID=null;
const modal=document.getElementById("modal");
function openModal(id){
  MID=id;
  const info=ID2INFO[id]||{}; const t=(DATA.tracking||{})[id]||{};
  document.getElementById("mDate").textContent="["+(info.date||"")+"]";
  document.getElementById("mIns").innerHTML=richText(info.insight||"");
  const v=document.getElementById("mVerdict");
  if(t.verdict){ v.style.display="block"; v.innerHTML="📈 추적 효과: "+esc(t.verdict)+(t.stop_suggested?' <b class="good">(중지 제안)</b>':''); }
  else { v.style.display="none"; }
  document.getElementById("mPlan").value=t.plan||"";
  document.getElementById("mExec").value=t.exec||"";
  document.getElementById("mStop").style.display=(t.status!=="stopped" && (t.plan||t.exec))?"inline-block":"none";
  document.getElementById("mQ").value="";
  document.getElementById("mSaved").style.opacity=0; document.getElementById("mQMsg").style.opacity=0;
  modal.style.display="flex";
}
function closeModal(){ modal.style.display="none"; MID=null; }
document.getElementById("mClose").addEventListener("click", closeModal);
modal.addEventListener("click", e=>{ if(e.target===modal) closeModal(); });
document.getElementById("mSave").addEventListener("click", async ()=>{
  if(!MID) return;
  const info=ID2INFO[MID]||{};
  const plan=document.getElementById("mPlan").value, ex=document.getElementById("mExec").value;
  if(await postJSON("/api/track",{id:MID, date:info.date, insight:info.insight, plan, exec:ex})){
    DATA.tracking[MID]=Object.assign({}, DATA.tracking[MID], {date:info.date, insight:info.insight, plan, exec:ex, status:"active"});
    const m=document.getElementById("mSaved"); m.style.opacity=1; setTimeout(()=>m.style.opacity=0,2000);
    document.getElementById("mStop").style.display=(plan||ex)?"inline-block":"none";
    renderLog();
  } else alert("저장 실패 — 사내망 서버 접속 상태를 확인하세요 (대시보드 파일을 직접 연 경우 동작 안 함).");
});
document.getElementById("mStop").addEventListener("click", async ()=>{
  if(!MID) return;
  if(await postJSON("/api/track",{id:MID, status:"stopped"})){
    if(DATA.tracking[MID]) DATA.tracking[MID].status="stopped";
    renderLog(); closeModal();
  }
});
document.getElementById("mQSend").addEventListener("click", async ()=>{
  if(!MID) return;
  const info=ID2INFO[MID]||{}; const q=document.getElementById("mQ").value.trim(); if(!q) return;
  if(await postJSON("/api/question",{question:q, name:document.getElementById("mQName").value, date:info.date, insight:info.insight})){
    document.getElementById("mQ").value="";
    const m=document.getElementById("mQMsg"); m.textContent="전송됨 ✅ 담당자에게 전달"; m.style.opacity=1; setTimeout(()=>m.style.opacity=0,2500);
  } else alert("전송 실패 — 사내망 서버 접속 상태를 확인하세요.");
});

/* ---------- 날짜별 보기 (목표·진단을 고른 날짜 기준으로) ---------- */
const BYDATE={}; DATA.days.forEach(d=> BYDATE[d.date]=d);
const sel=document.getElementById("datesel");
DATA.days.slice().reverse().forEach(d=> sel.add(new Option(d.date, d.date)));
function showDay(date){
  const d=BYDATE[date]||{};
  renderGoal(d.stats);
  renderDiag(d.diagnostics);
  const g=document.getElementById("goalday"); if(g) g.textContent = date ? "("+date+" 기준)" : "";
}
if(sel){
  sel.addEventListener("change", ()=> showDay(sel.value));
  const dh=document.getElementById("datehint"); if(dh) dh.textContent = "← 과거 날짜를 고르면 그날의 목표·진단을 봅니다 (인사이트는 아래 일지에 날짜별로)";
}
showDay(DATA.days.length ? DATA.days[DATA.days.length-1].date : "");

/* ---------- 질문 접수 (인박스 → Jandi) ---------- */
async function postJSON(path, payload){
  try{ const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); return r.ok; }
  catch(e){ return false; }
}
const qbox=document.getElementById("qbox");
document.getElementById("qsend").addEventListener("click", async ()=>{
  const q=(qbox.value||"").trim(); if(!q){ qbox.focus(); return; }
  const btn=document.getElementById("qsend"); btn.disabled=true;
  const ok=await postJSON("/api/question", {question:q, name:document.getElementById("qname").value, date:(document.getElementById("datesel")||{}).value||"", insight:qbox.dataset.insight||""});
  btn.disabled=false;
  const m=document.getElementById("qmsg");
  if(ok){ qbox.value=""; qbox.dataset.insight=""; m.textContent="접수됐어요 ✅ 담당자가 확인 후 답합니다"; m.style.opacity=1; setTimeout(()=>m.style.opacity=0, 3000); }
  else { alert("전송 실패 — 사내망 서버 접속 상태를 확인하세요. (대시보드 파일을 직접 연 경우 동작하지 않습니다)"); }
});

/* ---------- 용어 사전 (접이식) ---------- */
document.getElementById("gloss").insertAdjacentHTML("beforeend",
  (DATA.glossRef||[]).map(g=>`<div class="row"><span class="t">${g[0]}</span> — ${esc(g[1])}</div>`).join(""));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
