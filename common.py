"""공통 유틸 — 환경변수 로딩, 경로, 날짜, JSON 저장/로딩, 변화율 계산."""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Windows 콘솔 기본 인코딩(cp949)에서 한글/이모지 print 가 깨지거나 죽는 것 방지.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# OAuth/서비스 계정 스코프
ADSENSE_SCOPES = ["https://www.googleapis.com/auth/adsense.readonly"]
GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

TOKEN_ADSENSE = BASE_DIR / "token_adsense.json"


def env(key, default=None, required=False):
    val = os.getenv(key, default)
    if required and not val:
        raise SystemExit(f"[설정오류] 환경변수 {key} 가 .env 에 없습니다.")
    return val


def yesterday():
    """어제 날짜 (로컬 기준). AdSense/GA4 모두 어제 데이터를 수집한다."""
    return date.today() - timedelta(days=1)


def daily_path(d):
    return DATA_DIR / f"{d.isoformat()}.json"


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_history(before_date, days=30):
    """before_date 이전(미포함) days일 구간의 일별 레코드를 날짜순으로 반환.

    개수 기준(records[-days:])이 아니라 날짜 구간 기준이다. 결측일이 있으면
    7일 구간의 레코드가 6개일 수 있고, 그게 정확한 동작이다.
    """
    cutoff = before_date - timedelta(days=days)
    records = []
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            d = datetime.strptime(f.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if cutoff <= d < before_date:
            rec = load_json(f)
            if rec:
                records.append(rec)
    return records


def pct_change(current, baseline):
    """변화율(%) — baseline 이 0 이면 None."""
    if baseline in (None, 0):
        return None
    return (current - baseline) / baseline * 100.0


def fmt_pct(value, signed=True, digits=1):
    if value is None:
        return "N/A"
    sign = "+" if (signed and value >= 0) else ""
    return f"{sign}{value:.{digits}f}%"
