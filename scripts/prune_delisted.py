# -*- coding: utf-8 -*-
"""把已下市/不在市的代號從 scores*.json 移除（2026-09-06 稽核.一）。

第一份全市場稽核報告抓到：選股排行榜上有 69 檔股票今天完全不在官方名冊裡，價格
停在 2010～2024 年（矽品 2325、勝華 2384、神達 2315、日月光 2311 …）。這些是早就
下市或改組的公司，App 卻照樣把它們排進推薦名單。

這支腳本用 `data/listed_universe.json` 的 active 清單過濾三份榜單，並重新編號 rank
（rank 必須是連續的 1..N，中間挖洞會讓「第 28 名」這種說法失去意義）。
`research/generate_scores_live.py` 也加了同一道過濾，所以下次重新產生榜單時不會再
跑回來——這支負責把「現在已經在 repo 裡的那三份檔案」立刻修好。

用法：`python scripts/prune_delisted.py`（可重複執行，第二次跑會是 0 筆變更）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "data" / "listed_universe.json"
TARGETS = ["scores.json", "scores_momentum.json", "scores_future.json"]
TZ = timezone(timedelta(hours=8))


def main() -> int:
    if not UNIVERSE.exists():
        print(f"！找不到 {UNIVERSE.relative_to(ROOT)}，先跑 scripts/build_listed_universe.py")
        return 2
    uni = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    active = set(uni.get("active") or [])
    if len(active) < 1000:
        # 官方端點半殘時可能只拿到幾十檔，那樣過濾會把整個榜單清空——寧可不動
        print(f"！active 清單只有 {len(active)} 檔，明顯不完整，不執行過濾（避免清空榜單）")
        return 2

    # 除了「不在名冊」，還要擋「還在名冊、但價格早就不動了」的股票。稽核抓到正峰 1538
    # 與永冠-KY 1589 仍在掛牌名冊裡，最後一筆價格卻停在 2024-12-31（長期停止交易/重整），
    # App 照樣把它們排進榜單並顯示一年半前的價格當現價。判斷方式不打網路：拿
    # price_history 全市場最新日期當基準，個股落後超過 STALE_DAYS 天就一起排除。
    STALE_DAYS = 30
    stale_codes: set[str] = set()
    ph_path = ROOT / "data" / "price_history.json"
    market_latest = None
    if ph_path.exists():
        prices = json.loads(ph_path.read_text(encoding="utf-8")).get("prices", {})
        per_code = {}
        for code, rows in prices.items():
            if rows:
                per_code[code] = str(rows[-1].get("date") or "")
        market_latest = max((d for d in per_code.values() if d), default=None)
        if market_latest:
            y, m, dd = (int(x) for x in market_latest.split("-"))
            base = datetime(y, m, dd, tzinfo=TZ).date()
            for code, d in per_code.items():
                try:
                    y2, m2, d2 = (int(x) for x in d.split("-"))
                except Exception:
                    continue
                if (base - datetime(y2, m2, d2, tzinfo=TZ).date()).days > STALE_DAYS:
                    stale_codes.add(code)
    print(f"  全市場最新價格日 {market_latest}，價格落後超過 {STALE_DAYS} 天的代號 {len(stale_codes)} 檔")

    total_removed = 0
    for name in TARGETS:
        path = ROOT / name
        if not path.exists():
            print(f"  - {name} 不存在，跳過")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        stocks = data.get("stocks") or []
        kept, removed = [], []
        for row in stocks:
            code = row.get("code")
            ok = (code in active) and (code not in stale_codes)
            (kept if ok else removed).append(row)

        # 重新編號：原本有 rank 的照原順序重排成 1..N，原本是 null（流動性不足）的維持 null
        n = 0
        for row in kept:
            if row.get("rank") is not None:
                n += 1
                row["rank"] = n

        data["stocks"] = kept
        meta = data.setdefault("meta", {})
        meta["delisted_filter"] = {
            "applied_at": datetime.now(TZ).isoformat(),
            "universe_file": "data/listed_universe.json",
            "stale_days": STALE_DAYS,
            "market_latest_date": market_latest,
            "removed": len(removed),
            "removed_ranked": sum(1 for r in removed if r.get("rank") is not None),
            "note": "移除不在官方上市/上櫃名冊、或價格落後全市場最新交易日超過 "
                    f"{STALE_DAYS} 天的代號（已下市、改組、長期停止交易或重整中）",
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        total_removed += len(removed)
        ranked_removed = [r for r in removed if r.get("rank") is not None]
        print(f"  {name}: 移除 {len(removed)} 檔（其中原本有排名的 {len(ranked_removed)} 檔），保留 {len(kept)} 檔")
        for r in ranked_removed[:10]:
            print(f"      原第 {r['rank']} 名 {r['code']} {r.get('name', '')}")

    print(f"共移除 {total_removed} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main())
