# -*- coding: utf-8 -*-
"""每週檢查 live server 相依套件有沒有新版（2026-09-06 連線三.4）。

**只回報，不自動升級。** 理由：alpha_live_server.py 是常駐服務，自動升級等於在沒有
人看著的時候換掉正在對外服務的程式的地基；升級要照 CLAUDE.md「七之二、常駐服務
發布紀律」的四步驗過才算完成。這支只負責讓總司令知道「有新版了」。

資料來源：PyPI 官方 JSON API（https://pypi.org/pypi/<package>/json），公開端點，
不需要金鑰，符合「只走官方公開端點」的鐵律。

用法：python scripts/check_security_updates.py
輸出：終端機摘要 ＋ data/dependency_status.json（給設定頁顯示用）
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "research" / "requirements-live.txt"
OUT = ROOT / "data" / "dependency_status.json"
TZ = timezone(timedelta(hours=8))


def parse_pinned() -> dict[str, str]:
    pinned = {}
    for line in REQ.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, ver = line.split("==", 1)
        pinned[name.strip()] = ver.strip()
    return pinned


def latest(pkg: str) -> tuple[str | None, str | None]:
    """回傳 (最新版, 錯誤訊息)。查不到就誠實回報，不猜。"""
    try:
        url = f"https://pypi.org/pypi/{pkg}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaDepCheck/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["info"]["version"], None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def main() -> int:
    if not REQ.exists():
        print(f"找不到 {REQ}")
        return 2
    pinned = parse_pinned()
    rows, behind = [], 0
    for pkg, cur in sorted(pinned.items()):
        new, err = latest(pkg)
        is_behind = bool(new and new != cur)
        if is_behind:
            behind += 1
        rows.append({"package": pkg, "pinned": cur, "latest": new, "behind": is_behind, "error": err})
        mark = "有新版" if is_behind else ("查詢失敗" if err else "已是最新")
        print(f"  {pkg:<12} 目前 {cur:<12} 最新 {new or '?':<12} {mark}")

    doc = {
        "generated_at": datetime.now(TZ).isoformat(),
        "source": "PyPI 官方 JSON API",
        "policy": "只回報不自動升級；升級須照 CLAUDE.md 七之二 四步驗證",
        "behind_count": behind,
        "packages": rows,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{behind} 個套件有新版　→ {OUT.relative_to(ROOT)}")
    if behind:
        print("提醒：這只是「有新版」，不代表舊版有漏洞。要不要升級由總司令決定，")
        print("      升級後必須重啟並跑四步驗證（重啟→比對 build sha→OPTIONS 預檢→stale_process=false）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
