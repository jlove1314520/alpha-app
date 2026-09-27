# -*- coding: utf-8 -*-
"""修.七項三.3：重建`data/price_history.json`的`adj_close`欄位（一次性
腳本，非常駐排程）。

**為什麼不能只重跑`build_price_history.py`**：該腳本的`merge_rows()`
刻意「既有值優先覆蓋」（保護每日排程寫入的較新欄位不被backfill清掉），
但這代表已經存在的`adj_close`（用修正前的錯誤公式算出）**永遠不會被
backfill覆蓋**——實測重跑一次`build_price_history.py`後逐檔比對，
90天滾動視窗內**零筆**`adj_close`實際改變，證實了這一點。這裡是本
還原公式bug（修.七）唯一需要的動作：**只覆蓋`adj_close`欄位，不動
其他欄位**，繞開`merge_rows()`原本保護coverage的設計（那個保護的對象
是「別的排程寫入的新欄位」，不是「已知算錯的舊欄位」，兩者不衝突）。

輸出：就地更新`data/price_history.json`；同時寫
`research/data/adj_close_fix_report.json`記錄哪些股票的哪些日期
adj_close改變了多少（供App分數變化回報使用）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import build_price_history as bph

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
REPORT_PATH = Path(__file__).parent / "data" / "adj_close_fix_report.json"


def recompute_adj_close_for_code(code: str, dates_needed: list[str]) -> dict[str, float] | None:
    """用修正後的`_adjustment_events()`重算這支股票的adj_close，只回傳
    `dates_needed`裡有出現的日期(即目前`price_history.json`裡已經有的
    那些列)，用完整(未裁90天)的原始價格歷史當計算基礎，確保發生在
    視窗更早之前的事件也正確套用進來。"""
    df = bph._load_concat("TaiwanStockPrice", code)
    if df.empty or "close" not in df.columns:
        return None
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    events = bph._adjustment_events(code, df)
    adj = df["close"].astype(float).copy()
    for ev in sorted(events, key=lambda e: e["ex_date"], reverse=True):
        mask = df["date"] < ev["ex_date"]
        adj.loc[mask] = adj.loc[mask] * ev["factor"]
    by_date = dict(zip(df["date"], adj))
    return {d: by_date[d] for d in dates_needed if d in by_date}


def main() -> None:
    payload = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    prices = payload.get("prices", {})
    print(f"[修.七] 讀取 {PRICE_HISTORY_PATH}，共 {len(prices)} 檔")

    changed_report: list[dict] = []
    n_stocks_changed = 0
    n_rows_changed = 0
    for i, (code, rows) in enumerate(prices.items()):
        dates_needed = [r["date"] for r in rows]
        new_adj = recompute_adj_close_for_code(code, dates_needed)
        if new_adj is None:
            continue
        stock_changed_rows = []
        for r in rows:
            old_val = r.get("adj_close")
            new_val = new_adj.get(r["date"])
            if new_val is None:
                continue
            if old_val is None or abs(new_val - old_val) > max(abs(old_val) * 1e-6, 1e-6):
                stock_changed_rows.append({
                    "date": r["date"], "old_adj_close": old_val, "new_adj_close": round(new_val, 4),
                    "diff_pct": round((new_val - old_val) / old_val * 100, 3) if old_val else None,
                })
            r["adj_close"] = round(new_val, 4)
        if stock_changed_rows:
            n_stocks_changed += 1
            n_rows_changed += len(stock_changed_rows)
            max_diff = max((abs(x["diff_pct"]) for x in stock_changed_rows if x["diff_pct"] is not None), default=0.0)
            changed_report.append({"stock_id": code, "n_rows_changed": len(stock_changed_rows),
                                    "max_diff_pct": round(max_diff, 3), "rows": stock_changed_rows})
        if (i + 1) % 500 == 0:
            print(f"  進度 {i+1}/{len(prices)}（目前已發現 {n_stocks_changed} 檔改變）")

    PRICE_HISTORY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[修.七] 已就地更新 {PRICE_HISTORY_PATH}：{n_stocks_changed} 檔股票、{n_rows_changed} 列的adj_close改變")

    changed_report.sort(key=lambda x: -x["max_diff_pct"])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "n_stocks_changed": n_stocks_changed, "n_rows_changed": n_rows_changed,
        "top_changed": changed_report[:50],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[修.七] 明細已寫入 {REPORT_PATH}")
    print("\n變化最大的前20檔：")
    for c in changed_report[:20]:
        print(f"  {c['stock_id']}：{c['n_rows_changed']}列改變，最大差異{c['max_diff_pct']}%")


if __name__ == "__main__":
    main()
