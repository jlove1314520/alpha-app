# -*- coding: utf-8 -*-
"""月營收SUE連續分數加權版（非二元閾值），`PENDING_QUEUE.md`常備.8。

**這條要填的具體缺口**：`STRATEGY_GRAVEYARD.md`「事件驅動SUE訊號」段落
（E1財報/E2月營收，`event_driven_prototype.py`/`event_driven_gate_sequence.py`）
的「不泛化成」明確列出「未測SUE連續分數加權（非二元閾值）」——但那個構造
本身有兩個獨立的既有前例，這支腳本要做的是**兩者都沒做過的第三個組合**：

1. `monthly_revenue_event_study.py`（`HYPOTHESIS_QUEUE.md`#14，2026-09-02
   已FAIL）**已經**測過連續分數（pooled Spearman IC，`revenue_sue`直接對
   `fwd_ret`），但**沒有**bucket中性化——同季度/同產業/同市值分位的系統性
   差異全部混進殘差，VAL期IC=+0.0204、null percentile=68.0（門檻90.0未過）。
2. `event_driven_prototype.py`（E2，2026-09-22已FAIL）**有**bucket控制
   （季度×產業×市值五分位），但只測二元「前10% vs 同bucket其餘」。

本腳本＝bucket中性化＋連續分數：在每個bucket內把`fwd20`減去bucket均值
（跟E2同一組bucket_key，直接重用`event_driven_prototype.build_event_table`
產出的事件表，不重新發明分bucket邏輯），消除掉#14缺少的季度/產業/市值
混雜因子後，再用連續SUE分數（非二元切點）對bucket中性化後的報酬算pooled
Spearman IC——這是「連續分數」與「bucket控制」第一次同時出現在同一個
檢定裡，是#14與E2各自的已知缺口的交集，不是重複測試。

**事前判斷（誠實記錄，非事後合理化）**：這個SUE訊號家族（月營收/財報SUE，
`方法.一/二/三`三條路線）截至2026-09-23已累積369次試驗全數FAIL/未過，
加上#14本身已對連續分數版本給出負面證據，本次事前預期PASS機率低——但
「已知動機不高」不等於「不用測」，`STRATEGY_GRAVEYARD.md`既有「不泛化成」
的文字明確把這個具體組合列為未測項目，且已被`PENDING_QUEUE.md`常備.8
正式排入佇列，此處誠實跑一次、誠實記錄結果。

沿用既有元件（不重新發明）：`event_driven_prototype.build_event_table`
（bucket_key構造）、`factor_ic.py`（樣本/日期常數）、
`monthly_revenue_event_study._permutation_null_percentile`（洗牌null，
同一套邏輯：全域打散`revenue_sue`↔`fwd_ret_neutral`配對關係，非逐bucket
打散——理由跟#14一致，這裡要檢定的虛無假設是「SUE分數本身跟bucket中性化
後報酬無關」，全域打散足以檢驗這個虛無假設；若要進一步控制bucket內部的
序列相關性，屬於下一步深挖，本次cheap gate等級不做）、`validation.holdout`
（TRAIN_END/VAL_END切分＋洩漏斷言）、`trial_registry.register_trial()`
（唯一登記入口）。

判定標準比照#14/E1/E2同一把cheap gate尺：①TRAIN/VAL同號 ②VAL |IC|贏過
500次洗牌null percentile>=90.0 ③樣本數門檻（比照#14的30筆下限）。
Standalone bonferroni_n=1（跟#14/#76~81等單一構造cheap gate同一慣例，
這是一個新的具體構造，不是既有試驗的重跑）。
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
from scipy.stats import spearmanr

from event_driven_prototype import EVENT_TYPES, build_event_table
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from monthly_revenue_event_study import _permutation_null_percentile
from trial_registry import register_trial
from validation import holdout

HORIZON = 20  # 對齊 event_driven_prototype.HORIZONS 與 monthly_revenue_event_study.FORWARD_HORIZON
N_PERMUTATIONS = 500
PERM_SEED = 20260923
BASE_ALPHA = 0.10
BONFERRONI_N = 1
MIN_N = 30  # 跟monthly_revenue_event_study.py同一個樣本數門檻


def _bucket_neutralize(events: pd.DataFrame, ret_col: str) -> pd.DataFrame:
    """在每個bucket_key內把ret_col減去bucket均值。bucket只有1筆事件時無法
    中性化（減自己等於0，會人工製造零變異），該bucket整批丟棄並記錄丟棄數，
    不得靜默保留單筆bucket（那會讓最終pooled相關性摻進恆為0的假資料點）。
    """
    counts = events.groupby("bucket_key")[ret_col].transform("size")
    usable = events[counts >= 2].copy()
    n_dropped = int(len(events) - len(usable))
    bucket_mean = usable.groupby("bucket_key")[ret_col].transform("mean")
    usable[f"{ret_col}_neutral"] = usable[ret_col] - bucket_mean
    return usable, n_dropped


def _period_stats(df: pd.DataFrame, label: str, ret_col: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p_value": float("nan")}
    rho, p = spearmanr(df["surprise"], df[ret_col])
    return {"label": label, "n": n, "ic": float(rho), "p_value": float(p)}


def main() -> dict:
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    spec = EVENT_TYPES["E2_月營收公布(SUE)"]
    print("=== 月營收SUE連續分數加權版（bucket中性化＋連續IC），PENDING_QUEUE.md常備.8 ===")
    print(f"Sample: {len(sample_ids)}檔 (SAMPLE_SEED={SAMPLE_SEED})，horizon=t+{HORIZON}，"
          f"standalone bonferroni_n={BONFERRONI_N}")

    events = build_event_table(sample_ids, spec["surprise_fn"], spec["surprise_col"], verbose=True)
    if events.empty:
        print("SANITY FAIL: 零事件，資料層級問題（不是市場沒訊號）。")
        out = {"passes": False, "reason": "no_events"}
        register_trial(
            track="hypothesis_queue",
            name="monthly_revenue_sue_continuous_bucket_v1",
            design="月營收SUE連續分數(非二元)+bucket中性化(季度x產業x市值五分位)pooled Spearman IC，"
                   "PENDING_QUEUE.md常備.8，填補#14(連續但無bucket控制)與E2(bucket控制但二元閾值)的交集缺口",
            result="零事件，資料層級問題，未能建立事件表",
            verdict="FAIL",
            notes="build_event_table回傳空表，跟資料抓取/解析有關，非訊號本身無效。",
            round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.8獨立交辦項，非馬拉松固定輪次編號",
            failed_gates=["unknown"],
        )
        return out

    ret_col = f"fwd{HORIZON}"
    events, n_dropped_single = _bucket_neutralize(events, ret_col)
    neutral_col = f"{ret_col}_neutral"
    print(f"\nbucket中性化：{len(events)}筆可用（單筆bucket丟棄{n_dropped_single}筆）")

    holdout.assert_no_holdout_leakage(events, date_col="entry_date", context="monthly_revenue_sue_continuous_bucket_v1 (final)")

    train = holdout.cap_to_train(events, date_col="entry_date")
    val = holdout.validation_slice(events, date_col="entry_date")
    n_months_train = train["entry_date"].astype(str).str.slice(0, 7).nunique() if not train.empty else 0
    n_months_val = val["entry_date"].astype(str).str.slice(0, 7).nunique() if not val.empty else 0
    print(f"TRAIN: {len(train)}筆事件跨{n_months_train}個不同月份 | VAL: {len(val)}筆事件跨{n_months_val}個不同月份")

    train_stats = _period_stats(train, "TRAIN", neutral_col)
    val_stats = _period_stats(val, "VAL", neutral_col)
    print(f"\nTRAIN pooled Spearman IC(bucket中性化)={train_stats['ic']:+.4f} (p={train_stats['p_value']:.4f}, n={train_stats['n']})")
    print(f"VAL   pooled Spearman IC(bucket中性化)={val_stats['ic']:+.4f} (p={val_stats['p_value']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )

    val_for_perm = val.rename(columns={"surprise": "revenue_sue", neutral_col: "fwd_ret"})
    null_pct = _permutation_null_percentile(val_for_perm, val_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"\nVAL |IC| vs {N_PERMUTATIONS}次洗牌null percentile={null_pct:.1f} (需要>={required_pct:.1f})")
    print(f"same_sign(TRAIN/VAL)={same_sign}")

    reasons = []
    if train_stats["n"] < MIN_N or val_stats["n"] < MIN_N:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")

    passes = len(reasons) == 0
    print(f"\n=== {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    out = {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign,
        "n_events_total": len(events), "n_dropped_single_bucket": n_dropped_single,
    }

    verdict = "CHEAP_PASS" if passes else "FAIL"
    design = (
        "月營收SUE連續分數(非二元)+bucket中性化(季度x產業x市值五分位)pooled Spearman IC，"
        f"horizon=t+{HORIZON}，N_SHUFFLE={N_PERMUTATIONS}，PENDING_QUEUE.md常備.8。"
        "填補#14(monthly_revenue_event_study.py，連續但無bucket控制，2026-09-02 FAIL)與"
        "E2(event_driven_gate_sequence.py，bucket控制但二元前10%閾值，2026-09-22 FAIL)"
        "各自缺口的交集，事件表/bucket_key直接重用event_driven_prototype.build_event_table。"
    )
    result = (
        f"{len(sample_ids)}檔樣本，事件表{len(events)}筆(單筆bucket丟棄{n_dropped_single}筆)，"
        f"TRAIN n={train_stats['n']}跨{n_months_train}月 IC={train_stats['ic']:+.4f}(p={train_stats['p_value']:.4f})，"
        f"VAL n={val_stats['n']}跨{n_months_val}月 IC={val_stats['ic']:+.4f}(p={val_stats['p_value']:.4f})，"
        f"same_sign={same_sign}，VAL null percentile={null_pct:.1f}(門檻{required_pct:.1f})"
    )
    notes = (
        f"三項判準：{'①幅度/樣本數過' if train_stats['n'] >= MIN_N and val_stats['n'] >= MIN_N else '①樣本數未過'}、"
        f"{'②train/val同號過' if same_sign else '②train/val正負號不一致未過'}、"
        f"{'③VAL贏過洗牌null過' if (not pd.isna(null_pct) and null_pct >= required_pct) else '③VAL贏過洗牌null未過'}。"
        + (f" 未過原因：{reasons}。" if reasons else " 三項判準全過。")
        + "此為SUE訊號家族(方法.一/二/三既有369次試驗)的延伸變體，同家族計數，非獨立訊號家族的第一次發現。"
    )
    register_trial(
        track="hypothesis_queue",
        name="monthly_revenue_sue_continuous_bucket_v1",
        design=design,
        result=result,
        verdict=verdict,
        notes=notes,
        round_note="DevQueue自走輪次20260923-131601，PENDING_QUEUE.md常備.8獨立交辦項，非馬拉松固定輪次編號",
        failed_gates=(["cheap_gate_precheck"] if not passes else None),
    )
    return out


if __name__ == "__main__":
    import json
    result = main()
    out_path = Path(__file__).parent / "monthly_revenue_sue_continuous_bucket_v1_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n結果已寫入 {out_path}")
