"""과거 GA4 데이터 백필 — 지정한 날짜 구간을 확정본으로 재수집해 일별 레코드를 치유.

collect_ga4 의 자기 치유는 D-2~D-5 만 고친다. 그보다 오래된 날짜에 잘못 저장된
값(예: 확정 전 수집으로 이탈률 99%)은 이 스크립트로 구간을 지정해 다시 받는다.
GA4 는 한 번 확정되면 재조회해도 값이 같으므로 여러 번 실행해도 안전하다.

사용법:
  python backfill_ga4.py 2026-06-22 2026-07-24
  (또는 환경변수 BACKFILL_START / BACKFILL_END)

- raw/ga4-YYYY-MM-DD.json 을 새로 쓰고, data/YYYY-MM-DD.json 의 ga4 키만 교체한다.
- AdSense 수치(수익 금액)는 절대 건드리지 않는다 — analyze.refresh_ga4_in_records 와 동일 원칙.
- 종료일은 D-2 까지만 허용한다(그 이후는 아직 미확정, collect_ga4 SETTLE_DAYS 참고).
"""
import os
import sys
from datetime import date, timedelta

import collect_ga4
import common


def _parse_date(s, label):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise SystemExit(f"[백필] {label} 날짜 형식 오류: {s!r} (YYYY-MM-DD)")


def main():
    start_s = os.getenv("BACKFILL_START") or (sys.argv[1] if len(sys.argv) > 1 else None)
    end_s = os.getenv("BACKFILL_END") or (sys.argv[2] if len(sys.argv) > 2 else None)
    if not start_s or not end_s:
        raise SystemExit("[백필] 시작/종료 날짜가 필요합니다: python backfill_ga4.py 2026-06-22 2026-07-24")

    start = _parse_date(start_s, "시작")
    end = _parse_date(end_s, "종료")
    if start > end:
        raise SystemExit(f"[백필] 시작({start})이 종료({end})보다 늦습니다.")

    settled_limit = date.today() - timedelta(days=collect_ga4.SETTLE_DAYS)
    if end > settled_limit:
        print(f"[백필] 종료일을 확정 한계 {settled_limit} 로 당깁니다 (D-2 이후는 미확정).")
        end = settled_limit

    property_id = common.env("GA4_PROPERTY_ID", required=True)

    total = (end - start).days + 1
    healed, skipped, failed = [], [], []
    for off in range(total):
        d = start + timedelta(days=off)
        try:
            data = collect_ga4.fetch(property_id, d)
        except Exception as e:  # noqa: BLE001
            print(f"[백필] {d} 수집 실패 (건너뜀): {str(e)[:120]}")
            failed.append(d.isoformat())
            continue

        common.save_json(common.RAW_DIR / f"ga4-{d.isoformat()}.json", {"date": d.isoformat(), "ga4": data})

        rec = common.load_json(common.daily_path(d))
        if not rec:
            print(f"[백필] {d} 일별 레코드 없음 — raw 만 저장")
            skipped.append(d.isoformat())
            continue

        old_br = (rec.get("ga4") or {}).get("total", {}).get("bounce_rate")
        new_br = data.get("total", {}).get("bounce_rate")
        rec["ga4"] = data
        common.save_json(common.daily_path(d), rec)
        healed.append(d.isoformat())
        old_txt = f"{old_br:.1f}%" if isinstance(old_br, (int, float)) else str(old_br)
        new_txt = f"{new_br:.1f}%" if isinstance(new_br, (int, float)) else str(new_br)
        print(f"[백필] {d} 치유 완료: 이탈률 {old_txt} → {new_txt}")

    print(f"[백필] 요약: 치유 {len(healed)}일 / 레코드없음 {len(skipped)}일 / 실패 {len(failed)}일")
    if failed:
        print(f"[백필] 실패 날짜: {', '.join(failed)}")


if __name__ == "__main__":
    main()
