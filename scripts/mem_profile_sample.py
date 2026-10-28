# -*- coding: utf-8 -*-
"""記憶體取樣（先.一三八-B1，Cowork 收件匣 027 B1）：只量不殺。

平日台北 18:30～21:30 取一筆「前 15 名程式（名稱、工作集 MB）＋可用實體記憶體」，
append 到 research/data/mem_profile_<台北日期>.jsonl（本機，不進公開 repo）。
只記程式名與記憶體，不記命令列與視窗標題（避免記到個資）。

不新建本機排程：由既有每 30 分鐘的 DevQueue runner 與對外連通性監測入口順手呼叫
maybe_sample()（兩者錯開，實際間隔約 10～30 分鐘，不是每 10 分鐘——照實降級，間隔看每列 ts）。
同一 9 分鐘內只取一次；量滿 2 個平日（已有 2 個日期檔且今天不在其中）就自動停。
自身任何失敗只印一行警告、回傳 False，不影響呼叫端（十二節）。

用法（手動測試）：python scripts/mem_profile_sample.py [--force]
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "research" / "data"
TW = timezone(timedelta(hours=8))
DAYS_NEEDED = 2
MIN_GAP_SEC = 9 * 60

PS = ("$p = Get-Process | Group-Object ProcessName | ForEach-Object { [pscustomobject]@{ name = $_.Name; "
      "ws_mb = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum) / 1MB, 1); n = $_.Count } } "
      "| Sort-Object ws_mb -Descending | Select-Object -First 15; "
      "$os = Get-CimInstance Win32_OperatingSystem; "
      "[pscustomobject]@{ top = @($p); free_mb = [math]::Round($os.FreePhysicalMemory / 1KB, 0); "
      "total_mb = [math]::Round($os.TotalVisibleMemorySize / 1KB, 0) } | ConvertTo-Json -Depth 4 -Compress")


def _in_window(now: datetime) -> bool:
    hm = now.hour * 60 + now.minute
    return now.weekday() < 5 and 18 * 60 + 30 <= hm <= 21 * 60 + 30


def _done(today: str) -> bool:
    days = sorted(p.stem.replace("mem_profile_", "") for p in OUT_DIR.glob("mem_profile_*.jsonl"))
    return len(days) >= DAYS_NEEDED and today not in days


def maybe_sample(force: bool = False, caller: str = "") -> bool:
    try:
        now = datetime.now(TW)
        today = now.strftime("%Y-%m-%d")
        if not force and (not _in_window(now) or _done(today)):
            return False
        out = OUT_DIR / f"mem_profile_{today}.jsonl"
        if out.exists() and not force:
            lines = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                last = datetime.fromisoformat(json.loads(lines[-1])["ts"])
                if (now - last).total_seconds() < MIN_GAP_SEC:
                    return False
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS],
                           capture_output=True, timeout=60, encoding="utf-8", errors="replace")
        d = json.loads(r.stdout)
        rec = {"ts": now.isoformat(timespec="seconds"), "caller": caller, "free_mb": d.get("free_mb"),
               "total_mb": d.get("total_mb"),
               "top": [{"name": x.get("name"), "ws_mb": x.get("ws_mb"), "n": x.get("n")} for x in (d.get("top") or [])]}
        if force:  # 手動測試只印、不寫檔（不讓測試樣本被算成量滿的一天）
            print(json.dumps(rec, ensure_ascii=False)[:600])
            return True
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception as e:  # noqa: BLE001 —— 十二節：取樣自身失敗只警告
        try:
            print(f"[warn] mem_profile 取樣失敗（不影響主流程）：{type(e).__name__}: {str(e)[:150]}")
        except Exception:  # noqa: BLE001
            pass
        return False


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    print("取樣" + ("成功" if maybe_sample(force="--force" in sys.argv, caller="manual") else "略過（不在時段／已量滿／9 分鐘內已取）"))
