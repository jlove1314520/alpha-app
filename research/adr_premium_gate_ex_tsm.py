"""`HYPOTHESIS_QUEUE.md` #45 存託憑證（ADR）溢價/折價收斂 第1關cheap gate

——排除TSM對照重跑（第1關CHEAP_PASS後「下一輪待辦(a)」）。

背景：`adr_premium_gate.py`跑出的pooled CHEAP_PASS，逐檔拆解揭露VAL期
只有TSM(+0.1380,p=0.0000)與ASX(+0.1114,p=0.0006)顯著同號，UMC/CHT兩者
VAL期皆不顯著（UMC p=0.4967、CHT p=0.6296且方向反轉）。本腳本回答#45
「下一輪待辦(a)」：**排除TSM，只用UMC+CHT+ASX三檔pooled重跑**，檢驗
訊號是否幾乎完全消失（若消失＝「單一巨型股擇時」而非「ADR收斂機制
普遍存在」，依快殺標準提早收斂判死）。

完全複用`adr_premium_gate.py`既有的`build_panel()`/`_split()`/`evaluate()`
（含逐標的內部洗牌null設計），只多一個「排除TSM」的panel過濾步驟，不
重寫任何既有邏輯，避免兩份程式碼分岔。

2026-09-06 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#45第1關
深挖，尚未最終結案（本輪僅完成待辦(a)，(b)/(c)留待下一輪視結果決定）。
"""
from __future__ import annotations

from adr_premium_gate import M_TARGET_DAYS, N_SHUFFLE, SHUFFLE_SEED, MIN_SAMPLE
from adr_premium_gate import build_panel, _split, evaluate


def main() -> dict:
    print("=== #45 ADR premium 第1關cheap gate ——排除TSM對照重跑 ===")
    panel = build_panel()
    before_n = len(panel)
    panel_ex_tsm = panel[panel["ticker"] != "TSM"].reset_index(drop=True)
    print(f"排除前panel總列數: {before_n}, 標的: {sorted(panel['ticker'].unique())}")
    print(f"排除TSM後panel總列數: {len(panel_ex_tsm)}, 標的: {sorted(panel_ex_tsm['ticker'].unique())}")

    train, val = _split(panel_ex_tsm)
    print(f"\nTRAIN(排除TSM): n={len(train)}  VAL(排除TSM): n={len(val)}")
    print(f"TRAIN逐標的列數: {train['ticker'].value_counts().to_dict()}")
    print(f"VAL逐標的列數: {val['ticker'].value_counts().to_dict()}")

    if len(train) < MIN_SAMPLE or len(val) < MIN_SAMPLE:
        print(f"\n樣本數過少（<{MIN_SAMPLE}），判定FAIL（結構性資料不足）")
        return {"verdict": "FAIL", "reason": "insufficient_sample_ex_tsm",
                "train_n": len(train), "val_n": len(val)}

    train_result = evaluate(train, "TRAIN 排除TSM (UMC+CHT+ASX)")
    val_result = evaluate(val, "VAL 排除TSM (UMC+CHT+ASX)")

    same_sign = (train_result["pearson"] > 0) == (val_result["pearson"] > 0)
    nontrivial = abs(train_result["pearson"]) > 0.01 and abs(val_result["pearson"]) > 0.01
    beats_null = val_result["null_percentile"] >= 90.0
    matches_expected_direction = val_result["pearson"] > 0

    print("\n=== 排除TSM後三項判準（跟原始pooled同一套框架） ===")
    print(f"  1. 幅度非零 (|r|>0.01兩期): {nontrivial}")
    print(f"  2. train/val同號: {same_sign} (TRAIN r={train_result['pearson']:+.4f}, "
          f"VAL r={val_result['pearson']:+.4f})")
    print(f"  3. VAL贏過逐標的內部洗牌null(percentile>=90.0): {beats_null} "
          f"(percentile={val_result['null_percentile']:.1f})")
    print(f"  （附註）VAL方向是否符合事前預期(正相關): {matches_expected_direction}")

    verdict = "CHEAP_PASS" if (same_sign and nontrivial and beats_null) else "FAIL"
    print(f"\n判定(排除TSM): {verdict}")

    return {"train": train_result, "val": val_result, "verdict": verdict,
            "matches_expected_direction": matches_expected_direction}


if __name__ == "__main__":
    main()
