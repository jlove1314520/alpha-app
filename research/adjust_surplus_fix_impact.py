# -*- coding: utf-8 -*-
"""先.一三三-1d／收件匣 023 A（2026-10-23）：adjust.py 加資本公積配息／配股後的影響清單。離線、零請求、不算任何報酬。

比較「修正前 adjust.py（scratch 備份）」與「修正後」的 FinMind 路徑還原（_finmind_adjusted_frame，2010-01-01 起本機快取）：
- 每檔：有公積配發的事件（日期、公積配息／配股、舊係數→新係數）、2015～2024 與 2015 以前 adj_close 最大相對變動、變動日數；
- 實際走哪條路徑：adjusted_price_series 先試 yfinance，yfinance 路徑完全不受影響，只有 FinMind 路徑（含 yfinance 被物理檢查踢回）會變；
- 模擬 H 訓練面板：該股走 FinMind 路徑時，特徵日往回 60 個交易日～標籤終點之間有受影響除息日的列＝可能變動的列（上限估計）。
輸出 research/data/adjust_surplus_fix_impact.json
跑法：cd research && python adjust_surplus_fix_impact.py <修正前 adjust.py 路徑>
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (adjust_surplus_fix_impact)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import adjust as NEW  # noqa: E402
from finmind_client import _cache_path, load_dev  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

START = "2010-01-01"
D = Path(__file__).parent / "data"
OUT = D / "adjust_surplus_fix_impact.json"
PANEL = D / "paper_8_train_panel"

spec = importlib.util.spec_from_file_location("adjust_old", sys.argv[1])
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)
# 舊版放在暫存資料夾，補充檔路徑要指回 research/data（否則舊版會少了官方除權息／減資補充，比較到的不是公式差異）
OLD.SUPPLEMENTAL_REDUCTIONS, OLD.SUPPLEMENTAL_EXRIGHTS = NEW.SUPPLEMENTAL_REDUCTIONS, NEW.SUPPLEMENTAL_EXRIGHTS


def offline(mod):
    real = mod.load_dev

    def f(ds, sid, *a, **k):
        st = a[0] if a else START
        if ds in ("TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice", "TaiwanStockParValueChange") \
                and not _cache_path(ds, sid, st, VAL_END).exists():
            return pd.DataFrame()
        return real(ds, sid, *a, **k)
    mod.load_dev = f


offline(NEW)
offline(OLD)


def surplus_rows(sid):
    d = load_dev("TaiwanStockDividend", sid, START)
    if d.empty:
        return []
    out = []
    for r in d.itertuples():
        cs = float(getattr(r, "CashStatutorySurplus", 0) or 0)
        ss = float(getattr(r, "StockStatutorySurplus", 0) or 0)
        ex = getattr(r, "CashExDividendTradingDate", "") or getattr(r, "StockExDividendTradingDate", "")
        if (cs > 0 or ss > 0) and ex:
            out.append({"ex_date": str(ex), "cash_surplus": cs, "stock_surplus": ss})
    return out


def path_of(sid):
    try:
        s = NEW.adjusted_price_series(sid, START)
        return str(s["source"].iloc[-1]) if len(s) and "source" in s.columns else "unknown"
    except Exception as e:  # noqa: BLE001
        return f"unknown:{type(e).__name__}"


def panel_rows_affected(sid, ex_dates, cal):
    p = PANEL / f"{sid}.json"
    if not p.exists():
        return 0, 0
    rows = json.loads(p.read_text(encoding="utf-8")).get("rows") or []
    pos = {d: i for i, d in enumerate(cal)}
    hit = 0
    for r in rows:
        fi = pos.get(r["feature_date"])
        lo = cal[max(0, fi - 60)] if fi is not None else r["feature_date"]
        if any(lo <= e <= r["label_end"] for e in ex_dates):
            hit += 1
    return hit, len(rows)


def main() -> int:
    stocks = sorted({p.name.split("__")[1] for p in (D / "raw").glob(f"TaiwanStockDividend__*__{START}__*.parquet")})
    tx = load_dev("TaiwanStockPrice", "TAIEX", START)
    cal = sorted(tx["date"].astype(str).str[:10]) if not tx.empty else []
    res, n_scan = [], 0
    panel_hit = panel_tot = 0
    for sid in stocks:
        if not _cache_path("TaiwanStockPrice", sid, START, VAL_END).exists():
            continue
        ev = surplus_rows(sid)
        if not ev:
            continue
        n_scan += 1
        try:
            a, b = OLD._finmind_adjusted_frame(sid, START), NEW._finmind_adjusted_frame(sid, START)
        except Exception as e:  # noqa: BLE001
            res.append({"stock_id": sid, "error": f"{type(e).__name__}: {e}"[:120]})
            continue
        if a.empty or b.empty:
            continue
        m = a[["date", "adj_close"]].merge(b[["date", "adj_close"]], on="date", suffixes=("_o", "_n"))
        m["rel"] = (m["adj_close_n"] / m["adj_close_o"] - 1).abs()
        post, pre = m[m["date"] >= "2015-01-01"], m[m["date"] < "2015-01-01"]
        fo = {e["ex_date"]: e["factor"] for e in OLD.adjustment_events(sid, START).to_dict("records")} if True else {}
        fn = {e["ex_date"]: e["factor"] for e in NEW.adjustment_events(sid, START).to_dict("records")}
        for e in ev:
            e["factor_old"] = round(fo[e["ex_date"]], 6) if e["ex_date"] in fo else None
            e["factor_new"] = round(fn[e["ex_date"]], 6) if e["ex_date"] in fn else None
        path = path_of(sid)
        ex_post = [e["ex_date"] for e in ev if e["ex_date"] >= "2015-01-01" and e["factor_old"] != e["factor_new"]]
        hit, tot = panel_rows_affected(sid, [e["ex_date"] for e in ev if e["factor_old"] != e["factor_new"]], cal) \
            if path.startswith("finmind") else (0, 0)
        panel_hit += hit
        res.append({"stock_id": sid, "path": path, "events": ev,
                    "n_changed_events_2015_2024": len(ex_post),
                    "max_rel_change_2015_2024": round(float(post["rel"].max()), 6) if len(post) else 0.0,
                    "max_rel_change_pre2015": round(float(pre["rel"].max()), 6) if len(pre) else 0.0,
                    "n_dates_changed": int((m["rel"] > 1e-12).sum()), "paper8_panel_rows_affected": hit})
    for p in PANEL.glob("*.json"):
        panel_tot += len(json.loads(p.read_text(encoding="utf-8")).get("rows") or [])
    aff = [r for r in res if r.get("max_rel_change_2015_2024", 0) > 1e-12]
    fin = [r for r in aff if str(r.get("path", "")).startswith("finmind")]
    summary = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
               "n_stocks_with_surplus_rows": n_scan, "n_stocks_changed_2015_2024_finmind_path_calc": len(aff),
               "n_of_those_actually_on_finmind_path": len(fin),
               "n_changed_events_2015_2024": sum(r.get("n_changed_events_2015_2024", 0) for r in res),
               "paper8_panel_rows_affected_upper_bound": panel_hit, "paper8_panel_rows_total": panel_tot,
               "paper8_panel_affected_pct": round(100 * panel_hit / panel_tot, 3) if panel_tot else None,
               "note": "yfinance 路徑不受影響；FinMind 路徑股票的 2015 以後還原價會變。模擬 H 受影響列數為上限估計（特徵日往回 60 交易日～標籤終點含受影響除息日）。"}
    OUT.write_text(json.dumps({"summary": summary, "stocks": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
