"""Jandi Incoming Webhook 전송.

data/_jandi-YYYY-MM-DD.json payload 를 읽어 전송한다.
(analyze.py 가 payload 를 미리 만들어 둠.)
"""
import requests

import common


def send(payload):
    url = common.env("JANDI_WEBHOOK_URL", required=True)
    headers = {
        "Accept": "application/vnd.tosslab.jandi-v2+json",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp


def main():
    d = common.yesterday()
    payload = common.load_json(common.DATA_DIR / f"_jandi-{d.isoformat()}.json")
    if not payload:
        raise SystemExit(f"[전송오류] payload 가 없습니다. analyze.py 를 먼저 실행하세요: _jandi-{d.isoformat()}.json")
    send(payload)
    print(f"[Jandi] {d} 리포트 전송 완료")


if __name__ == "__main__":
    main()
