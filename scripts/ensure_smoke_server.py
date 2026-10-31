"""冒煙測試用的本機靜態伺服器：已經有就沿用，沒有才啟動一個（先.一〇九-14）。

為什麼有這支：10/16 起每個工作階段各自跑 `(python -m http.server 8792 &)`，
沒人檢查 8792 是不是已經有人在聽，結果留下 5 組孤兒 bash＋http.server
（先.一〇九-11 孤兒巡檢查到）。這支先打 http://127.0.0.1:8792/index.html：
- 回 200 且內容跟本 repo 的 index.html 相同 → 已經有伺服器，什麼都不做；
- 回 200 但內容不同（別份工作目錄／worktree 開的伺服器）→ 不沿用、exit 1 並說明
  （先.一三五-1fg：沿用會讓冒煙測到別份 index.html，冒煙全過也不代表這份程式碼沒壞）；
- 打不通 → 用獨立行程（Windows DETACHED_PROCESS，不跟著呼叫端的 bash 外殼一起掛著）
  在 repo 根目錄啟動 `python -m http.server 8792 --bind 127.0.0.1`，
  PID 寫進 research/.smoke_server.pid，再等到它回 200 為止（最多 10 秒）。

用法：python scripts/ensure_smoke_server.py [--port 8792]
結束碼：0＝伺服器可用；1＝啟動後 10 秒內仍打不通，或 8792 上是別份 index.html。
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


def _fetch(port: int) -> bytes | None:
    """回 index.html 內容；打不通或非 200 回 None。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2) as r:
            return r.read() if r.status == 200 else None
    except Exception:
        return None


def _alive(port: int) -> bool:
    return _fetch(port) is not None


def _same_repo(body: bytes) -> bool:
    try:
        return body == (ROOT / "index.html").read_bytes()
    except OSError as e:  # 讀不到本機檔就無從比對，照舊沿用（只降級成警告）
        print(f"[ensure_smoke_server] [warn] 讀不到本機 index.html 無法比對：{e}", file=sys.stderr)
        return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8792)
    a = ap.parse_args()

    body = _fetch(a.port)
    if body is not None:
        if not _same_repo(body):
            print(f"[ensure_smoke_server] {a.port} 已有伺服器，但它給的 index.html 跟 {ROOT} 這份不同"
                  f"（可能是別的工作目錄開的），不沿用；請先關掉那個伺服器或用 --port 換埠", file=sys.stderr)
            return 1
        print(f"[ensure_smoke_server] {a.port} 已有伺服器回 200 且內容一致，沿用，不另外啟動")
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
