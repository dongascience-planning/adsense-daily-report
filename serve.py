"""대시보드 로컬 웹서버.

report/ 폴더를 사내망에 정적 호스팅한다. PC가 켜져 있는 동안 팀원이 링크로 열람.
수익 데이터 보호를 위해 SERVE_PASS 가 설정돼 있으면 기본 인증(아이디/비번)을 요구한다.

환경변수(.env):
  SERVE_PORT  기본 8080
  SERVE_USER  기본 team
  SERVE_PASS  비우면 인증 없음(누구나 열람). 값이 있으면 그 비번 요구.
"""
import base64
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

BASE = Path(__file__).resolve().parent
ROOT = str(BASE / "report")
TRACKING = BASE / "data" / "tracking.json"
QUESTIONS = BASE / "data" / "questions.json"
JANDI_URL = os.getenv("JANDI_WEBHOOK_URL", "")
PORT = int(os.getenv("SERVE_PORT", "8080"))
USER = os.getenv("SERVE_USER", "team")
PASS = os.getenv("SERVE_PASS", "")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _auth_ok(self):
        if not PASS:
            return True
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(hdr[6:]).decode("utf-8").partition(":")
            return user == USER and pw == PASS
        except Exception:
            return False

    def _deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AdSense Report"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("로그인이 필요합니다.".encode("utf-8"))

    def do_GET(self):
        if not self._auth_ok():
            return self._deny()
        return super().do_GET()

    def _ok(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _bad(self, code=400):
        self.send_response(code)
        self.end_headers()

    def do_POST(self):
        if not self._auth_ok():
            return self._deny()
        path = self.path.rstrip("/")
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._bad()
        if path == "/api/track":
            return self._handle_track(body)
        if path == "/api/question":
            return self._handle_question(body)
        return self._bad(404)

    def _handle_track(self, body):
        iid = body.get("id")
        if not iid:
            return self._bad()
        data = {}
        if TRACKING.exists():
            try:
                data = json.loads(TRACKING.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        item = data.get(iid, {})
        for k in ("date", "insight", "plan", "exec", "status"):
            if k in body:
                item[k] = body[k]
        item.setdefault("status", "active")
        data[iid] = item
        TRACKING.parent.mkdir(exist_ok=True)
        TRACKING.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._ok()

    def _handle_question(self, body):
        q = (body.get("question") or "").strip()
        if not q:
            return self._bad()
        entry = {
            "question": q,
            "name": (body.get("name") or "").strip(),
            "date": body.get("date") or "",
            "insight": body.get("insight") or "",
            "answered": False,
        }
        items = []
        if QUESTIONS.exists():
            try:
                items = json.loads(QUESTIONS.read_text(encoding="utf-8"))
            except Exception:
                items = []
        items.append(entry)
        QUESTIONS.parent.mkdir(exist_ok=True)
        QUESTIONS.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        self._notify_jandi(entry)
        self._ok()

    def _notify_jandi(self, entry):
        if not JANDI_URL:
            return
        info = [{"title": "❓ 질문", "description": entry["question"]}]
        if entry.get("name"):
            info.append({"title": "보낸 사람", "description": entry["name"]})
        if entry.get("date"):
            info.append({"title": "관련 날짜", "description": entry["date"]})
        if entry.get("insight"):
            info.append({"title": "관련 인사이트", "description": entry["insight"][:200]})
        payload = {
            "body": "💬 [대시보드 질문 접수] — 답변이 필요합니다",
            "connectColor": "#f5a623",
            "connectInfo": info,
        }
        try:
            import requests
            requests.post(
                JANDI_URL, json=payload,
                headers={"Accept": "application/vnd.tosslab.jandi-v2+json", "Content-Type": "application/json"},
                timeout=15,
            )
        except Exception as e:  # noqa: BLE001
            print("[질문 Jandi 전송 실패]", e)

    def log_message(self, fmt, *args):
        pass  # 콘솔 로그 억제


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"대시보드 서버 시작: 0.0.0.0:{PORT}  (root={ROOT}, 인증={'있음' if PASS else '없음'})")
    server.serve_forever()
