# -*- coding: utf-8 -*-
"""先.一二九-2②（2026-10-22，收件匣 011）：模擬 H 訓練面板的 f_dividend_yield_ttm 換成修正後定義。

只改面板每列的 f_dividend_yield_ttm 一欄，其他欄、標籤不動；模型尚未訓練（沒有觀察任何結果）。
新值＝factors._dividend_yield_ttm_cash()（窗口只取一年份）在 feature_date 的值 ÷ 當天 FinMind 原始收盤，
與 factors.prepare_factors() 修正後的算法相同（FinMind 路徑的 close 本來就是同一份原始收盤）。
離線：擋網路、只讀本機快取（load_dev 截在 VAL_END，不碰 holdout）；沒有原始收盤快取的股票該欄改 None。
--check 2884,2330：先拿 prepare_factors() 在這幾檔逐列比對，一致才寫檔。

跑法：cd research && python paper_8_refresh_dividend_yield.py [--check 2884,2330,2412] [--dry-run]
"""
import argparse
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _no_net(*a, **k):
    raise RuntimeError("network blocked (paper_8_refresh_dividend_yield)")


socket.socket.connect = _no_net
socket.create_connection = _no_net

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import factors  # noqa: E402
from finmind_client import _cache_path, load_dev  # noqa: E402
from paper_8_ml_tracker import FACTOR_START, PANEL_DIR  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

COL = "f_dividend_yield_ttm"


def new_values(sid: str, feature_dates: list[str]) -> dict:
    if not (_cache_path("TaiwanStockPrice", sid, FACTOR_START, VAL_END).exists()
            and _cache_path("TaiwanStockDividend", sid, FACTOR_START, VAL_END).exists()):
        return {}
    raw = load_dev("TaiwanStockPrice", sid, FACTOR_START)
    if raw.empty:
        return {}
    px = pd.DataFrame({"date": raw["date"].astype(str).str[:10],
                       "close": pd.to_numeric(raw["close"], errors="coerce")})
    px = px[px["date"].isin(set(feature_dates))].sort_values("date").reset_index(drop=True)
    px = factors._asof_join(px, factors._dividend_yield_ttm_cash(sid, FACTOR_START), "ttm_cash_dividend", "ttm")
    out = {}
    for dt, c, t in zip(px["date"], px["close"], px["ttm"]):
        v = t / c if (c > 0 and t == t) else np.nan
        out[dt] = float(v) if np.isfinite(v) else None
    return out


def check(sids: list[str]) -> bool:
    import adjust
    from strategies.weinstein_stage2 import prepare_market_data
    mk = prepare_market_data(load_dev("TaiwanStockPrice", "TAIEX", FACTOR_START))
    ok = True
    for sid in sids:
        rows = json.loads((PANEL_DIR / f"{sid}.json").read_text(encoding="utf-8"))["rows"]
        fds = [r["feature_date"] for r in rows]
        mine = new_values(sid, fds)
        d = factors.prepare_factors(sid, adjust.adjusted_price_series(sid, FACTOR_START), mk, FACTOR_START)
        ref = dict(zip(pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d"), d[COL]))
        bad = 0
        for fd in fds:
            a, b = mine.get(fd), ref.get(fd)
            b = None if b is None or not np.isfinite(b) else float(b)
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 1e-12 * max(1.0, abs(b))):
                bad += 1
        print(f"check {sid}: {len(fds)} 列，與 prepare_factors 不一致 {bad} 列")
        ok &= bad == 0
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="2884,2330,2412")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.check and not check(a.check.split(",")):
        print("比對不一致，不寫檔。")
        return 1
    n_files = n_rows = n_none = n_changed = 0
    old_vals, new_vals = [], []
    for p in sorted(PANEL_DIR.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:  # build-panel 同時在刪檔／寫檔
            print(f"  [skip] {p.name}：{e!r}")
            continue
        rows = obj.get("rows") or []
        if not rows:
            continue
        nv = new_values(p.stem, [r["feature_date"] for r in rows])
        for r in rows:
            old, new = r.get(COL), nv.get(r["feature_date"])
            if old is not None and new is not None:
                old_vals.append(old); new_vals.append(new)
            n_changed += (old != new)
            n_none += new is None
            r[COL] = new
        n_files += 1
        n_rows += len(rows)
        if not a.dry_run:
            p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    o, n = np.array(old_vals), np.array(new_vals)
    print(f"{'（乾跑）' if a.dry_run else ''}面板 {n_files} 檔 {n_rows} 列；值有變 {n_changed} 列；新值為空 {n_none} 列（{n_none / max(n_rows, 1):.1%}）")
    if len(o):
        ratio = np.nanmedian(n / np.where(o > 0, o, np.nan))
        print(f"新舊皆有值 {len(o)} 列：舊中位數 {np.median(o):.4f}、新中位數 {np.median(n):.4f}、新÷舊中位數 {ratio:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
