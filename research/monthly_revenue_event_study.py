"""`HYPOTHESIS_QUEUE.md` #14 台股月營收公布事件效應：第1關 sanity（事件研究設計）。

經濟理由：台股上市櫃公司依法每月10日前必須公布上月營收，是高頻強制揭露事件，
理論上公布當下市場消化不完全，營收驚喜（`f_revenue_surprise`/SUE，已在
`TRIALS_LEDGER.md`#8 通過因子層日頻cross-sectional IC驗證）若夠大，公布後
應有可觀察的持續漂移。詳見`HYPOTHESIS_QUEUE.md`#14完整說明。

**跟既有`factor_ic.py`框架的關鍵差異（這正是這條假設要驗證的新東西）**：
`factor_ic.py`用固定日曆網格快照（每20個交易日一次，全樣本股票共用同一批
snapshot日期），這是「日頻橫斷面排序」設計，PEAD策略層（`pead_portfolio_v1`，
已FAIL）也是月頻再平衡，同樣不是逐股「以自己的公布日為起點」的設計。這支腳本
改用**事件錨定窗口**：對每一檔股票，用它自己的月營收公布`pit_date`
（`pit.py::month_revenue_pit()`既有PIT邏輯，真實`create_time`優先、否則假設
次月10日）當事件起點，找公布後第一個交易日進場、持有`FORWARD_HORIZON`個交易日，
逐事件記錄「進場前的SUE值」跟「事件後N日報酬」，事件之間彼此不同步（不同股票
公布日不同），這是`HYPOTHESIS_QUEUE.md`#14要求的「事件研究設計」而非「月頻
橫斷面再平衡」，是這條佇列項目跟PEAD策略層（#3，FAIL）刻意做出的區隔。

沿用既有元件（不重新發明）：`factor_ic.py::sample_universe_ids()`（同一個
100檔快取樣本，SAMPLE_SEED=20260822，跟其他cheap gate腳本共用快取，省重抓）、
`factors.py::_revenue_surprise_sue()`（既有SUE計算，含`pit_date`欄位）、
`adjust.py::adjusted_price_series()`（既有還原股價+VAL_END自動截斷）、
`validation.holdout`（TRAIN_END/VAL_END切分+holdout洩漏斷言）。

判定標準比照本專案既有cheap gate三項判準（`factor_ic.py::evaluate_factor()`
同一把尺，只是把「日曆網格cross-sectional IC」換成「事件池pooled Spearman
相關」）：①TRAIN/VAL方向一致 ②VAL期|correlation|超過雜訊量級 ③贏過洗牌
（permutation）null分布，percentile>=90.0（standalone測試，bonferroni_n=1）。
這是第1關sanity（本輪目標）+ 一併做第2關等級的洗牌對照（沿用既有專案「cheap
gate合併測sanity+隨機控制組」的既定做法，跟#9/#11/#12/#13同一個模式），不是
完整GATE_SEQUENCE 3~9關（成本/leave-one-out/前向paper等留給portfolio層
follow-up，若這關過了才值得投入）。

2026-09-02 由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#14第1關起跑。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from factors import _revenue_surprise_sue
from validation import holdout

FORWARD_HORIZON = 20  # trading days，`HYPOTHESIS_QUEUE.md`#14定義「例如20日」
N_PERMUTATIONS = 500  # 洗牌null分布draws數；池化事件層級的相關性計算便宜（非回測），
# 500次足夠解析到90百分位所需的精度，不需要跟portfolio層那種昂貴回測一樣壓到200/1000。
PERM_SEED = 20260902
BASE_ALPHA = 0.10  # 跟factor_ic.py同一個單測顯著水準基準
BONFERRONI_N = 1  # standalone測試（這條佇列項目只測一個訊號，非批次多因子同時測）


def _stock_events(stock_id: str) -> pd.DataFrame:
    """單一股票的月營收公布事件表：pit_date, entry_date, revenue_sue, fwd_ret。

    進場規則：公布日`pit_date`之後第一個交易日進場（不是公布當天收盤價，避免用
    尚未公開的當日收盤價當進場價這種未來函數疑慮——公布後市場才看得到，隔一個
    交易日進場是保守但正確的PIT處理）。
    """
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一個容錯尺度
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return pd.DataFrame()
    if px.empty or len(px) < 260:
        return pd.DataFrame()
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in monthly_revenue_event_study")

    try:
        rev = _revenue_surprise_sue(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001
        print(f"  [{stock_id}] revenue ERROR ({e}), dropping")
        return pd.DataFrame()
    if rev.empty:
        return pd.DataFrame()
    # 注意：這裡刻意不對`rev`（原始營收表）本身做holdout斷言——`load_dev()`是用
    # 營收所屬期間的`date`欄位裁切VAL_END，但`pit_date`（揭露日）本來就會晚於
    # `date`一段時間，個別rows的`pit_date`超過VAL_END是正常現象，不是洩漏。真正
    # 的保護在下面：進場交易日必須取自已經被`adjusted_price_series()`（經
    # `load_dev`）裁到VAL_END的`px["date"]`，`pit_date`>VAL_END的事件天然找不到
    # 「之後的交易日」而被跳過（entry_idx=None）。最終的斷言放在`main()`裡對
    # 組好的事件表（用`entry_date`）做，那才是真正受保護、會被使用的資料。

    px = px.sort_values("date").reset_index(drop=True)
    dates = px["date"].tolist()
    adj_close = px["adj_close"].tolist()

    rows = []
    for _, r in rev.iterrows():
        pit = r["pit_date"]
        sue = r["revenue_sue"]
        if pd.isna(sue) or pd.isna(pit):
            continue
        entry_idx = None
        for i, d in enumerate(dates):
            if d > pit:
                entry_idx = i
                break
        if entry_idx is None or entry_idx + FORWARD_HORIZON >= len(dates):
            continue
        p0 = adj_close[entry_idx]
        p1 = adj_close[entry_idx + FORWARD_HORIZON]
        if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
            continue
        rows.append({
            "stock_id": stock_id, "pit_date": pit, "entry_date": dates[entry_idx],
            "revenue_sue": float(sue), "fwd_ret": float(p1 / p0 - 1),
        })
    return pd.DataFrame(rows)


def _period_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p_value": float("nan")}
    rho, p = spearmanr(df["revenue_sue"], df["fwd_ret"])
    return {"label": label, "n": n, "ic": float(rho), "p_value": float(p)}


def _quintile_spread(df: pd.DataFrame) -> dict:
    """做多SUE最高分位、放空(或比較)最低分位的事件平均報酬，方向性sanity檢查用。"""
    if len(df) < 25:  # 至少要有夠多事件才有意義切五等分
        return {"n": len(df), "q_top_mean": float("nan"), "q_bottom_mean": float("nan"), "spread": float("nan")}
    d = df.copy()
    d["quintile"] = pd.qcut(d["revenue_sue"], 5, labels=False, duplicates="drop")
    top = d[d["quintile"] == d["quintile"].max()]["fwd_ret"].mean()
    bottom = d[d["quintile"] == d["quintile"].min()]["fwd_ret"].mean()
    return {"n": len(df), "q_top_mean": float(top), "q_bottom_mean": float(bottom), "spread": float(top - bottom)}


def _permutation_null_percentile(df: pd.DataFrame, real_ic: float, n_perm: int, seed: int) -> float:
    """洗牌`revenue_sue`跟`fwd_ret`的配對關係（保留兩邊各自的邊際分布），重算
    Spearman相關，看真實|IC|贏過幾%的洗牌結果——跟`factor_ic.py::evaluate_factor()`
    的洗牌null邏輯同一個精神，只是這裡池化事件層級而非逐日cross-section。
    """
    if len(df) < 10 or pd.isna(real_ic):
        return float("nan")
    rng = np.random.RandomState(seed)
    sue = df["revenue_sue"].to_numpy()
    ret = df["fwd_ret"].to_numpy()
    abs_real = abs(real_ic)
    beaten = 0
    for _ in range(n_perm):
        shuffled = rng.permutation(sue)
        rho, _ = spearmanr(shuffled, ret)
        if pd.isna(rho):
            continue
        if abs(rho) <= abs_real:
            beaten += 1
    return 100.0 * beaten / n_perm


def main():
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"=== 台股月營收公布事件效應 sanity (HYPOTHESIS_QUEUE.md#14, standalone bonferroni_n={BONFERRONI_N}) ===")
    print(f"Sample: {len(sample_ids)} names (SAMPLE_SEED={SAMPLE_SEED}, 沿用factor_ic.py既有快取樣本), "
          f"forward_horizon={FORWARD_HORIZON}交易日")

    all_events = []
    n_ok = 0
    for i, sid in enumerate(sample_ids):
        ev = _stock_events(sid)
        if not ev.empty:
            all_events.append(ev)
            n_ok += 1
        if (i + 1) % 20 == 0:
            print(f"  progress {i+1}/{len(sample_ids)}, {n_ok} usable so far")

    if not all_events:
        print("SANITY FAIL: 零事件，資料層級有問題（不是無訊號，是抓取/解析有誤）。")
        return {"passes": False, "reason": "no_events"}

    events = pd.concat(all_events, ignore_index=True)
    holdout.assert_no_holdout_leakage(events, date_col="entry_date", context="monthly_revenue_event_study events (final)")
    print(f"\n{n_ok}/{len(sample_ids)} 檔股票有可用事件，總事件數={len(events)}")

    train = holdout.cap_to_train(events, date_col="entry_date")
    val = holdout.validation_slice(events, date_col="entry_date")

    n_months_train = train["entry_date"].str.slice(0, 7).nunique() if not train.empty else 0
    n_months_val = val["entry_date"].str.slice(0, 7).nunique() if not val.empty else 0
    print(f"TRAIN: {len(train)}筆事件跨{n_months_train}個不同月份 | VAL: {len(val)}筆事件跨{n_months_val}個不同月份")

    if events["revenue_sue"].isna().all() or events["fwd_ret"].isna().all():
        print("SANITY FAIL: revenue_sue或fwd_ret全部NaN。")
        return {"passes": False, "reason": "all_nan"}

    train_stats = _period_stats(train, "TRAIN")
    val_stats = _period_stats(val, "VAL")
    print(f"\nTRAIN pooled Spearman IC={train_stats['ic']:+.4f} (p={train_stats['p_value']:.4f}, n={train_stats['n']})")
    print(f"VAL   pooled Spearman IC={val_stats['ic']:+.4f} (p={val_stats['p_value']:.4f}, n={val_stats['n']})")

    train_q = _quintile_spread(train)
    val_q = _quintile_spread(val)
    print(f"\nTRAIN quintile: top_mean={train_q['q_top_mean']:+.4f} bottom_mean={train_q['q_bottom_mean']:+.4f} spread={train_q['spread']:+.4f}")
    print(f"VAL   quintile: top_mean={val_q['q_top_mean']:+.4f} bottom_mean={val_q['q_bottom_mean']:+.4f} spread={val_q['spread']:+.4f}")

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )

    null_pct = _permutation_null_percentile(val, val_stats["ic"], N_PERMUTATIONS, PERM_SEED)
    required_pct = 100.0 * (1 - BASE_ALPHA / BONFERRONI_N)
    print(f"\nVAL |IC| vs {N_PERMUTATIONS}次洗牌null percentile={null_pct:.1f} (需要>={required_pct:.1f})")
    print(f"same_sign(TRAIN/VAL)={same_sign}")

    reasons = []
    if train_stats["n"] < 30 or val_stats["n"] < 30:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")

    passes = len(reasons) == 0
    print(f"\n=== SANITY {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    return {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "train_quintile": train_q, "val_quintile": val_q,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign, "n_stocks_usable": n_ok,
    }


if __name__ == "__main__":
    main()
