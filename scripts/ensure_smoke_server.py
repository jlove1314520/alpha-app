"""冒煙測試用的本機靜態伺服器：已經有就沿用，沒有才啟動一個（先.一〇九-14）。

為什麼有這支：10/16 起每個工作階段各自跑 `(python -m http.server 8792 &)`，
沒人檢查 8792 是不是已經有人在聽，結果留下 5 組孤兒 bash＋http.server
（先.一〇九-11 孤兒巡檢查到）。這支先打 http://127.0.0.1:8792/index.html：
- 回 200 → 已經有伺服器，什麼都不做；
- 打不通 → 用獨立行程（Windows DETACHED_PROCESS，不跟著呼叫端的 bash 外殼一起掛著）
  在 repo 根目錄啟動 `python -m http.server 8792 --bind 127.0.0.1`，
  PID 寫進 research/.smoke_server.pid，再等到它回 200 為止（最多 10 秒）。

用法：python scripts/ensure_smoke_server.py [--port 8792]
結束碼：0＝伺服器可用；1＝啟動後 10 秒內仍打不通。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "research" / ".smoke_server.pid"


def _alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8792)
    a = ap.parse_args()

    if _alive(a.port):
        print(f"[ensure_smoke_server] {a.port} 已有伺服器回 200，沿用，不另外啟動")
        return 0

    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    p = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(a.port), "--bind", "127.0.0.1"],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )
    PID_FILE.write_text(f"{p.pid}\n", encoding="utf-8")
    for _ in range(20):
        time.sleep(0.5)
        if _alive(a.port):
            print(f"[ensure_smoke_server] 已啟動 {a.port}（PID {p.pid}，記在 {PID_FILE.relative_to(ROOT)}）")
            return 0
    print(f"[ensure_smoke_server] 啟動 PID {p.pid} 後 10 秒內 {a.port} 仍打不通", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
