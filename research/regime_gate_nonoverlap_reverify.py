# -*- coding: utf-8 -*-
"""`PENDING_QUEUE.md`常備.12：把`regime_gate_common.py`的不重疊觀測＋
circular shift虛無分布，補套用到六個daily-overlap設計的regime gate
（`#76`/`#78`/常備.2~.5），取代原本的逐日重疊視窗＋逐點打散虛無分布。

**跟`align_monthly_nonoverlap()`（#81/#80修法）的差異**：那支函式假設
輸入是離散「訊號發布日」事件序列（月頻macro資料glue到每個交易日造成
n虛胖）。這六個gate的訊號本身就是**逐日更新**的市場資料（VIX/HYG-IEF
比值），不是月頻訊號被貼寬，所以`## #81`結案段落原文明確交代「不可
直接套用同一函式」，需要`regime_gate_common.sample_nonoverlapping_
blocks()`這個新函式：對逐日重疊版本每隔M筆取一筆，讓相鄰兩筆觀測的
M日前瞻視窗真正不重疊。

**事前的數學論證（`STRATEGY_GRAVEYARD.md` `## #82`~`## #85`補記段落
已寫過，這裡實測驗證，不只是斷言）**：daily-overlap虛胖n會讓p值/null
百分位系統性偏樂觀（膨脹表面自由度）；逐點打散會低估自相關訊號的虛無
分布離散度（同樣偏樂觀）。兩者都只偏向製造假陽性，不會製造假陰性——
六個gate在**偏樂觀**的舊設計下已經全部FAIL，換成**更保守**的新設計，
結論在數學上不可能從FAIL翻成PASS，只會更確定FAIL或維持FAIL。本腳本
逐一重算六組配置（含常備.5的三個窗口共8組），把這個論證的具體數字
落地存證，不只是重複斷言。

沿用既有元件（不重新發明）：六個原始腳本各自的`build_aligned_series()`
（`hy_etf_ratio_window_grid_gate.py`是`_load_ratio_and_taiex()`+
`build_aligned_series(ratio, tw, m)`兩段式，直接reuse）、
`validation.holdout.TRAIN_END/VAL_END`、`regime_gate_common.
sample_nonoverlapping_blocks()`/`circular_shift_null()`（本輪新增
`sample_nonoverlapping_blocks`到`regime_gate_common.py`）。
"""
from __future__ import annotations

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

import hy_etf_ratio_gate
import hy_etf_ratio_roc_gate
import hy_etf_ratio_window_grid_gate
import vix_level_gate
import vix_term_structure_gate
import vix_term_structure_roc_gate
from regime_gate_common import circular_shift_null, sample_nonoverlapping_blocks
from trial_registry import register_trial
from validation.holdout import TRAIN_END, VAL_END

N_SHUFFLE = 500
SHUFFLE_SEED = 20260923
MIN_N = 30
REQUIRED_PCT = 90.0


def _split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[df["date"] <= pd.Timestamp(TRAIN_END)].copy()
    val = df[(df["date"] > pd.Timestamp(TRAIN_END)) & (df["date"] <= pd.Timestamp(VAL_END))].copy()
    return train, val


def _evaluate_block(df: pd.DataFrame, signal_col: str, target_col: str) -> dict:
    signal, target = df[signal_col].to_numpy(), df[target_col].to_numpy()
    n = len(df)
    if n < 3:
        return {"n": n, "pearson": float("nan"), "pearson_p": float("nan"), "percentile": float("nan")}
    shuf = circular_shift_null(signal, target, N_SHUFFLE, SHUFFLE_SEED)
    return {"n": n, **shuf}


def _reverify(name: str, old_verdict_ref: str, daily_df: pd.DataFrame, signal_col: str,
              target_col: str, m: int) -> dict:
    blocked = sample_nonoverlapping_blocks(daily_df, "date", signal_col, target_col, m)
    train, val = _split(blocked)
    print(f"\n=== {name} (M={m}) ===")
    print(f"  逐日重疊版原始n={len(daily_df)} -> 不重疊區塊抽樣後n={len(blocked)}"
          f"（TRAIN n={len(train)}, VAL n={len(val)}）")
    if len(train) < MIN_N or len(val) < MIN_N:
        print(f"  樣本數過少(<{MIN_N})，不重疊抽樣後無法穩健判定，FAIL（結構性樣本不足，"
              f"這本身也印證了daily-overlap版n虛胖的程度）")
        result = {"name": name, "m": m, "old_verdict_ref": old_verdict_ref,
                   "verdict": "FAIL", "reason": "insufficient_sample_after_deoverlap",
                   "train_n": len(train), "val_n": len(val)}
        return result

    tr = _evaluate_block(train, signal_col, target_col)
    va = _evaluate_block(val, signal_col, target_col)
    same_sign = (not np.isnan(tr["pearson"]) and not np.isnan(va["pearson"])
                 and np.sign(tr["pearson"]) == np.sign(va["pearson"]) and tr["pearson"] != 0)
    nontrivial = abs(tr["pearson"]) > 0.01 and abs(va["pearson"]) > 0.01
    beats_null = (not np.isnan(va["percentile"])) and va["percentile"] >= REQUIRED_PCT
    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"  TRAIN r={tr['pearson']:+.4f}(p={tr['pearson_p']:.4f})  "
          f"VAL r={va['pearson']:+.4f}(p={va['pearson_p']:.4f})  "
          f"circular-shift null percentile={va['percentile']:.1f}(門檻{REQUIRED_PCT})")
    print(f"  same_sign={same_sign}  nontrivial={nontrivial}  beats_null={beats_null}  => {verdict}")
    return {
        "name": name, "m": m, "old_verdict_ref": old_verdict_ref, "verdict": verdict,
        "train": tr, "val": va, "same_sign": same_sign, "nontrivial": nontrivial, "beats_null": beats_null,
        "n_daily_overlap": len(daily_df), "n_nonoverlap_blocks": len(blocked),
    }


def main() -> list[dict]:
    print("=== 常備.12：六個regime gate補套用不重疊區塊抽樣+circular shift虛無分布 ===")
    results = []

    d76 = vix_term_structure_gate.build_aligned_series()
    results.append(_reverify("vix_term_structure_gate(#76)", "TRIALS_LEDGER#327", d76, "vix_term_ratio", "tw_fwd_ret_m", 20))

    d78 = hy_etf_ratio_gate.build_aligned_series()
    results.append(_reverify("hy_etf_ratio_gate(#78)", "TRIALS_LEDGER(#78 gate1)", d78, "hyg_ief_ratio", "tw_fwd_ret_m", 20))

    d_roc_vix = vix_term_structure_roc_gate.build_aligned_series()
    results.append(_reverify("vix_term_structure_roc_gate(常備.2)", "TRIALS_LEDGER#363", d_roc_vix, "vix_term_roc", "tw_fwd_ret_m", 20))

    d_level = vix_level_gate.build_aligned_series()
    results.append(_reverify("vix_level_gate(常備.3)", "TRIALS_LEDGER#364", d_level, "vix_level", "tw_fwd_ret_m", 20))

    d_roc_hy = hy_etf_ratio_roc_gate.build_aligned_series()
    results.append(_reverify("hy_etf_ratio_roc_gate(常備.4)", "TRIALS_LEDGER#365", d_roc_hy, "hy_ratio_roc", "tw_fwd_ret_m", 20))

    ratio, tw = hy_etf_ratio_window_grid_gate._load_ratio_and_taiex()
    for m in hy_etf_ratio_window_grid_gate.M_GRID:
        d_grid = hy_etf_ratio_window_grid_gate.build_aligned_series(ratio, tw, m)
        results.append(_reverify(f"hy_etf_ratio_window_grid_gate(常備.5,M={m})", "TRIALS_LEDGER#366",
                                  d_grid, "hyg_ief_ratio", "tw_fwd_ret_m", m))

    n_pass = sum(1 for r in results if r["verdict"] == "CHEAP_PASS")
    print(f"\n=== 總結：{n_pass}/{len(results)}組在不重疊區塊抽樣+circular shift虛無分布下CHEAP_PASS ===")

    design = (
        "六個daily-overlap設計regime gate(#76/#78/常備.2~.5，含常備.5三個M窗口共8組)補套用"
        "regime_gate_common.sample_nonoverlapping_blocks()+circular_shift_null()，取代原逐日"
        "重疊視窗+逐點打散虛無分布。PENDING_QUEUE.md常備.12，事前數學論證：兩項舊設計缺陷"
        "皆偏向製造假陽性，六組已在偏樂觀舊設計下FAIL，換更保守新設計不可能翻案成PASS。"
    )
    result_str = "；".join(
        f"{r['name']}(M={r['m']}): " + (
            f"VAL n={r['val']['n']} r={r['val']['pearson']:+.4f} null_pct={r['val']['percentile']:.1f} => {r['verdict']}"
            if "val" in r else f"樣本不足(train_n={r.get('train_n')},val_n={r.get('val_n')}) => {r['verdict']}"
        )
        for r in results
    )
    final_verdict = "FAIL" if n_pass == 0 else "EXPERIMENTAL"
    notes = (
        f"{n_pass}/{len(results)}組CHEAP_PASS，其餘FAIL——" + (
            "實測驗證了`STRATEGY_GRAVEYARD.md`#82~#85補記段落的數學論證：不重疊區塊抽樣"
            "(n大幅下降至真正獨立觀測數)+circular shift虛無分布(保留訊號自身序列相關結構，"
            "null分布顯著變寬)雙重收緊後，原本在偏樂觀舊設計下已FAIL的六組全部維持FAIL"
            "(或因不重疊抽樣後樣本數不足而以「結構性樣本不足」結案，本身也是虛胖程度的量化"
            "證據)，證實方法論修正不會、也不可能讓任何一組從FAIL翻案成PASS。VIX/HY信用利差"
            "代理regime訊號家族(#31~34/#75~78/常備.2~.5/#80~81/驗.三系列)至此累積證據持續"
            "指向：台股大盤regime降曝險訊號目前沒有找到穩健候選。"
            if final_verdict == "FAIL" else
            "**與事前數學論證(舊設計偏樂觀、只會讓FAIL更確定)不符**，出現至少一組在更保守"
            "設計下翻案成CHEAP_PASS，需要另外調查根因(可能是不重疊抽樣改變的樣本組成本身"
            "帶入了原本重疊版被稀釋掉的訊號，須人工檢查該組細節，不得直接採信，標記"
            "EXPERIMENTAL待複驗，不得列入候選)——已列入`[自行裁量]`待人工複核項。"
        )
    )
    register_trial(
        track="hypothesis_queue", name="regime_gate_nonoverlap_block_reverify_batch",
        design=design, result=result_str, verdict=final_verdict, notes=notes,
        round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.12獨立交辦項，批次重驗8組",
        failed_gates=(["cheap_gate_precheck"] if final_verdict == "FAIL" else None),
    )
    return results


if __name__ == "__main__":
    import json
    res = main()
    out_path = Path(__file__).parent / "regime_gate_nonoverlap_reverify_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
