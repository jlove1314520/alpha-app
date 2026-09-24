# -*- coding: utf-8 -*-
"""閘門.一（2026-09-24總司令裁示【候選名單定案＋抓取程式修正＋開考前
資料品質閘門】＋【開考前修正——宇宙限普通股＋MDD判準回復原裁示】閘門.一
補充）：開考前資料品質閘門，六項全過才准執行`SINGLE_SHOT_2007_2014_
SPEC.md`的2007-2014單發檢定。**只讀既有快取，零新增API呼叫**——
`adjusted_price_series()`/`load_dev()`對`資料.一`已抓取過的(stock_id,
EXTENDED_START)組合是快取命中，不會觸發網路請求。

六項：
1. 價格：2007-2014可用檔數，及其中2007-2008下市股檔數(須>0，證明沒有
   存活者偏差)。
2. 零價格：adj_close<=0已轉NaN（`adjust.py::_mask_non_positive_adj_
   prices()`單一關卡，見閘門結果的殘留驗證），列出比例。
3. 股利：「有除息紀錄但股利率為NaN」必須為0檔（沿用驗.四`audit_f52w_
   2007_data_quality.py::audit_one_stock()`同一套邏輯，對完整245檔
   successful集合重跑，不只是驗.四當時的132/108檔子集）。
4. 基準：`load_0050_full_history()`覆蓋2007-2014全段，且2008年MDD與
   公開資料量級一致(約-50%以上)——沿用規.五已算出的-55.75%。
5. 閘門結果寫成`research/data/exam_2007_2014_data_gate.json`並進repo，
   Cowork要能直接核對。
6.（閘門.一補充新增）2007-2014期間通過`common_stock_only()`的可用檔數，
   以及其中2007-2008年下市的普通股檔數（必須>0）。

用法：python research/exam_2007_2014_data_gate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from survival_constraint_allocation_test import load_0050_full_history, segment_mdd
from universe import delisted_stock_ids, common_stock_only, classify_security
from finmind_client import _fetch

import audit_f52w_2007_data_quality as dq_mod

CHECKPOINT_PATH = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"
OOS_START, OOS_END = "2007-01-01", "2014-12-31"
OUT_JSON = Path(__file__).parent / "data" / "exam_2007_2014_data_gate.json"


def _load_info_lookup() -> dict[str, dict]:
    """跟`audit_universe_composition_val.py::_load_info_lookup()`同一套
    兩層來源邏輯（TaiwanStockInfo權威來源＋universe()補早期下市股名稱），
    這裡獨立重寫一份小版本，避免import一支主要用途是VAL期稽核的腳本。"""
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    lookup = info.set_index("stock_id")[["stock_name", "industry_category"]].to_dict("index")
    from universe import universe as build_universe
    combined = build_universe()
    for _, row in combined.iterrows():
        sid = row["stock_id"]
        if sid not in lookup:
            lookup[sid] = {"stock_name": row["stock_name"], "industry_category": row.get("industry_category")}
    return lookup


def item1_and_6_price_coverage(successful_ids: list[str], info_lookup: dict[str, dict]) -> dict:
    """項目1（價格可用檔數＋2007-2008下市股檔數）與項目6（限普通股後的
    同一組統計）合併計算，因為兩者都需要逐檔載入價格序列確認2007-2014
    區間內有實際資料列，載入一次共用。"""
    delisted = delisted_stock_ids()  # cutoff=2003-01-01預設，含delist_date欄位
    delisted_lookup = delisted.set_index("stock_id")["delist_date"].to_dict()

    available_ids = []
    for sid in successful_ids:
        px = adjusted_price_series(sid, "2006-01-01")
        if px.empty:
            continue
        px = px[(pd.to_datetime(px["date"]) >= pd.Timestamp(OOS_START)) &
                 (pd.to_datetime(px["date"]) <= pd.Timestamp(OOS_END))]
        if not px.empty and px["adj_close"].notna().any():
            available_ids.append(sid)

    def _delisted_in_2007_2008(ids: list[str]) -> list[str]:
        out = []
        for sid in ids:
            dd = delisted_lookup.get(sid)
            if dd is not None and "2007-01-01" <= str(dd) <= "2008-12-31":
                out.append(sid)
        return out

    delisted_2007_2008 = _delisted_in_2007_2008(available_ids)

    common_ids = [sid for sid in available_ids
                  if classify_security(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                        (info_lookup.get(sid) or {}).get("industry_category")) == "普通股"]
    common_delisted_2007_2008 = _delisted_in_2007_2008(common_ids)

    return {
        "n_available_2007_2014": len(available_ids),
        "n_delisted_2007_2008_among_available": len(delisted_2007_2008),
        "delisted_2007_2008_ids": sorted(delisted_2007_2008),
        "n_common_stock_available_2007_2014": len(common_ids),
        "n_common_stock_delisted_2007_2008": len(common_delisted_2007_2008),
        "common_stock_delisted_2007_2008_ids": sorted(common_delisted_2007_2008),
        "available_ids": sorted(available_ids),
    }


def item2_zero_price_ratio(successful_ids: list[str]) -> dict:
    total_rows = 0
    total_nan = 0
    residual_nonpositive = 0
    per_stock_ratio = {}
    for sid in successful_ids:
        px = adjusted_price_series(sid, "2006-01-01")
        if px.empty:
            continue
        w = px[(pd.to_datetime(px["date"]) >= pd.Timestamp(OOS_START)) &
               (pd.to_datetime(px["date"]) <= pd.Timestamp(OOS_END))]
        if w.empty:
            continue
        n = len(w)
        n_nan = int(w["adj_close"].isna().sum())
        n_bad = int((w["adj_close"] <= 0).sum())  # 應恆為0，見_mask_non_positive_adj_prices()
        total_rows += n
        total_nan += n_nan
        residual_nonpositive += n_bad
        if n:
            per_stock_ratio[sid] = round(n_nan / n, 4)
    return {
        "total_price_rows_2007_2014": total_rows,
        "total_nan_adj_close_2007_2014": total_nan,
        "nan_ratio_2007_2014": round(total_nan / total_rows, 4) if total_rows else None,
        "residual_nonpositive_leftover": residual_nonpositive,  # 必須=0，否則_mask_non_positive_adj_prices()本身有缺陷
        "max_per_stock_nan_ratio": max(per_stock_ratio.values()) if per_stock_ratio else None,
    }


def item3_dividend_nan_check(successful_ids: list[str]) -> dict:
    rows = [dq_mod.audit_one_stock(sid) for sid in successful_ids]
    df = pd.DataFrame(rows)
    flagged = df[df["verdict"].astype(str).str.contains("推論成立", na=False)]
    n_dividend_cache_missing = int((~df["dividend_cache_exists"]).sum())
    return {
        "n_audited": len(df),
        "n_flagged_has_records_all_nan": len(flagged),
        "flagged_stock_ids": sorted(flagged["stock_id"].tolist()),
        "n_dividend_cache_missing": n_dividend_cache_missing,
        "dividend_cache_missing_ids": sorted(df.loc[~df["dividend_cache_exists"], "stock_id"].tolist()),
    }


def item4_benchmark_coverage() -> dict:
    prices = load_0050_full_history()
    eq = prices.rename(columns={"adj_close": "equity"})[["date", "equity"]]
    covers_full_window = (pd.to_datetime(prices["date"]).min() <= pd.Timestamp(OOS_START) and
                           pd.to_datetime(prices["date"]).max() >= pd.Timestamp(OOS_END))
    mdd_2008 = segment_mdd(eq, "2008-01-01", "2008-12-31")
    return {
        "covers_2007_2014_full_window": bool(covers_full_window),
        "date_range": [str(prices["date"].min().date()), str(prices["date"].max().date())],
        "mdd_2008_pct": round(mdd_2008, 2) if mdd_2008 is not None else None,
        "mdd_2008_consistent_with_public_data": bool(mdd_2008 is not None and mdd_2008 <= -50.0),
    }


def main():
    print("=== 閘門.一：開考前資料品質閘門（六項，零新增API呼叫）===", flush=True)
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    ckpt = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    fetched = ckpt["fetched_ids"]
    failed = ckpt.get("failed_ids", {})
    successful = [sid for sid in fetched if sid not in failed]
    print(f"checkpoint: 300樣本中fetched={len(fetched)}  failed={len(failed)}  successful={len(successful)}", flush=True)

    info_lookup = _load_info_lookup()

    print("\n--- 項目1+6：價格可用檔數／2007-2008下市股檔數／限普通股後同一組統計 ---", flush=True)
    i1_6 = item1_and_6_price_coverage(successful, info_lookup)
    print(f"  可用檔數={i1_6['n_available_2007_2014']}  其中2007-2008下市={i1_6['n_delisted_2007_2008_among_available']}檔", flush=True)
    print(f"  限普通股後可用檔數={i1_6['n_common_stock_available_2007_2014']}  "
          f"其中2007-2008下市普通股={i1_6['n_common_stock_delisted_2007_2008']}檔", flush=True)

    print("\n--- 項目2：零價格(adj_close<=0)轉NaN比例 ---", flush=True)
    i2 = item2_zero_price_ratio(successful)
    print(f"  總列數={i2['total_price_rows_2007_2014']}  NaN列數={i2['total_nan_adj_close_2007_2014']}"
          f"  比例={i2['nan_ratio_2007_2014']}  殘留<=0未轉NaN={i2['residual_nonpositive_leftover']}(須=0)", flush=True)

    print("\n--- 項目3：股利率NaN檢查（「有除息紀錄但股利率全NaN」須為0檔）---", flush=True)
    i3 = item3_dividend_nan_check(successful)
    print(f"  稽核{i3['n_audited']}檔，flagged={i3['n_flagged_has_records_all_nan']}檔"
          f"（須=0）：{i3['flagged_stock_ids']}", flush=True)
    print(f"  股利快取缺失={i3['n_dividend_cache_missing']}檔：{i3['dividend_cache_missing_ids']}", flush=True)

    print("\n--- 項目4：0050基準覆蓋＋2008 MDD ---", flush=True)
    i4 = item4_benchmark_coverage()
    print(f"  覆蓋2007-2014全段={i4['covers_2007_2014_full_window']}  範圍={i4['date_range']}  "
          f"2008 MDD={i4['mdd_2008_pct']}%（須<=-50%）={i4['mdd_2008_consistent_with_public_data']}", flush=True)

    # ── 六項綜合判定 ──
    gate1_pass = i1_6["n_available_2007_2014"] > 0 and i1_6["n_delisted_2007_2008_among_available"] > 0
    gate2_pass = i2["residual_nonpositive_leftover"] == 0
    gate3_pass = i3["n_flagged_has_records_all_nan"] == 0
    gate4_pass = i4["covers_2007_2014_full_window"] and i4["mdd_2008_consistent_with_public_data"]
    gate6_pass = i1_6["n_common_stock_available_2007_2014"] > 0 and i1_6["n_common_stock_delisted_2007_2008"] > 0
    all_pass = gate1_pass and gate2_pass and gate3_pass and gate4_pass and gate6_pass

    print(f"\n=== 綜合判定：{'全部通過，可執行單發檢定' if all_pass else '未全數通過，不得執行單發檢定'} ===", flush=True)
    print(f"  項目1(價格+2007-2008下市)={'PASS' if gate1_pass else 'FAIL'}  "
          f"項目2(零價格已轉NaN)={'PASS' if gate2_pass else 'FAIL'}  "
          f"項目3(股利無NaN殘留)={'PASS' if gate3_pass else 'FAIL'}  "
          f"項目4(0050基準)={'PASS' if gate4_pass else 'FAIL'}  "
          f"項目6(限普通股後仍>0)={'PASS' if gate6_pass else 'FAIL'}", flush=True)

    out = {
        "generated_for": "閘門.一（2026-09-24裁示【候選名單定案】＋【開考前修正】閘門.一補充）",
        "note": "只讀既有快取（資料.一已完成的300檔fetch），零新增API呼叫，未呼叫register_trial()。",
        "sample_size": len(sample_ids), "n_fetched": len(fetched), "n_failed": len(failed),
        "n_successful": len(successful),
        "item1_price_and_delisted": {k: v for k, v in i1_6.items() if k != "available_ids"},
        "item2_zero_price": i2,
        "item3_dividend_nan": i3,
        "item4_benchmark": i4,
        "item6_common_stock_only": {
            "n_common_stock_available_2007_2014": i1_6["n_common_stock_available_2007_2014"],
            "n_common_stock_delisted_2007_2008": i1_6["n_common_stock_delisted_2007_2008"],
            "common_stock_delisted_2007_2008_ids": i1_6["common_stock_delisted_2007_2008_ids"],
        },
        "gate_verdicts": {
            "item1_pass": gate1_pass, "item2_pass": gate2_pass, "item3_pass": gate3_pass,
            "item4_pass": gate4_pass, "item6_pass": gate6_pass, "all_pass": all_pass,
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON}", flush=True)
    return out


if __name__ == "__main__":
    main()
