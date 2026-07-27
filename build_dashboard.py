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

# 📅 7월 실행 계획 (WBS · 일별 할 일 + 체크할 데이터). do=할 일, chk=확인할 데이터
PLAN = [
    {"week": "1주차 · 배포·설정 완료(자동광고 7/6, 개발 7/7) → 매일 감시·조정", "days": [
        {"date": "7/7", "label": "✅ 완료 — 자동광고 7/6 · 개발 7/7 반영",
         "do": ["[콘솔·7/6] 자동광고 보수적 재ON (개수·간격 최소) + 모바일 전면광고 30분 간격",
                "[개발·7/7] 본문 인아티클 1개 → 최대 3개(5문단마다) 다중삽입 (배포·코드검증 완료)",
                "[개발·7/7] 고정 360×640 광고 → 반응형 전환 (배포·코드검증 완료)",
                "[개발·7/7] 모바일 기사 상세 배너 깨짐 수정 (배포 완료)"],
         "chk": ["여러 개를 한 번에 켰으니 → 이제 '도배 안 나나'와 '무엇이 효과였나'가 핵심"]},
        {"date": "7/3", "label": "7/2~7/6 · 매일 감시 (도배·이탈 방어)",
         "do": ["⚠️ 수동 본문광고 + 자동광고가 겹쳐 도배(>30%) 안 나는지 실제 모바일로 매일 확인",
                "이탈률 오르면 → 자동광고 개수 더 낮추거나 전면광고 간격 늘리기 (수동 3개는 유지)"],
         "chk": ["수익↑ 와 이탈률 유지가 '동시에' 되나 (매일)"]},
    ]},
    {"week": "2주차 (7/7~7/11) · 무엇이 효과였는지 가려내기 + 과한 것 덜기", "days": [
        {"date": "7/7", "label": "7/7~7/9 · 원인 분리",
         "do": ["한꺼번에 켜서 원인이 섞임 → 이탈률이 나쁘면 하나씩 꺼보며 범인 찾기",
                "잘 되면 유지, 과하면(특히 자동광고·전면광고) 덜어내기"],
         "chk": ["어떤 조합이 수익↑ & 이탈률 유지인가"]},
        {"date": "7/10", "label": "7/10~7/11 · 1차 효과 판정",
         "do": ["대시보드 추적에서 7/1 액션들의 효과 판정 확인"],
         "chk": ["7/1 대비 일수익·이탈률 변화 / 목표 페이스"]},
    ]},
    {"week": "3주차 (7/14~7/18) · 최적 설정 찾기 (판정 기준: 방문당 수익)", "days": [
        {"date": "7/14", "label": "7/14~7/16 · 한 번에 하나씩 바꿔 비교",
         "do": ["설정을 한 번에 '하나만' 바꾼다 (예: 본문 광고 3개→2개) → 3~5일 관찰",
                "판정은 '총수익'이 아니라 '방문당 수익(1,000명당)'으로 — 트래픽 영향 제거",
                "(여유 있으면) PC 인아티클도 본문 2곳으로 확대해 같은 방식으로 비교"],
         "chk": ["방문당 수익이 오르면서 이탈률은 안 오르는 설정이 '이긴' 것"],
         "notelabel": "📏 '가장 잘 나온 설정' 판정하는 법 (펼치기)",
         "note": (
            "<b>📏 '가장 잘 나온 설정'을 판정하는 법</b> (안 그러면 트래픽에 속아요)<br><br>"
            "· <b>기준 지표</b>: 총수익(❌) → <b>방문당 수익(⭕)</b>. 매일 방문자 수가 달라서 총수익으론 설정 효과를 못 가림.<br>"
            "· <b>방법</b>: 한 번에 하나만 바꾸고 <b>3~5일</b> 관찰 → 바꾸기 전후 방문당 수익 비교.<br>"
            "· <b>승리 조건</b>: <b>이탈률 안 오르면서 방문당 수익이 오른</b> 설정 = 채택.<br>"
            "· <b>자동광고</b>: AdSense <b>'실험(Experiments)'</b> 기능으로 A/B — 트래픽 절반씩 나눠 구글이 승자를 알려줌.<br><br>"
            "→ 대시보드 '독자 반응' 카드의 <b>방문당 수익</b> 숫자를 보면 돼요."
         )},
        {"date": "7/17", "label": "7/17~7/18 · 최적 설정 고정",
         "do": ["방문당 수익 최대 + 이탈률 유지였던 설정을 확정·고정",
                "자동광고는 실험(Experiments) A/B 승자 확인 후 반영"],
         "chk": ["고정 후 방문당 수익·이탈률이 안정적으로 유지되는가"]},
    ]},
    {"week": "4주차 (7/21~7/30) · 굳히기 + 결산", "days": [
        {"date": "7/21", "label": "7/21~7/25 · 안정화",
         "do": ["방문당 수익 최대였던 설정 고정 · 매일 방문당 수익·이탈률 이상치만 감시"],
         "chk": ["방문당 수익·목표 페이스 유지되나"]},
        {"date": "7/28", "label": "7/28~7/30 · 월말 결산",
         "do": ["목표 $2,850 대비 결산", "8월 계획 수립 (축 = 트래픽 확대)"],
         "chk": ["월 수익 vs 목표 · 다음 달 레버는?"]},
    ]},
]


def load_days():
    days = []
    for f in sorted(common.DATA_DIR.glob("20[0-9][0-9]-[0-1][0-9]-[0-3][0-9].json")):
        rec = common.load_json(f)
        if not rec or "date" not in rec:
            continue
        t = (rec.get("adsense") or {}).get("total", {}) or {}
        ga = (rec.get("ga4") or {}).get("total", {}) or {}
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
            "reader": {
                "bounce": ga.get("bounce_rate"),
                "dur": ga.get("avg_session_duration"),
                "sessions": ga.get("sessions"),
            },
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
        "readOnly": str(common.env("DASHBOARD_READONLY", "")).lower() in ("1", "true", "yes"),
        "generated": days[-1]["date"] if days else "",
        "currency": currency,
        "stats": stats,
        "days": days,
        "journal": journal_seed,
        "tracking": tracking,
        "diagnostics": diagnostics,
        "glossRef": gloss_ref,
        "glossMap": gloss_map,
        "plan": PLAN,
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
  .report-link{display:inline-block;margin:6px 0 4px;padding:9px 16px;background:linear-gradient(90deg,#6d3bf0,#8b5cf6);color:#fff;font-weight:800;border-radius:10px;text-decoration:none;box-shadow:var(--shadow)}
  .report-link:hover{filter:brightness(1.07)}
  .datebar{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0;box-shadow:var(--shadow);font-weight:600}
  .datebar select{font:inherit;font-weight:700;color:var(--accent);background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:5px 9px;cursor:pointer}
  h2 small{font-weight:500;color:var(--muted);font-size:12px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;
    box-shadow:var(--shadow);overflow-x:auto}
  .good{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}

  /* 📅 실행 계획 (WBS 체크리스트) */
  .plan-prog{font-size:13px;color:var(--muted);margin:0 0 12px}
  .plan-prog b{color:var(--accent);font-size:15px}
  .plan-week{margin:16px 0 6px;font-weight:800;font-size:14px;color:var(--txt);
    padding:7px 12px;background:var(--card2);border-radius:9px;border-left:4px solid var(--accent)}
  .plan-day{border:1px solid var(--line);border-radius:11px;padding:12px 14px;margin:8px 0;background:var(--card)}
  .plan-day.today{border-color:var(--accent);box-shadow:0 0 0 2px rgba(37,99,235,.15);background:#f5f8ff}
  .plan-day.done{opacity:.6}
  .plan-dhead{display:flex;align-items:center;gap:8px;font-weight:800;font-size:14px;margin-bottom:8px}
  .plan-today-chip{background:var(--accent);color:#fff;font-size:11px;font-weight:800;border-radius:20px;padding:2px 9px}
  .plan-task{display:flex;align-items:flex-start;gap:9px;padding:5px 0;cursor:pointer;font-size:14px;line-height:1.45}
  .plan-task input{margin-top:3px;width:17px;height:17px;flex:none;cursor:pointer;accent-color:var(--accent)}
  .plan-task.checked span{text-decoration:line-through;color:var(--muted)}
  .plan-chk{margin-top:7px;padding-top:7px;border-top:1px dashed var(--line)}
  .plan-chk .lbl{font-size:11px;font-weight:800;color:var(--warn);letter-spacing:.3px}
  .plan-chk div{font-size:13px;color:var(--muted);padding:2px 0}
  .plan-note{margin-top:9px}
  .plan-note summary{cursor:pointer;font-size:12px;font-weight:800;color:var(--accent);
    background:#eef4ff;border:1px solid #cfe0ff;border-radius:8px;padding:7px 11px;list-style:none;display:inline-block}
  .plan-note summary::-webkit-details-marker{display:none}
  .plan-note summary::before{content:"▸ ";}
  .plan-note[open] summary::before{content:"▾ ";}
  .plan-note-body{font-size:13px;line-height:1.65;color:var(--txt);margin-top:9px;
    background:var(--card2);border-radius:10px;padding:13px 15px}
  .plan-note-body code{background:#fff;border:1px solid var(--line);border-radius:5px;
    padding:1px 5px;font-size:12px;font-family:ui-monospace,Consolas,monospace;color:#b3005e}
  .plan-note-body u{text-decoration:none;font-weight:800;color:var(--accent)}

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

  /* 독자 반응 */
  .reader-row{display:flex;gap:26px;flex-wrap:wrap}
  .reader-stat .rl{font-size:12px;color:var(--muted);margin-bottom:2px}
  .reader-stat .rv{font-size:24px;font-weight:800}
  .reader-note{font-size:13px;margin-top:10px;border-top:1px dashed var(--line);padding-top:10px}
  .prio{display:inline-block;font-size:10px;font-weight:800;padding:2px 8px;border-radius:20px;margin-right:6px;white-space:nowrap}
  .prio-warn{background:#fde8e8;color:#c0392b} .prio-admin{background:#e7f7ee;color:#0f7a43}
  .prio-site{background:#e7effd;color:#1d4ed8} .prio-check{background:#fdf3e0;color:#9a6700}
  .prio-info{background:var(--card2);color:var(--muted)}
  .ins-date{font-size:11px;color:var(--muted);margin-left:8px;white-space:nowrap}

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

  <a class="report-link" href="광고수익_성과보고_2주.html" target="_blank">📊 2주 성과보고 발표자료 열기 →</a>
  <a class="report-link" href="광고수익_원페이지.html" target="_blank" style="margin-left:8px">📈 월간 광고수익 리포트 (원페이지) →</a>

  <div class="datebar">📅 날짜별 보기: <select id="datesel"></select> <span class="hint" id="datehint"></span></div>

  <h2>🎯 이번 달 목표 <small id="goalday"></small></h2>
  <div class="card" id="goalCard"></div>

  <h2>📅 7월 실행 계획 <small>— 오늘 할 일 · 확인할 데이터 (체크하면 저장됨)</small></h2>
  <div class="card" id="planCard"></div>

  <h2>✅ 진행 중인 액션 <small>— 실행한 조치와 효과 (데이터로 자동 판정)</small></h2>
  <div id="trackCard"></div>

  <h2>최근 7일 수익</h2>
  <div class="card" id="weekChart"></div>

  <h2>🙂 독자 반응 <small>— 광고가 독자를 쫓아내지 않는지 (매일 체크)</small></h2>
  <div class="card" id="readerCard"></div>

  <h2>📝 해볼 만한 것 <small>— 우선순위 순 (⚠️경고·🟢바로·🔵개발·🟡확인) · 클릭하면 계획·실행·질문</small></h2>
  <div id="log"></div>
  <details class="gloss" id="infofold"><summary>📋 데이터 진단·참고 (펼치기)</summary><div id="infolog" style="margin-top:8px"></div></details>

  <details class="gloss" id="diagfold"><summary>🔍 충족률 진단 (펼치기) — 수익이 흔들리거나 원인 팔 때만</summary>
    <div class="card" id="diag" style="margin-top:10px;box-shadow:none;border:none"></div>
  </details>

  <details class="gloss" id="gloss"><summary>📖 용어 사전 (펼치기)</summary></details>

  <h2>💬 질문 / 요청 남기기</h2>
  <div class="card qcard">
    <div class="hint">자동 답변이 아니라, 담당자(서비스기획팀)가 Jandi로 받아 확인 후 답합니다. (특정 인사이트 질문은 그 인사이트를 클릭하세요)</div>
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
      <div id="mRoNote" class="hint" style="display:none">👁 보기 전용 — 편집/질문은 사내 서버 대시보드에서</div>
      <label class="ml">🧭 계획</label>
      <textarea id="mPlan" placeholder="이 인사이트에 대해 무엇을 할 계획인지..."></textarea>
      <label class="ml">🔧 실행</label>
      <textarea id="mExec" placeholder="언제 무엇을 실행했는지 (날짜 포함 권장: 예 6/24 본문 광고 2개 추가)..."></textarea>
      <div class="qrow" id="mSaveRow"><button id="mSave">💾 저장 (추적 시작)</button><button class="ghost" id="mStop">⏹ 추적 중지</button><span class="saved" id="mSaved">저장됨 ✅</span></div>
      <div id="mAsk">
        <hr class="modal-hr">
        <label class="ml">💬 이 인사이트에 질문</label>
        <textarea id="mQ" placeholder="궁금한 점을 적으면 담당자(서비스기획팀)에게 전달됩니다..."></textarea>
        <div class="qrow"><input id="mQName" placeholder="이름(선택)"><button id="mQSend">질문 보내기</button><span class="saved" id="mQMsg">전송됨 ✅</span></div>
      </div>
    </div>
  </div>

<script>
const DATA = /*__DATA__*/;
const SYM = {USD:"$",KRW:"₩",EUR:"€",JPY:"¥",GBP:"£"}[DATA.currency] || (DATA.currency+" ");
const money = v => (typeof v==="number") ? SYM + v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) : "—";
const esc = s => (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

document.getElementById("banner").textContent = DATA.headline || "🎯 이번 달 목표";
document.getElementById("sub").textContent = "마지막 갱신: " + (DATA.generated||"-") + "  ·  통화 " + DATA.currency + (DATA.readOnly ? "  ·  👁 보기 전용" : "");
if(DATA.readOnly){ const qc=document.querySelector(".qcard"); if(qc) qc.style.display="none"; }

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

  // 기분 이모지: 새 달 시작 → 출발, 목표 80%+ 예상 → 신남, 지난달 넘으면 → 안도, 둘 다 아니면 → 슬픔
  let mood, msg, dance = "";
  if(s.fresh){ mood = "🚀"; msg = "새 달 시작! 목표를 향해 0부터 달려요"; }
  else if(projPct >= 80){ mood = "🥳"; dance = "mood-dance"; msg = "목표가 손에 잡혀요 — 신나서 춤춰요!"; }
  else if(beatLast){ mood = "😌"; msg = "휴~ 그래도 지난달보다는 앞서 있어요"; }
  else { mood = "😢"; msg = "목표도 지난달도 아직… 분발이 필요해요"; }

  const lastLine = (vs != null)
    ? ` · 지난달 동기 ${money(s.lm_same)} 대비 <b class="${beatLast?'good':'bad'}">${vs>=0?'+':''}${vs.toFixed(1)}%</b>`
    : "";
  const remNote = s.fresh
    ? `아직 이번 달 집계 데이터가 없어요 — <b>내일부터</b> 채워집니다`
    : ok
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

/* ---------- 독자 반응 (광고가 독자를 쫓아내는지) ---------- */
function renderReader(r, earnings){
  const box=document.getElementById("readerCard");
  if(!r || (r.bounce==null && r.dur==null)){ box.innerHTML=`<div class="empty">독자 데이터 없음</div>`; return; }
  const b=r.bounce, dur=r.dur, ses=r.sessions;
  const rpm = (typeof earnings==="number" && typeof ses==="number" && ses>0) ? earnings/ses*1000 : null;
  const bClass = (typeof b==="number") ? (b<60?"good":(b<80?"warn":"bad")) : "";
  let note;
  if(typeof b!=="number") note="데이터가 쌓이면 판단할 수 있어요.";
  else if(b<60) note="✅ 이탈률 낮음 — 광고가 독자를 쫓아내는 신호 없음.";
  else if(b<80) note="🟡 이탈률 보통 — 광고 늘릴 때 이 수치가 오르는지 지켜보세요.";
  else note="🟡 이탈률 높음 — 뉴스 특성상 높을 수 있어요. 중요한 건 '광고 바꾼 뒤 더 오르는지'예요.";
  box.innerHTML = `<div class="reader-row">
    <div class="reader-stat"><div class="rl">방문당 수익 <span style="font-weight:400;font-size:11px">(1,000명당)</span></div><div class="rv good">${rpm!=null?money(rpm):"—"}</div></div>
    <div class="reader-stat"><div class="rl">이탈률</div><div class="rv ${bClass}">${typeof b==="number"?b.toFixed(0)+"%":"—"}</div></div>
    <div class="reader-stat"><div class="rl">평균 참여시간</div><div class="rv">${typeof dur==="number"?Math.round(dur)+"s":"—"}</div></div>
    <div class="reader-stat"><div class="rl">세션</div><div class="rv">${typeof ses==="number"?Math.round(ses).toLocaleString():"—"}</div></div>
  </div>
  <div class="reader-note" style="color:var(--muted)">${note}</div>
  <div class="reader-note" style="color:var(--muted);margin-top:6px">💡 <b>방문당 수익</b> = 트래픽과 무관한 '광고 효율' 지표. 설정을 바꿨을 때 <b>이 값이 오르고 이탈률은 안 오르면</b> = 더 좋은 설정이에요. (총수익은 트래픽에 휘둘려서 설정 판단엔 부적합)</div>`;
}

/* ---------- 인사이트: 해볼 만한 것 우선순위 순 (중복 최신만) ---------- */
const log=document.getElementById("log");
const PRIO_META = {0:["prio-warn","⚠️ 경고"],1:["prio-admin","🟢 바로 할 것"],2:["prio-site","🔵 개발 필요"],3:["prio-check","🟡 확인"],4:["prio-info","참고"]};
function insightPriority(p){
  if(/⚠️|경고/.test(p)) return 0;
  if(p.includes("[관리자]")) return 1;
  if(p.includes("[사이트]")) return 2;
  if(p.includes("[확인]")) return 3;
  return 4;
}
function stripTag(t){ return t.replace(/^\s*(\[관리자\]|\[사이트\]|\[확인\])\s*/,"").replace(/^\s*⚠️\s*경고[:：]?\s*/,""); }
function iwords(s){ return new Set((s.toLowerCase().match(/[가-힣a-z0-9]+/g)||[])); }
function isimilar(a,b){ const A=iwords(a),B=iwords(b); if(!A.size||!B.size) return false; let x=0; A.forEach(w=>{if(B.has(w))x++;}); const u=new Set([...A,...B]).size; return x/u>=0.5; }
function statusBadge(id){
  const t=(DATA.tracking||{})[id];
  if(t && t.status!=="stopped" && (t.plan||t.exec)){
    return `<span class="b-track">🔴 액션 추적중</span>`;
  }
  return `<span class="b-add">＋ 계획·실행·질문</span>`;
}
function makeRow(it){
  ID2INFO[it.id]={date:it.date, insight:it.text};
  const m=PRIO_META[it.prio];
  const row=document.createElement("div"); row.className="ins"; row.dataset.id=it.id;
  row.innerHTML=`<div class="ins-text"><span class="prio ${m[0]}">${m[1]}</span>${richText(stripTag(it.text))}<span class="ins-date">${it.date.slice(5)}</span></div><div class="ins-status">${statusBadge(it.id)}</div>`;
  row.addEventListener("click", ()=> openModal(it.id));
  return row;
}
function renderLog(){
  log.innerHTML="";
  const infolog=document.getElementById("infolog"); if(infolog) infolog.innerHTML="";
  const all=[];
  DATA.days.slice().reverse().forEach(d=>{ (d.points||[]).forEach((p,idx)=>{ all.push({date:d.date, id:d.date+"#"+idx, text:p, prio:insightPriority(p)}); }); });
  const kept=[]; all.forEach(it=>{ if(!kept.some(k=>isimilar(k.text,it.text))) kept.push(it); });  // 중복 제거(최신 유지)
  const warns   = kept.filter(x=>x.prio===0).slice(0,3);                 // 최근 경고 3개만
  const actions = kept.filter(x=>x.prio>=1 && x.prio<=3).sort((a,b)=>a.prio-b.prio);  // 해볼 만한 것
  const info    = kept.filter(x=>x.prio===4);                            // 진단·참고
  [...warns, ...actions].forEach(it=> log.appendChild(makeRow(it)));
  if(!log.children.length) log.innerHTML=`<div class="empty">지금 바로 해볼 액션이 없어요. 데이터가 쌓이면 표시됩니다.</div>`;
  if(infolog) info.forEach(it=> infolog.appendChild(makeRow(it)));
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
  // 보기 전용(정적 호스팅)일 땐 편집/질문 숨김
  const ro=!!DATA.readOnly;
  document.getElementById("mRoNote").style.display=ro?"block":"none";
  document.getElementById("mPlan").readOnly=ro; document.getElementById("mExec").readOnly=ro;
  document.getElementById("mSaveRow").style.display=ro?"none":"flex";
  document.getElementById("mAsk").style.display=ro?"none":"block";
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

/* ---------- 📅 실행 계획 (WBS 체크리스트) ---------- */
const PLAN = DATA.plan || [];
const PLAN_KEY = "ds_plan_checks_v1";
function planState(){ try{ return JSON.parse(localStorage.getItem(PLAN_KEY)||"{}"); }catch(e){ return {}; } }
function planSave(st){ try{ localStorage.setItem(PLAN_KEY, JSON.stringify(st)); }catch(e){} }
function todayMD(){ const t=new Date(); return (t.getMonth()+1)+"/"+t.getDate(); }
function renderPlan(){
  const box=document.getElementById("planCard"); if(!box) return;
  const st=planState(); const today=todayMD();
  let total=0, done=0;
  let html="";
  PLAN.forEach((wk, wi)=>{
    html += '<div class="plan-week">'+esc(wk.week)+'</div>';
    (wk.days||[]).forEach((day, di)=>{
      const tasks=day.do||[]; const checks=day.chk||[];
      let dchecked=0;
      const isToday = day.date===today;
      let tHtml="";
      tasks.forEach((t, ti)=>{
        const id="w"+wi+"d"+di+"t"+ti; total++;
        const on=!!st[id]; if(on){ done++; dchecked++; }
        tHtml += '<label class="plan-task'+(on?' checked':'')+'"><input type="checkbox" data-id="'+id+'"'+(on?' checked':'')+'><span>'+richText(t)+'</span></label>';
      });
      let cHtml="";
      if(checks.length){
        cHtml = '<div class="plan-chk"><span class="lbl">📊 확인할 데이터</span>'+
          checks.map(c=>'<div>· '+richText(c)+'</div>').join("")+'</div>';
      }
      let nHtml="";
      if(day.note){
        const nlabel = day.notelabel || "📩 개발 요청서 보기 (개발팀 전달용)";
        nHtml = '<details class="plan-note"><summary>'+esc(nlabel)+'</summary>'+
          '<div class="plan-note-body">'+day.note+'</div></details>';
      }
      const allDone = tasks.length && dchecked===tasks.length;
      html += '<div class="plan-day'+(isToday?' today':'')+(allDone?' done':'')+'">'+
        '<div class="plan-dhead">'+esc(day.label||day.date)+
        (isToday?' <span class="plan-today-chip">오늘</span>':'')+'</div>'+
        tHtml + cHtml + nHtml + '</div>';
    });
  });
  const pct = total ? Math.round(done/total*100) : 0;
  const prog = '<div class="plan-prog">전체 진행 <b>'+done+'/'+total+'</b> ('+pct+'%) · 오늘 날짜는 파란 테두리로 표시돼요</div>';
  box.innerHTML = prog + html;
  box.querySelectorAll('input[type=checkbox]').forEach(cb=>{
    cb.addEventListener("change", ()=>{
      const s=planState(); if(cb.checked) s[cb.dataset.id]=1; else delete s[cb.dataset.id];
      planSave(s); renderPlan();
    });
  });
}
renderPlan();

/* ---------- ✅ 진행 중인 액션 (tracking.json 직접 렌더) ---------- */
function renderTracking(){
  const box=document.getElementById("trackCard"); if(!box) return;
  const all=Object.entries(DATA.tracking||{})
    .filter(([id,t])=> t && t.status!=="stopped" && (t.plan||t.exec))
    .sort((a,b)=> String(b[1].date||"").localeCompare(String(a[1].date||"")) || String(a[0]).localeCompare(String(b[0])));
  function card([id,t]){
    let sig;
    if(t.stop_suggested) sig='<span class="good">🟩 효과 확인</span>';
    else if(t.verdict) sig='⬜ 관찰 중';
    else if(t.exec) sig='⏳ 효과 집계 대기';
    else sig='⏳ 실행 대기';
    const verd = t.verdict
      ? `<div class="track-verdict">📈 ${richText(t.verdict)}${t.stop_suggested?' <b class="good">(중지 제안)</b>':''}</div>` : "";
    const execLine = t.exec ? `<div class="track-pe"><b>실행</b> ${richText(t.exec)}</div>` : "";
    return `<div class="track-item${t.stop_suggested?' stopflag':''}">
       <div class="track-ins">📅 ${esc(t.date||"")} · <b>${sig}</b></div>
       <div class="track-pe" style="font-weight:600">${richText(t.insight||"")}</div>
       ${execLine}${verd}</div>`;
  }
  const done=all.filter(([id,t])=>t.stop_suggested);                 // 효과 확인 → 접기
  const rest=all.filter(([id,t])=>!t.stop_suggested);
  const ongoing=rest.filter(([id,t])=>t.exec);                       // 실행됨·지켜보는 중 = 메인
  const pending=rest.filter(([id,t])=>!t.exec);                      // 미실행 계획 → 접기
  let html = ongoing.length ? ongoing.map(card).join("")
    : '<div class="empty">지금 지켜보는 중인 액션이 없어요.</div>';
  if(pending.length){
    html += `<details class="gloss" style="margin-top:10px"><summary>⏳ 미실행 계획 ${pending.length}건 (검토 필요 · 펼치기)</summary>`
          + `<div style="margin-top:10px">${pending.map(card).join("")}</div></details>`;
  }
  if(done.length){
    html += `<details class="gloss" style="margin-top:10px"><summary>✅ 효과 확인 완료 ${done.length}건 (펼치기)</summary>`
          + `<div style="margin-top:10px">${done.map(card).join("")}</div></details>`;
  }
  box.innerHTML = html;
}
renderTracking();

/* ---------- 새 달 감지: 데이터는 지난달인데 오늘이 새 달이면 목표를 0부터 리셋 ---------- */
function freshMonthStats(goal){
  const now=new Date();
  const y=now.getFullYear(), mo=now.getMonth()+1, day=now.getDate();
  const dim=new Date(y, mo, 0).getDate();          // 이번 달 총 일수
  const daysLeft=Math.max(0, dim-day);             // 오늘 이후 남은 일수
  return { fresh:true, goal:goal, mtd:0, progress_pct:0,
    projection:0, projected_pct:0, projected_gap: (goal!=null? -goal : 0),
    vs_lm_same_pct:null, lm_same:null,
    days_elapsed:day, days_in_month:dim, days_left:daysLeft,
    needed_daily: (goal!=null && daysLeft>0) ? goal/daysLeft : 0 };
}
const GEN_MONTH=(DATA.generated||"").slice(0,7);   // 최신 데이터의 연-월 (예: 2026-06)
const _now=new Date();
const CUR_MONTH=_now.getFullYear()+"-"+String(_now.getMonth()+1).padStart(2,"0");
const NEW_MONTH = !!GEN_MONTH && CUR_MONTH > GEN_MONTH;   // 새 달로 넘어왔고 아직 데이터 없음
const GOAL_VAL = (DATA.stats && DATA.stats.goal!=null) ? DATA.stats.goal : null;
const FRESH_STATS = NEW_MONTH ? freshMonthStats(GOAL_VAL) : null;

/* ---------- 날짜별 보기 (목표·진단을 고른 날짜 기준으로) ---------- */
const BYDATE={}; DATA.days.forEach(d=> BYDATE[d.date]=d);
const sel=document.getElementById("datesel");
DATA.days.slice().reverse().forEach(d=> sel.add(new Option(d.date, d.date)));
function showDay(date){
  const d=BYDATE[date]||{};
  renderGoal(NEW_MONTH ? FRESH_STATS : d.stats);   // 새 달이면 목표는 항상 0부터
  renderReader(d.reader, d.earnings);
  renderDiag(d.diagnostics);
  const g=document.getElementById("goalday");
  if(g) g.textContent = NEW_MONTH ? "("+CUR_MONTH.replace("-","년 ")+"월 · 새 달 시작)" : (date ? "("+date+" 기준)" : "");
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
