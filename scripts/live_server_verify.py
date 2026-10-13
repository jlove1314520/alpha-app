# -*- coding: utf-8 -*-
"""常駐 alpha_live_server 重啟後的四步驗證（CLAUDE.md 七之二），不讀 token（2026-10-13 先.八十一-63）。

  ① 服務活著：GET /health（公開版只回 ok）
  ② 啟動 log 的 [build] git sha 與 repo HEAD 相同；不同時，確認兩者之間伺服器相關檔（本檔＋延後 import 的本地模組）沒有差異
  ③ OPTIONS 預檢回精確來源＋allow-credentials:true
  ④ stale_process＝false 的等效：把 [build] 行記下的啟動時內容雜湊，跟現在檔案重算的雜湊逐一比對（同一套演算法）
**只讀 log 裡以「[build]」開頭的行**——同一份 log 還有給 App 配對用的 token 那一行，絕不讀出、不印出。
用法：python scripts/live_server_verify.py [--port 8001]
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "research" / "alpha_live_server_stdout.log"
SERVER_FILES = {"alpha_live_server": ROOT / "research" / "alpha_live_server.py",
                "auto_rebalance_bb90": ROOT / "research" / "auto_rebalance_bb90.py",
                "auto_ledger_view": ROOT / "research" / "auto_ledger_view.py",
                "web_push": ROOT / "research" / "web_push.py",
                "price_history_store": ROOT / "scripts" / "price_history_store.py"}
ORIGIN = "https://jlove1314520.github.io"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def build_lines(log: Path = LOG) -> dict:
    """最後一次啟動的 [build] 資訊。逐行讀、只留 [build] 開頭的行，其餘（含 token 行）直接丟掉不保存。"""
    sha, src, deps = None, None, {}
    with log.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("[build]"):
                continue
            if "git sha=" in line:
                sha = line.split("git sha=", 1)[1].split()[0].split("　")[0]
                src, deps = None, {}  # 新的一次啟動，清掉前一次的雜湊
            elif "source_hash=" in line:
                body = line.split("source_hash=", 1)[1].strip()
                src = body.split()[0]
                if " deps=" in body:
                    deps = dict(x.split(":", 1) for x in body.split(" deps=", 1)[1].split(",") if ":" in x)
    return {"sha": sha, "source_hash": src, "deps": deps}


def _h(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    except OSError:
        return ""


def _git(*a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main(port: int = 8001) -> int:
    base = f"http://127.0.0.1:{port}"
    res = []
    try:
        r = requests.get(base + "/health", timeout=10)
        res.append(("①服務活著（/health 200）", r.status_code == 200 and r.json().get("ok") is True, f"HTTP {r.status_code}"))
    except Exception as e:  # noqa: BLE001
        res.append(("①服務活著（/health 200）", False, type(e).__name__))
    b = build_lines()
    head = _git("rev-parse", "--short=7", "HEAD").stdout.strip()
    same = bool(b["sha"]) and head.startswith(b["sha"][:7])
    if same:
        res.append(("②build sha＝HEAD", True, f"{b['sha']}＝{head}"))
    else:
        d = _git("diff", "--quiet", b["sha"] or "HEAD", "HEAD", "--", *[str(p.relative_to(ROOT)) for p in SERVER_FILES.values()])
        res.append(("②build sha 與 HEAD 之間伺服器相關檔無差異", bool(b["sha"]) and d.returncode == 0, f"{b['sha']} vs HEAD {head}"))
    try:
        o = requests.options(base + "/live/quotes", timeout=10, headers={
            "Origin": ORIGIN, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "x-alpha-local-token"})
        ok = o.headers.get("access-control-allow-origin") == ORIGIN and o.headers.get("access-control-allow-credentials") == "true"
        res.append(("③OPTIONS 預檢（精確來源＋allow-credentials）", ok, f"HTTP {o.status_code}"))
    except Exception as e:  # noqa: BLE001
        res.append(("③OPTIONS 預檢", False, type(e).__name__))
    if not b["source_hash"]:
        res.append(("④stale_process＝false（重算雜湊比對）", False, "log 沒有 source_hash（伺服器是舊版，需重啟一次）"))
    else:
        now = {k: _h(p) for k, p in SERVER_FILES.items()}
        start = {"alpha_live_server": b["source_hash"], **b["deps"]}
        diff = [k for k in now if start.get(k) and start[k] != now[k]]
        res.append(("④stale_process＝false（啟動時雜湊＝現在檔案）", not diff, "全部一致" if not diff else "已改未重啟：" + "、".join(diff)))
    for name, ok, info in res:
        print(("PASS " if ok else "FAIL ") + f"{name}：{info}")
    bad = sum(1 for _, ok, _ in res if not ok)
    print(f"合計 {len(res)} 項，失敗 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8001))
