"""驗.二續（總司令2026-09-24裁示【value_board 翻案處理＋轉向.一 候選名單
定案＋FinLab 借鏡登記】）：spillover開盤到收盤版，走完整第2-9關。

**背景**：`spillover_overlay_v1.py`（close-to-close版，#346）已判FAIL——
不是統計不顯著，是前視偏誤：台股收盤到收盤報酬乘上「美股t日訊號決定的
曝險」，但美股t日訊號要等台股t-1收盤後（美股當晚交易時段）才完全確定，
用收盤到收盤報酬回測等於讓策略看到了實際交易時看不到的隔夜跳空報酬。
`spillover_overnight_gate.py::build_aligned_series_o2c()`（#386，cheap gate
地基）已修正這個問題，改用「台股t日開盤到收盤」報酬（訊號在當日開盤前
已知，可合法套用在整個交易時段），並誠實診斷出：原#346量到的84.9%相關性
其實活在無法交易的跳空裡，開盤到收盤版本身只剩較弱訊號（TRAIN r=0.058／
VAL r=0.25，前後期不穩定）。#386只完成cheap gate＋跳空診斷，本檔案接續
走完整第2~9關才能做最終PASS/FAIL判定。

**重用範圍（不重寫，直接import）**：`build_overlay()`／`apply_costs()`／
`_switch_cost_pct()`（已用ETF稅率`tax_rate("etf")`=0.1%，修.二既有修正）／
gate2~gate9 全部函式，全部原封不動沿用`spillover_overlay_v1.py`——唯一
差異是資料來源換成`spillover_overnight_gate.build_aligned_series_o2c()`
（`tw_ret`欄位定義從close-to-close換成open-to-close，欄位名相同，下游
函式不需要任何修改就能重用，見該函式docstring）。

**每日切換換手成本明列（裁示原文第4關要求）**：THRESHOLD=0.0代表美股
當日收盤只要收黑就觸發降曝險，經驗上非常接近逐日切換，`gate4_cost_
sensitivity()`原本只報總報酬在1x/2x/3x下的數字，這裡額外加一段換手
成本統計（平均每次切換的成本%、年化換手成本%、切換頻率），讓「頻繁
切換的成本有多重」這件事在報告裡直接看得到，不用從總報酬倒推。

用法：python research/spillover_overlay_v1_o2c.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import pandas as pd

from spillover_overlay_v1 import (
    THRESHOLD, EXPOSURE_DOWN, EXPOSURE_UP,
    build_overlay, apply_costs, _switch_cost_pct, _split, _metrics,
    gate2_random_control, gate3_parameter_plateau, gate5_leave_one_out,
    gate6_yearly_consistency, gate4_cost_sensitivity, gate8_alpha_decomposition,
    gate9_downside_protection,
)
from spillover_overnight_gate import build_aligned_series_o2c, _daily_returns
from validation.holdout import TRAIN_END, VAL_END

OUT_JSON = Path(__file__).parent / "data" / "spillover_overlay_v1_o2c_result.json"


def turnover_cost_detail(d: pd.DataFrame, label: str, mult: float = 1.0) -> dict:
    """裁示原文明確要求：每日切換的換手成本要在第4關明列，不只報總報酬。"""
    dd = d.copy()
    dd["cost_pct"] = dd["exposure_change"].apply(lambda dc: _switch_cost_pct(dc, mult=mult))
    n_days = len(dd)
    n_switches = int((dd["exposure_change"] != 0).sum())
    total_cost_pct = float(dd["cost_pct"].sum()) * 100
    avg_cost_per_switch_pct = float(dd.loc[dd["exposure_change"] != 0, "cost_pct"].mean() * 100) if n_switches else 0.0
    years = n_days / 252.0
    annualized_cost_pct = total_cost_pct / years if years > 0 else float("nan")
    switch_freq_pct = 100.0 * n_switches / n_days if n_days else float("nan")
    print(f"  {label}（{mult}x成本）：{n_days}個交易日中{n_switches}次切換（切換頻率={switch_freq_pct:.1f}%）、"
          f"累積換手成本={total_cost_pct:.2f}%、年化換手成本≈{annualized_cost_pct:.2f}%/年、"
          f"平均每次切換成本={avg_cost_per_switch_pct:.4f}%", flush=True)
    return {
        "label": label, "mult": mult, "n_days": n_days, "n_switches": n_switches,
        "switch_freq_pct": switch_freq_pct, "total_turnover_cost_pct": total_cost_pct,
        "annualized_turnover_cost_pct": annualized_cost_pct,
        "avg_cost_per_switch_pct": avg_cost_per_switch_pct,
    }


def main() -> dict:
    t0 = time.time()
    print("載入台美股指數對齊資料（開盤到收盤版，沿用#386"
          "spillover_overnight_gate.build_aligned_series_o2c()）...", flush=True)
    aligned = build_aligned_series_o2c()
    tw_close = _daily_returns("^TWII")[["date", "close"]]

    aligned_train_raw, aligned_val_raw = _split(aligned)
    tw_close_train = tw_close[tw_close["date"] <= pd.Timestamp(TRAIN_END)].reset_index(drop=True)
    tw_close_val = tw_close[(tw_close["date"] > pd.Timestamp(TRAIN_END)) & (tw_close["date"] <= pd.Timestamp(VAL_END))].reset_index(drop=True)
    print(f"  TRAIN(<= {TRAIN_END}): n={len(aligned_train_raw)}  VAL({TRAIN_END}~{VAL_END}): n={len(aligned_val_raw)}", flush=True)

    d_train = apply_costs(build_overlay(aligned_train_raw), mult=1.0)
    d_val = apply_costs(build_overlay(aligned_val_raw), mult=1.0)

    print(f"\n錨點參數：THRESHOLD={THRESHOLD}  EXPOSURE_DOWN={EXPOSURE_DOWN}  EXPOSURE_UP={EXPOSURE_UP}"
          f"（開盤到收盤版，成本一律ETF稅率0.1%）", flush=True)
    train_m = _metrics(d_train["overlay_return_net"])
    val_m = _metrics(d_val["overlay_return_net"])
    train_base_m = _metrics(d_train["tw_ret"])
    val_base_m = _metrics(d_val["tw_ret"])
    print(f"  TRAIN: overlay報酬={train_m['total_return_pct']:+.2f}%  baseline(開盤到收盤買進持有)={train_base_m['total_return_pct']:+.2f}%", flush=True)
    print(f"  VAL:   overlay報酬={val_m['total_return_pct']:+.2f}%  baseline(開盤到收盤買進持有)={val_base_m['total_return_pct']:+.2f}%", flush=True)

    gate2_train = gate2_random_control(d_train, "TRAIN")
    gate2_val = gate2_random_control(d_val, "VAL")

    gate3 = gate3_parameter_plateau(aligned_train_raw)
    if not gate3["pass"]:
        result = {"final_gate": 3, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val, "gate3": gate3,
                   "train_metrics": train_m, "val_metrics": val_m,
                   "train_baseline_metrics": train_base_m, "val_baseline_metrics": val_base_m}
        print(f"\n**第3關參數高原未過，快殺判定FAIL，不進第5關以後。**（耗時{time.time()-t0:.1f}s）", flush=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return result

    gate5 = gate5_leave_one_out(d_train)
    if not gate5["pass"]:
        result = {"final_gate": 5, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val,
                   "gate3": gate3, "gate5": gate5,
                   "train_metrics": train_m, "val_metrics": val_m,
                   "train_baseline_metrics": train_base_m, "val_baseline_metrics": val_base_m}
        print(f"\n**第5關leave-one-out未過，快殺判定FAIL，不進第6關以後。**（耗時{time.time()-t0:.1f}s）", flush=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return result

    gate6 = gate6_yearly_consistency(d_train)
    if not gate6["pass"]:
        result = {"final_gate": 6, "verdict": "FAIL", "gate2_train": gate2_train, "gate2_val": gate2_val,
                   "gate3": gate3, "gate5": gate5, "gate6": gate6,
                   "train_metrics": train_m, "val_metrics": val_m,
                   "train_baseline_metrics": train_base_m, "val_baseline_metrics": val_base_m}
        print(f"\n**第6關逐年一致性未過，快殺判定FAIL，不進第7關以後。**（耗時{time.time()-t0:.1f}s）", flush=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return result

    gate4 = gate4_cost_sensitivity(aligned_train_raw, aligned_val_raw)
    print("\n" + "=" * 70)
    print("第4關附加：每日切換換手成本明列（裁示原文要求）")
    print("=" * 70)
    turnover_train = turnover_cost_detail(d_train, "TRAIN", mult=1.0)
    turnover_val = turnover_cost_detail(d_val, "VAL", mult=1.0)
    gate4["turnover_detail"] = {"TRAIN": turnover_train, "VAL": turnover_val}

    gate8 = gate8_alpha_decomposition(d_train, d_val, tw_close_train, tw_close_val)
    gate9 = gate9_downside_protection(d_train, d_val)

    val_alpha_significant = bool(gate8["VAL"]["alpha_significant"])
    val_downside_ok = bool(gate9["VAL"]["mdd_improved"])
    verdict = "PASS" if (val_alpha_significant and val_downside_ok) else "FAIL"

    print("\n" + "=" * 70)
    print(f"最終判定：{verdict}")
    print(f"  VAL alpha顯著為正: {val_alpha_significant} (p={gate8['VAL']['alpha_pvalue']:.4f})")
    print(f"  VAL下檔保護(MDD改善): {val_downside_ok}")
    print("=" * 70)

    result = {"final_gate": 9, "verdict": verdict, "gate2_train": gate2_train, "gate2_val": gate2_val,
              "gate3": gate3, "gate4": gate4, "gate5": gate5, "gate6": gate6, "gate8": gate8, "gate9": gate9,
              "train_metrics": train_m, "val_metrics": val_m,
              "train_baseline_metrics": train_base_m, "val_baseline_metrics": val_base_m}
    print(f"\n(耗時{time.time()-t0:.1f}s)", flush=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"已寫入 {OUT_JSON}", flush=True)
    return result


if __name__ == "__main__":
    main()
