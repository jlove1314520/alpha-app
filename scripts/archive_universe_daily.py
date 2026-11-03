# -*- coding: utf-8 -*-
"""先.一三五-1ie 甲（2026-11-04 [預設放行]，Cowork 可推翻）：前向判定用的「全宇宙每日價格」月檔存檔。

背景：I～R 共 10 支前向模擬的隨機時點／控制組對照要整段追蹤期間的全宇宙日線，但 data/price_history/ 只留約 90 日。
1ic 已驗證可從 git 歷史串回（52 版、原始收盤 0 不一致），規則＝「每一天取最後一個含該日的版本；
含息日報酬取最後一個同時含 t−1 與 t 的版本」。git 歷史一旦被壓縮改寫就斷，所以每月存一份月檔進 repo。

輸出：research/data/universe_daily/YYYY-MM.json.gz（research/data/ 被 gitignore，首次要 git add -f；之後已追蹤即可一般 add）。
內容：{"month", "built_at", "rule", "n_versions_read", "dates", "codes": {代號: [[日期, 原始收盤, 含息日報酬或 null], ...]}}
含息日報酬＝同一版本內 adj_close_t / adj_close_{t−1} − 1（t−1 是該版本內前一列，不跨版本拼接）。
下市股：只要任何版本出現過該月的列就收錄（避免存活者偏誤）。

唯讀、零外部請求：只用 git log／git show 讀本機 git 物件，不寫 data/。
預設：補齊 2026-07 起到「上個月」為止尚未存檔的月份（已存就跳過，冪等）。掛在 scripts/news_local_fallback.py（每 30 分鐘）
開頭，實際上每月 1 號後第一班才會做事。自身任何失敗只印警告、回傳空清單（十二節）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIR = "data/price_history"
OUT_DIR = ROOT / "research" / "data" / "universe_daily"
FIRST_MONTH = "2026-07"  # 最早一版（2026-10-13）90 日視窗約從 6 月初起，7 月是第一個完整月
TW = timezone(timedelta(hours=8))


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True, timeout=300).stdout


def versions() -> list[tuple[str, str]]:
    """(短 hash, 台北日期 YYYY-MM-DD)，新→舊。"""
    out = []
    for line in _git("log", "--format=%h %ct", "--", DIR + "/").decode().split("\n"):
        if line.strip():
            h, ct = line.split()
            out.append((h, datetime.fromtimestamp(int(ct), TW).strftime("%Y-%m-%d")))
    return out


def _load(rev: str) -> dict:
    names = [n for n in _git("ls-tree", "--name-only", f"{rev}:{DIR}").decode().split() if n.startswith("b") and n.endswith(".json")]
    prices = {}
    for n in names:
        prices.update(json.loads(_git("show", f"{rev}:{DIR}/{n}")).get("prices") or {})
    return prices


def prev_month(today: datetime | None = None) -> str:
    t = (today or datetime.now(TW)).replace(day=1) - timedelta(days=1)
    return t.strftime("%Y-%m")


def months_between(a: str, b: str) -> list[str]:
    out, (y, m) = [], map(int, a.split("-"))
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_months(months: list[str]) -> dict:
    """一次讀過所有相關版本（新→舊），同時填多個月份；已填過的（代號, 日期）不再覆蓋＝取最晚版本。"""
    vs = versions()
    lo = min(months) + "-01"
    filled = {m: {} for m in months}  # month -> code -> date -> [close, ret]
    n_read = 0
    for h, vdate in vs:
        if vdate < lo:  # 該版本提交時還沒有這些月份的資料
            break
        p = _load(h)
        n_read += 1
        for code, rows in p.items():
            prev = None
            for r in rows:
                d = r.get("date") or ""
                m = d[:7]
                if m in filled:
                    slot = filled[m].setdefault(code, {})
                    cur = slot.get(d)
                    ret = None
                    if prev is not None and prev.get("adj_close") and r.get("adj_close"):
                        ret = round(r["adj_close"] / prev["adj_close"] - 1, 8)
                    if cur is None:
                        slot[d] = [r.get("close"), ret]
                    elif cur[1] is None and ret is not None:  # 較新版本缺 t−1（視窗起點），用較舊版本的報酬補
                        cur[1] = ret
                prev = r
        del p
    out = {}
    for m, codes in filled.items():
        dates = sorted({d for c in codes.values() for d in c})
        out[m] = {"month": m, "built_at": datetime.now(TW).isoformat(timespec="seconds"),
                  "rule": "每日取最晚含該日的 data/price_history 版本；含息日報酬取最晚同時含 t−1、t 的版本（同版本內 adj_close 比值）",
                  "n_versions_read": n_read, "dates": dates,
                  "codes": {c: [[d, *v] for d, v in sorted(rows.items())] for c, rows in sorted(codes.items())}}
    return out


def run(months: list[str] | None = None, force: bool = False) -> list[str]:
    """回傳本輪新寫出的檔案（repo 相對路徑）。失敗只警告、回傳空清單。"""
    try:
        todo = months or months_between(FIRST_MONTH, prev_month())
        if not force:
            todo = [m for m in todo if not (OUT_DIR / f"{m}.json.gz").exists()]
        if not todo:
            return []
        built = build_months(todo)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        written = []
        for m, obj in built.items():
            if not obj["dates"]:
                print(f"[warn] 全宇宙月檔：{m} 在 git 歷史裡找不到任何日期，不寫檔", flush=True)
                continue
            path = OUT_DIR / f"{m}.json.gz"
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
            tmp.replace(path)
            written.append(path.relative_to(ROOT).as_posix())
            print(f"全宇宙月檔 {m}：{len(obj['codes'])} 檔、{len(obj['dates'])} 個交易日（{obj['dates'][0]}～{obj['dates'][-1]}）、"
                  f"{path.stat().st_size / 1e6:.2f} MB、讀 {obj['n_versions_read']} 版", flush=True)
        return written
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 全宇宙月檔存檔失敗：{type(e).__name__}: {e}", flush=True)
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*", help="YYYY-MM；不給＝補齊 2026-07 起到上個月尚未存檔的月份")
    ap.add_argument("--force", action="store_true", help="已存在也重建")
    a = ap.parse_args()
    run(a.months, a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
