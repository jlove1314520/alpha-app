# -*- coding: utf-8 -*-
"""驗.六第一、二點：#398/#399資料路徑普查＋修正後診斷重算（2026-09-27
總司令裁示【驗.六：資料修正後的影響重估（診斷，不改任何判定）】）。

**這是診斷，不是重跑判定**：#398/#399/#400以及所有既有判定一律鎖定，
本腳本產生的數字只標「診斷值，判定鎖定」，不寫進`TRIALS_LEDGER.md`
新編號，只在該檔案#398/#399列附註一行指向`research/data/diag_v6_
398_399.json`。

方法：用**當前**（已含修.六/查.二/查.三/修.七四項修正的）`adjust.py`／
`universe.py`，呼叫跟登記#398/#399時完全相同的`single_shot_2007_2014_
test.py::load_common_stock_data_2007_2014()`/`run_single_shot()`，
重新載入資料、重新跑一次確定性回測，跟H.一驗.五時建立的「重建非重跑」
合規模式相同——但這裡**不要求**跟原始登記數字逐位元一致（原始登記
數字本來就是用未修正的舊資料算出來的，重建的目的正是要看修正後差多
少，不是要驗證重建正確性），所以不做bit-for-bit核對，直接呈現對照表。

輸出：`research/data/diag_v6_398_399.json`
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

import single_shot_2007_2014_test as sst
import f52w_high_portfolio_v1 as f52w_mod
import dividend_yield_portfolio_v1 as div_mod
from adjust import adjusted_price_series, adjustment_events

OUT = Path(__file__).parent / "data" / "diag_v6_398_399.json"

REGISTERED = {
    "f52w_high_portfolio_v1": {
        "n_trades": 919, "candidate_return_pct_2007_2014": 113.91, "mdd_full_period_pct": -47.14,
        "mdd_2008_pct": -47.14, "ir_annualized": 0.5783734876238544, "one_tailed_p": 0.061108408841473526,
    },
    "dividend_yield_portfolio_v1": {
        "n_trades": 579, "candidate_return_pct_2007_2014": 203.87, "mdd_full_period_pct": -53.72,
        "mdd_2008_pct": -53.72, "ir_annualized": 0.8318645768938427, "one_tailed_p": 0.012821491737059402,
    },
}


def data_path_census(sample_ids: list[str]) -> dict:
    """項一：股票×日數中yfinance vs FinMind路徑比例，以及FinMind路徑中
    碰到股票股利/現金增資事件的股票數。"""
    n_rows_yfinance, n_rows_finmind = 0, 0
    n_stocks_yfinance, n_stocks_finmind = 0, 0
    n_finmind_with_stock_dividend_or_cash_increase = 0
    per_stock = []
    for sid in sample_ids:
        try:
            px = adjusted_price_series(sid, sst.EXTENDED_START)
        except Exception as e:  # noqa: BLE001
            per_stock.append({"stock_id": sid, "error": str(e)})
            continue
        if px.empty or "source" not in px.columns:
            continue
        src = px["source"].iloc[0] if len(px) else None
        n = len(px)
        if src == "yfinance":
            n_rows_yfinance += n
            n_stocks_yfinance += 1
        elif src == "finmind":
            n_rows_finmind += n
            n_stocks_finmind += 1
            try:
                ev = adjustment_events(sid, sst.EXTENDED_START)
                has_event = bool(len(ev)) and (
                    (ev["stock_ratio"].fillna(0) != 0).any() if "stock_ratio" in ev.columns else False
                )
                # stock_ratio欄位只涵蓋股利事件的股票股利比率；現金增資的rights_ratio
                # 沒有單獨留在合併後的events表裡（已併入factor本身），改用event_type欄位
                # 判斷是否含dividend類事件且該事件本身非純現金股利（即有stock_ratio或
                # 是靠rights_ratio觸發的，這裡採保守寬鬆認定：只要有dividend類事件就算
                # 「可能碰到股票股利或現金增資」，因為兩者都走同一個事件類型，如實揭露
                # 這個粒度限制，不假裝能百分之百精確拆分）。
                has_dividend_type = bool(len(ev)) and "event_type" in ev.columns and \
                    (ev["event_type"] == "dividend").any()
                if has_dividend_type:
                    n_finmind_with_stock_dividend_or_cash_increase += 1
            except Exception:  # noqa: BLE001
                pass
        per_stock.append({"stock_id": sid, "source": src, "n_rows": n})

    total_rows = n_rows_yfinance + n_rows_finmind
    return {
        "n_stocks_yfinance": n_stocks_yfinance, "n_stocks_finmind": n_stocks_finmind,
        "n_rows_yfinance": n_rows_yfinance, "n_rows_finmind": n_rows_finmind,
        "pct_rows_yfinance": round(n_rows_yfinance / total_rows * 100, 2) if total_rows else None,
        "pct_rows_finmind": round(n_rows_finmind / total_rows * 100, 2) if total_rows else None,
        "n_finmind_stocks_with_dividend_type_event": n_finmind_with_stock_dividend_or_cash_increase,
        "note": "「股票股利或現金增資事件」用adjustment_events()的event_type=='dividend'"
                "粗粒度判斷(該事件類型同時涵蓋現金股利/股票股利/現金增資三種，資料本身"
                "沒有更細的拆分)，如實揭露這是寬鬆上界估計，不是精確只算股票股利/現金"
                "增資兩種的數字。",
    }


def main() -> None:
    print("[驗.六] 載入#398/#399共用資料（含修.六/查.二/查.三/修.七四項修正）...", flush=True)
    data, market_df, industry_map, liquidity, n_common = sst.load_common_stock_data_2007_2014()
    sample_ids = list(data.keys())

    print("\n[驗.六項一] 資料路徑普查...", flush=True)
    census = data_path_census(sample_ids)
    print(f"  yfinance: {census['n_stocks_yfinance']}檔/{census['n_rows_yfinance']}列"
          f"（{census['pct_rows_yfinance']}%）", flush=True)
    print(f"  FinMind:  {census['n_stocks_finmind']}檔/{census['n_rows_finmind']}列"
          f"（{census['pct_rows_finmind']}%），其中{census['n_finmind_stocks_with_dividend_type_event']}"
          f"檔碰到股利類事件", flush=True)

    print("\n[驗.六項二] #398/#399診斷重算（修正後資料層，判定鎖定）...", flush=True)
    diag_results = {}
    for mod, label in ((f52w_mod, "f52w_high_portfolio_v1"), (div_mod, "dividend_yield_portfolio_v1")):
        out = sst.run_single_shot(mod, data, market_df, industry_map, liquidity, label)
        reg = REGISTERED[label]
        diag = {
            "diagnostic_value_verdict_locked": True,
            "registered": reg,
            "diag_v6_corrected": {
                "n_trades": out["n_trades"],
                "candidate_return_pct_2007_2014": out["candidate_return_pct_2007_2014"],
                "mdd_full_period_pct": out["mdd_full_period_pct"],
                "mdd_2008_pct": out["mdd_2008_pct"],
                "ir_annualized": out["ir_test"]["ir_annualized"],
                "one_tailed_p": out["ir_test"]["one_tailed_p"],
            },
            "delta": {
                "n_trades": out["n_trades"] - reg["n_trades"],
                "candidate_return_pct_2007_2014": round(out["candidate_return_pct_2007_2014"] - reg["candidate_return_pct_2007_2014"], 2),
                "mdd_full_period_pct": round(out["mdd_full_period_pct"] - reg["mdd_full_period_pct"], 2),
                "mdd_2008_pct": round(out["mdd_2008_pct"] - reg["mdd_2008_pct"], 2),
                "ir_annualized": round(out["ir_test"]["ir_annualized"] - reg["ir_annualized"], 4),
                "one_tailed_p": round(out["ir_test"]["one_tailed_p"] - reg["one_tailed_p"], 4),
            },
            "gate_ir_pass_diag": out["gate_ir_pass"], "gate_mdd_2008_pass_diag": out["gate_mdd_2008_pass"],
            "gate_mdd_full_pass_diag": out["gate_mdd_full_pass"], "overall_verdict_diag_only": out["overall_verdict"],
        }
        diag_results[label] = diag
        print(f"  {label}：報酬{reg['candidate_return_pct_2007_2014']:+.2f}%→"
              f"{out['candidate_return_pct_2007_2014']:+.2f}%，"
              f"IR {reg['ir_annualized']:+.4f}→{out['ir_test']['ir_annualized']:+.4f}，"
              f"單尾p {reg['one_tailed_p']:.4f}→{out['ir_test']['one_tailed_p']:.4f}，"
              f"診斷判定(不影響鎖定判定)={out['overall_verdict']}", flush=True)

    OUT.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "verdict_locked_note": "本檔案全部數字為診斷值，#398/#399/#400判定一律鎖定不變，"
                                "兩個候選已判FAIL，本次診斷不會讓任何一個翻盤成PASS。",
        "n_common_universe": n_common, "n_usable": len(data),
        "data_path_census": census,
        "results": diag_results,
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n已寫入 {OUT}")


if __name__ == "__main__":
    main()
