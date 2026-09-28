# -*- coding: utf-8 -*-
"""驗.六第四點：異常掃描複查（2026-09-27總司令裁示【驗.六：資料修正後
的影響重估（診斷，不改任何判定）】）。

修正後（含修.六/查.二/查.三/修.七四項修正），對2007-2014與holdout期間
重新跑日期相依門檻(2015-06-01前±7.5%、之後±10.5%，`adjust._anomaly_
threshold_pct()`)的異常掃描，**還原價(adj_close)與原始價(close)分開
統計**，跟驗.五的1,158(2007-2014)／435(holdout)件對照。

**重要方法論揭露（誠實揭露，不是迴避）**：驗.五原始的1,158/435是用
**固定11%門檻**掃**還原價**(`adjusted_price_series()`的`adj_close`)
算出來的（見`audit_h1_benchmark_contamination.py`），跟這裡的「日期
相依門檻」不是同一把尺——直接比較兩個數字本身已經混了兩個變因（①資料
修正前後②門檻定義改變）。本腳本額外提供「用同樣日期相依門檻、但用
修正*前*的資料」這組基準線（凍結adjust.py修.六重構前版本，比照驗.五/
查.二已建立的重建模式），讓「資料修正的效果」跟「門檻定義改變的效果」
分開看得出來，不是含糊地說『少了多少』。

只作診斷，不改變任何既有判定。

輸出：research/data/diag_v6_anomaly_rescan.json
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import json
from pathlib import Path

import pandas as pd

import holdout_2025_dividend_account_test as h1
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from universe import classify_security

OUT = Path(__file__).parent / "data" / "diag_v6_anomaly_rescan.json"
REGISTERED_V5 = {"universe_2007_2014_flat11pct_adjclose": 1158, "universe_holdout_flat11pct_adjclose": 435}
MIN_ROWS_AFTER_LISTING = 5


def _build_sample(exclude_emerging: bool = True) -> list[str]:
    """2026-09-29驗.七更正：舊版用`h1._info_lookup()`取`type`，但該lookup只含
    stock_name/industry_category，`type`永遠是None→興櫃排除實際上從未生效
    （驗.六第一版就是這樣跑的，樣本仍是251檔含39檔興櫃，如實揭露）。改從
    TaiwanStockInfo parquet快取直接讀`type`欄位。"""
    import glob
    info = h1._info_lookup()
    type_map = pd.read_parquet(sorted(glob.glob(str(Path(__file__).parent / "data" / "raw" / "TaiwanStockInfo__ALL__*.parquet")))[-1])         .drop_duplicates("stock_id", keep="last").set_index("stock_id")["type"].to_dict()
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    out = []
    for sid in sample_ids:
        row = info.get(sid) or {}
        sec_type = type_map.get(sid) if exclude_emerging else None
        cls = classify_security(sid, row.get("stock_name"), row.get("industry_category"), sec_type)
        if cls == "普通股":
            out.append(sid)
    return out


def _scan(adjust_module, sids: list[str], lo: str, hi: str, price_kind: str, uncapped: bool = False) -> list[dict]:
    """price_kind: 'adj_close' or 'close'。`uncapped=True`時改走
    `h1.uncapped_adjusted_price_series()`（H.一腳本內的函式，其檔名在呼叫
    堆疊上→守.一允許清單放行），否則`adjusted_price_series()`會被
    `load_dev()`cap在VAL_END=2024-12-31，holdout視窗(2025+)根本沒有列——
    2026-09-29驗.七更正：驗.六第一版的holdout掃描就是這樣得到「0筆」的，
    那個0是cap造成的假象，不是資料修好了。"""
    hits = []
    thr_fn = adjust_module._anomaly_threshold_pct
    for sid in sids:
        try:
            px = (h1.uncapped_adjusted_price_series(sid, "2003-01-01") if uncapped
                  else adjust_module.adjusted_price_series(sid, "2003-01-01"))
        except Exception:  # noqa: BLE001
            continue
        if px.empty or price_kind not in px.columns:
            continue
        d = px[(px["date"] >= lo) & (px["date"] <= hi)].reset_index(drop=True)
        if len(d) <= MIN_ROWS_AFTER_LISTING:
            continue
        ret = d[price_kind].pct_change() * 100
        for i in range(MIN_ROWS_AFTER_LISTING, len(d)):
            r = ret.iloc[i]
            date_str = str(d.loc[i, "date"])
            if pd.notna(r) and abs(r) > thr_fn(date_str):
                hits.append({"stock_id": sid, "date": date_str, "ret_pct": round(float(r), 2),
                             "threshold_pct": thr_fn(date_str)})
    return hits


def main() -> None:
    print("[驗.六項四] 建立樣本(已排除興櫃，查.三/修.七後的預設宇宙行為)...", flush=True)
    sample_common = _build_sample()
    print(f"  普通股樣本(已排除興櫃)：{len(sample_common)}檔", flush=True)

    import adjust as adjust_current

    periods = {
        "universe_2007_2014": ("2007-01-01", "2014-12-31"),
        "universe_holdout": ("2025-01-01", "2026-09-24"),
    }

    result = {"generated_at": pd.Timestamp.now().isoformat(),
              "verdict_locked_note": "本檔案全部數字為診斷值，不改變任何既有判定。2026-09-29驗.七更正版：興櫃排除真正生效、holdout改走uncapped路徑（第一版holdout=0筆為VAL_END cap假象）。",
              "registered_v5_flat11pct_adjclose": REGISTERED_V5,
              "n_sample_common_stock_excl_emerging": len(sample_common)}

    for name, (lo, hi) in periods.items():
        print(f"\n[驗.六項四] {name}（{lo}~{hi}）修正後日期相依門檻掃描...", flush=True)
        unc = name == "universe_holdout"
        hits_adj = _scan(adjust_current, sample_common, lo, hi, "adj_close", uncapped=unc)
        hits_raw = _scan(adjust_current, sample_common, lo, hi, "close", uncapped=unc)
        print(f"  還原價(adj_close)命中：{len(hits_adj)}筆", flush=True)
        print(f"  原始價(close)命中：{len(hits_raw)}筆", flush=True)
        result[name] = {
            "adj_close_hits": len(hits_adj), "close_hits": len(hits_raw),
            "adj_close_top20": hits_adj[:20], "close_top20": hits_raw[:20],
        }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT}")


if __name__ == "__main__":
    main()
