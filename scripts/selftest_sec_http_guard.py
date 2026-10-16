# -*- coding: utf-8 -*-
"""先.一〇三-1b-3 自測：sec_http_guard 只記 sec.gov、403 → 警告＋寫檔＋STATUS 文字。不連 SEC（用本機假伺服器）。

用法：python scripts/selftest_sec_http_guard.py
"""
import http.server
import json
import sys
import tempfile
import threading
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import sec_http_guard as G  # noqa: E402
import requests  # noqa: E402

res = []


def check(cond, label):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label)


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(403 if "blocked" in self.path else 200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):  # noqa: D401
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}"
tmp = Path(tempfile.mkdtemp()) / "sec_access_status.json"
G.OUT = tmp
G._COUNTS.clear()

requests.get(base + "/other/ok")                 # 不是 sec.gov → 不記
check(sum(G._COUNTS.values()) == 0, "非 sec.gov 請求不記錄")
requests.get(base + "/sec.gov/ok")               # 網址含 sec.gov（假伺服器）→ 記 200
requests.get(base + "/sec.gov/blocked")          # → 記 403
s = requests.Session()
s.get(base + "/sec.gov/ok")                      # Session.get 也要記到
check(G._COUNTS.get("200") == 2 and G._COUNTS.get("403") == 1, f"requests.get 與 Session.get 都記到（{dict(G._COUNTS)}）")

G._flush()
d = json.loads(tmp.read_text(encoding="utf-8"))
check(d.get("warning", "").startswith(G.WARNING_TEXT), f"有 403 → warning 文字（{d.get('warning')}）")
check(d["scripts"][G.SCRIPT]["status_counts"].get("403") == 1, "寫檔含 403 次數")

# 下一輪全部 200 → 不再列為被擋
G._COUNTS.clear()
G._note("https://www.sec.gov/x", 200)
G._flush()
d2 = json.loads(tmp.read_text(encoding="utf-8"))
check(d2.get("warning") is None and d2["scripts"][G.SCRIPT].get("last_403_at"), "恢復正常後 warning 清空、保留上次 403 時間")

srv.shutdown()
print(f"合計 {len(res)} 項，失敗 {res.count(False)}")
sys.exit(0 if all(res) else 1)
