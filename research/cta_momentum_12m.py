"""CTA趨勢跟隨（時序動量，`HYPOTHESIS_QUEUE.md`#2）——完整GATE_SEQUENCE（1~9關）。

經濟理由（見HYPOTHESIS_QUEUE.md原文）：時序動量（time-series momentum，
Moskowitz/Ooi/Pedersen 2012）——資產自身過去12個月報酬的正負號預測未來報酬
方向，是CTA（管理期貨）產業幾十年的核心策略類型。

具體實作（跟已FAIL的`fut_trend_multi_tf`#18刻意做出區隔，不是換皮重測）：
- `fut_trend_multi_tf`：10/20/60日三窗口動能多數決，每日重新計算訊號。
- 這裡：**單一12個月（252交易日）回顧報酬正負號**，訊號在每個月最後一個
  交易日重新計算一次、持有到下個月底（月頻換倉，貼近文獻/實務常見的CTA
  再平衡頻率，也自然壓低換手/成本），不是每日重算的多窗口投票。

沿用既有基礎設施，不重新發明資料管線：
- `fut_cheap_gate._load_series()`：`continuous_contract.build_continuous_series()`
  的日盤（day session）連續合約序列，2000-2024全歷史。
- `fut_cheap_gate._permutation_test()`：配對式隨機控制組（洗牌部位陣列、
  保留報酬序列配對），沿用同一組N_SHUFFLES=200/SHUFFLE_SEED。
- `deep_dive_fut_basis_carry.py`的成本模型常數（`ROUND_TRIP_COST_BPS_1X=5.0`，
  台指期交易稅為主的近似值，docstring已誠實揭露非精確經紀商費率）跟
  train/val period-local控制組寫法。
- `validation.holdout`的TRAIN_END/VAL_END。

GATE_SEQUENCE執行順序（`HYPOTHESIS_QUEUE.md`統一關卡，不得跳關）：
  1. sanity：部位陣列基本檢查（無NaN爆炸、long/short/flat比例合理、換倉次數）。
  2. 隨機控制組（N=200≥100 draws，全樣本）。
  3. 參數密集高原：252個交易日（12個月）為中心，測189/210/231/252/273/294
     （9~14個月，21交易日=1個月的整數倍間距），確認鄰近窗口不是只有252這個
     點碰巧過。
  4. 成本敏感度1x/2x/3x。
  5. leave-one-year-out。
  6. 逐年一致性：把2000-2024切成6個約4年的連續區間，检查至少5/6個區間
     方向一致（正報酬或贏過對照組中位數）。
  7. train/val樣本外：period-local動態隨機控制組（不是重用全樣本靜態控制組）。
  8. 下檔保護：MDD、日報酬左尾（VaR/CVaR式的簡化版：最差1%交易日次數與大小）、
     regime（大盤高波動期間曝險是否有自然收斂，因為此策略天生會在盤整/
     方向不明時訊號在0附近翻動較頻繁，屬於部分內建的regime反應，非外掛
     overlay——如同`CLAUDE.md`原則3所述，這裡誠實檢查這個內建效果是否存在，
     不是宣稱有外掛overlay）。
  第8關「前向paper」留給樣本外(7)+下檔保護(8)都通過後才進，這裡若通過會
  在腳本結尾印出清楚的「下一步：前向paper」提示，不在本腳本內做前向模擬
  （需要另外掛`update_strategy_performance.py`機制，屬於後續步驟）。

任何一關FAIL就照協定直接結案（不硬做後面關卡）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import fut_cheap_gate as cg
from validation import holdout

ROUND_TRIP_COST_BPS_1X = 5.0  # 同 deep_dive_fut_basis_carry.py 的台指期近似成本假設，docstring見該檔
COST_TIERS = {"1x": 1, "2x": 2, "3x": 3}
LOOKBACK_DAYS = 252  # 12個月 ≈ 252個交易日（本文件的主參數）
PLATEAU_WINDOWS = [189, 210, 231, 252, 273, 294]  # 9/10/11/12/13/14個月，21交易日間距


def _build_position_monthly(series: pd.DataFrame, lookback: int) -> pd.Series:
    """月頻重平衡的時序動量部位：每個月最後一個交易日，用當天往回`lookback`
    個交易日的累積報酬正負號決定部位，持有到下個月底重新計算。不足lookback
    天數的樣本開頭一律部位=NaN（沒有訊號，不強迫填0，避免製造假的「flat」
    交易記錄）。"""
    close = series["adj_close"]
    trailing_ret = close.pct_change(lookback)
    dates = pd.to_datetime(series["date"])
    month_key = dates.dt.to_period("M")
    is_month_end = month_key != month_key.shift(-1)  # 該列是當月最後一筆交易日

    signal_at_month_end = pd.Series(np.nan, index=series.index)
    signal_at_month_end[is_month_end] = np.sign(trailing_ret[is_month_end])
    position = signal_at_month_end.ffill()
    return position


def _matched_permutation_terminal(pos: pd.Series, ret: pd.Series, seed: int, n_shuffles: int = cg.N_SHUFFLES):
    valid = pos.notna() & ret.notna()
    p = pos[valid].reset_index(drop=True)
    r = ret[valid].reset_index(drop=True)
    strat_ret = p.shift(1).fillna(0.0) * r
    real_equity = float((1.0 + strat_ret).cumprod().iloc[-1])

    rng = np.random.default_rng(seed)
    p_arr = p.to_numpy()
    r_arr = r.to_numpy()
    randoms = np.empty(n_shuffles)
    for i in range(n_shuffles):
        shuffled = rng.permutation(p_arr)
        shuffled_ret = np.roll(shuffled, 1)
        shuffled_ret[0] = 0.0
        randoms[i] = np.prod(1.0 + shuffled_ret * r_arr)

    percentile = float((randoms < real_equity).mean() * 100.0)
    return real_equity, float(np.median(randoms)), percentile, strat_ret


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched (before)"

    series = cg._load_series()
    print(f"loaded continuous series: {len(series)} rows, "
          f"{series['date'].min().date()} .. {series['date'].max().date()}")

    # === 第1關：sanity ===
    print(f"\n=== 第1關 sanity（lookback={LOOKBACK_DAYS}日≈12個月，月頻重平衡）===")
    position = _build_position_monthly(series, LOOKBACK_DAYS)
    valid_position = position.dropna()
    n_long = int((valid_position == 1).sum())
    n_short = int((valid_position == -1).sum())
    n_flat = int((valid_position == 0).sum())
    n_flips = int((valid_position.diff().abs() > 0).sum())
    print(f"  有效部位天數={len(valid_position)}/{len(position)}（開頭{position.isna().sum()}天無12個月回顧史，NaN非bug）")
    print(f"  long={n_long}({n_long/len(valid_position)*100:.1f}%) short={n_short}({n_short/len(valid_position)*100:.1f}%) "
          f"flat={n_flat}({n_flat/len(valid_position)*100:.1f}%)")
    print(f"  部位變動次數={n_flips}（月頻重平衡，理論上限≈總月數）")
    sanity_ok = (len(valid_position) > 1000) and (n_long > 0) and (n_short > 0) and (n_flips > 5)
    print(f"  sanity判定：{'PASS' if sanity_ok else 'FAIL'}"
          f"（要求：有效樣本>1000天、long/short都存在、換倉次數>5，非結構性no-op）")
    if not sanity_ok:
        print("\n**第1關sanity未過，直接結案FAIL，不進後續關卡**")
        return

    # === 第2關：隨機控制組（全樣本，N=200）===
    print(f"\n=== 第2關 隨機控制組（N={cg.N_SHUFFLES}，全樣本）===")
    real_eq, rand_med, pctl, strat_ret_full = _matched_permutation_terminal(
        position, series["ret"], seed=cg.SHUFFLE_SEED)
    bh_eq = float((1.0 + series["ret"].fillna(0.0)).cumprod().iloc[-1])
    print(f"  real_terminal_equity={real_eq:.4f} ({(real_eq-1)*100:+.1f}%累積，無成本)")
    print(f"  buy_and_hold_equity={bh_eq:.4f} ({(bh_eq-1)*100:+.1f}%)")
    print(f"  random_median_equity={rand_med:.4f} percentile={pctl:.1f}")
    gate2_pass = pctl >= 90.0
    print(f"  第2關判定：{'CHEAP_PASS' if gate2_pass else 'FAIL'}（門檻90.0，單測、未做Bonferroni/FDR累積校正）")
    if not gate2_pass:
        print("\n**第2關隨機控制組未過，直接結案FAIL，不進後續關卡**")
        return

    # === 第3關：參數密集高原 ===
    print(f"\n=== 第3關 參數密集高原（{PLATEAU_WINDOWS}交易日，以{LOOKBACK_DAYS}為中心）===")
    plateau_rows = []
    for w in PLATEAU_WINDOWS:
        pos_w = _build_position_monthly(series, w)
        r_eq, r_med, r_pctl, _ = _matched_permutation_terminal(pos_w, series["ret"], seed=cg.SHUFFLE_SEED)
        plateau_rows.append(dict(window=w, months=round(w / 21.0, 1), real_eq=r_eq, percentile=r_pctl,
                                  passes=r_pctl >= 90.0))
        print(f"  window={w}日(~{w/21.0:.1f}個月) real_eq={r_eq:.4f} percentile={r_pctl:.1f} "
              f"{'PASS' if r_pctl >= 90.0 else 'FAIL'}")
    n_pass_plateau = sum(1 for r in plateau_rows if r["passes"])
    gate3_pass = n_pass_plateau >= 4  # 6個窗口中至少4個過關才算「一整片高原」，不是單點僥倖
    print(f"  第3關判定：{n_pass_plateau}/{len(PLATEAU_WINDOWS)}個窗口過關，"
          f"{'PASS（密集高原成立）' if gate3_pass else 'FAIL（疑似單點僥倖，非穩健高原）'}")
    if not gate3_pass:
        print("\n**第3關參數密集高原未過（252天像是孤立僥倖點），直接結案FAIL，不進後續關卡**")
        return

    # === 第4關：成本敏感度1x/2x/3x ===
    print(f"\n=== 第4關 成本敏感度（round-trip 1x={ROUND_TRIP_COST_BPS_1X}bps，同deep_dive_fut_basis_carry.py假設）===")
    turnover = position.diff().abs().fillna(0.0)
    cost_results = {}
    for tier_label, mult in COST_TIERS.items():
        per_unit_cost = (ROUND_TRIP_COST_BPS_1X / 2.0 / 10000.0) * mult
        cost_drag = turnover * per_unit_cost
        strat_ret_net = strat_ret_full - cost_drag.shift(1).reindex(strat_ret_full.index).fillna(0.0)
        terminal_net = float((1.0 + strat_ret_net.fillna(0.0)).cumprod().iloc[-1])
        cost_results[tier_label] = terminal_net
        print(f"  [{tier_label}] round_trip_cost={ROUND_TRIP_COST_BPS_1X * mult:.1f}bps "
              f"terminal_equity_net={terminal_net:.4f} ({(terminal_net-1)*100:+.1f}%)")
    gate4_pass = all(v > 1.0 for v in cost_results.values())
    print(f"  第4關判定：{'PASS（三個情境都維持正報酬）' if gate4_pass else 'FAIL（至少一個成本情境轉負）'}")
    if not gate4_pass:
        print("\n**第4關成本敏感度未過，直接結案FAIL，不進後續關卡**")
        return

    # === 第5關：leave-one-year-out ===
    print(f"\n=== 第5關 leave-one-year-out ===")
    merged = series.copy()
    merged["position"] = position
    merged["strat_ret"] = strat_ret_full
    merged["year"] = pd.to_datetime(merged["date"]).dt.year
    full_terminal = real_eq
    years = sorted(merged["year"].unique())
    loyo_rows = []
    for y in years:
        kept = merged[merged["year"] != y]
        kept_ret = kept["strat_ret"].fillna(0.0)
        kept_terminal = float((1.0 + kept_ret).cumprod().iloc[-1]) if len(kept_ret) else np.nan
        year_only = merged[merged["year"] == y]
        year_ret = float((1.0 + year_only["strat_ret"].fillna(0.0)).cumprod().iloc[-1]) - 1.0
        loyo_rows.append(dict(year=y, year_return=year_ret, terminal_excl_year=kept_terminal,
                               ratio_to_full=kept_terminal / full_terminal if full_terminal else np.nan))
    loyo_df = pd.DataFrame(loyo_rows).sort_values("year_return", ascending=False)
    print(loyo_df.to_string(index=False, formatters={
        "year_return": "{:+.2%}".format, "terminal_excl_year": "{:.4f}".format,
        "ratio_to_full": "{:.4f}".format}))
    top3 = loyo_df.head(3)["year"].tolist()
    excl_top3 = merged[~merged["year"].isin(top3)]
    excl_top3_terminal = float((1.0 + excl_top3["strat_ret"].fillna(0.0)).cumprod().iloc[-1])
    ratio_excl_top3 = excl_top3_terminal / full_terminal
    print(f"\n  最大貢獻3個年份：{top3}，排除後終值比例={ratio_excl_top3:.4f}")
    gate5_pass = ratio_excl_top3 > 1.0  # 排除掉貢獻最大的3年後，剩餘樣本本身仍要是正報酬
    # 呼應fut_basis_carry #35->#37的教訓：717x的82倍放大集中在2000-2002三年，
    # 排除後樣本外直接轉負/大幅萎縮才是真正的危險信號，這裡用「排除後仍為正」
    # 當作最低限度的過關線（不是要求排除後跟全樣本一樣強）。
    print(f"  第5關判定：{'PASS（排除最大3年貢獻後仍為正報酬，非少數年份撐起全部）' if gate5_pass else 'FAIL（排除最大貢獻年份後轉負，集中度風險同fut_basis_carry #35的死法）'}")
    if not gate5_pass:
        print("\n**第5關leave-one-out未過，直接結案FAIL，不進後續關卡**")
        return

    # === 第6關：逐年一致性（切6個約4年區間，>=5/6方向一致）===
    print(f"\n=== 第6關 逐年一致性（切6個約4年連續區間）===")
    year_min, year_max = min(years), max(years)
    span = year_max - year_min + 1
    bucket_size = span / 6.0
    bucket_edges = [year_min + round(i * bucket_size) for i in range(7)]
    bucket_edges[-1] = year_max + 1  # 確保最後一個區間含最後一年
    consistency_rows = []
    for i in range(6):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        sub = merged[(merged["year"] >= lo) & (merged["year"] < hi)]
        if len(sub) == 0:
            continue
        sub_ret = sub["strat_ret"].fillna(0.0)
        sub_terminal = float((1.0 + sub_ret).cumprod().iloc[-1])
        _, sub_rand_med, sub_pctl, _ = _matched_permutation_terminal(
            sub["position"], sub["ret"], seed=cg.SHUFFLE_SEED, n_shuffles=100)
        direction_ok = (sub_terminal > 1.0) or (sub_pctl >= 50.0)
        consistency_rows.append(dict(period=f"{lo}-{hi-1}", terminal=sub_terminal,
                                      percentile=sub_pctl, direction_ok=direction_ok))
        print(f"  [{lo}-{hi-1}] terminal={sub_terminal:.4f}({(sub_terminal-1)*100:+.1f}%) "
              f"vs隨機中位數percentile={sub_pctl:.1f} "
              f"{'一致' if direction_ok else '不一致'}")
    n_consistent = sum(1 for r in consistency_rows if r["direction_ok"])
    gate6_pass = n_consistent >= 5
    print(f"  第6關判定：{n_consistent}/{len(consistency_rows)}個區間方向一致，"
          f"{'PASS' if gate6_pass else 'FAIL'}（門檻至少5/6）")
    if not gate6_pass:
        print("\n**第6關逐年一致性未過，直接結案FAIL，不進後續關卡**")
        return

    # === 第7關：train/val樣本外（period-local動態隨機控制組） ===
    print(f"\n=== 第7關 train/val樣本外（TRAIN_END={holdout.TRAIN_END}, VAL_END={holdout.VAL_END}）===")
    train_mask = merged["date"] <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = (merged["date"] > pd.Timestamp(holdout.TRAIN_END)) & (merged["date"] <= pd.Timestamp(holdout.VAL_END))
    split_results = {}
    for label, mask in [("train", train_mask), ("val", val_mask)]:
        sub = merged[mask].reset_index(drop=True)
        r_eq, r_med, r_pctl, _ = _matched_permutation_terminal(sub["position"], sub["ret"], seed=cg.SHUFFLE_SEED)
        sub_bh = float((1.0 + sub["ret"].fillna(0.0)).cumprod().iloc[-1])
        split_results[label] = dict(real_eq=r_eq, pctl=r_pctl, bh_eq=sub_bh, n=len(sub))
        print(f"  [{label}] {sub['date'].min().date()}..{sub['date'].max().date()} n={len(sub)} "
              f"real_eq={r_eq:.4f}({(r_eq-1)*100:+.1f}%) buy&hold={sub_bh:.4f}({(sub_bh-1)*100:+.1f}%) "
              f"random_median={r_med:.4f} percentile={r_pctl:.1f}")
    gate7_pass = split_results["val"]["real_eq"] > 1.0 and split_results["val"]["pctl"] >= 90.0
    print(f"  第7關判定：{'PASS' if gate7_pass else 'FAIL'}"
          f"（要求VAL期本身單獨過關，不能只靠TRAIN撐平均——VAL報酬為正且percentile>=90.0）")
    if not gate7_pass:
        print("\n**第7關樣本外未過（VAL期沒有獨立撐住），直接結案FAIL，不進後續關卡**")
        return

    # === 第8關：下檔保護 ===
    print(f"\n=== 第8關 下檔保護（MDD/尾端風險/內建regime反應）===")
    def _mdd(ret_series: pd.Series) -> float:
        eq = (1.0 + ret_series.fillna(0.0)).cumprod()
        running_max = eq.cummax()
        drawdown = eq / running_max - 1.0
        return float(drawdown.min())

    for label, mask in [("full", pd.Series(True, index=merged.index)), ("train", train_mask), ("val", val_mask)]:
        sub = merged[mask]
        mdd = _mdd(sub["strat_ret"])
        bh_mdd = _mdd(sub["ret"])
        worst_1pct = sub["strat_ret"].dropna().quantile(0.01)
        print(f"  [{label}] 策略MDD={mdd*100:.2f}% vs 買進持有MDD={bh_mdd*100:.2f}% "
              f"最差1%交易日報酬分位={worst_1pct*100:.2f}%")

    # regime檢查：高波動期間（20日已實現波動度高於自身展開中位數）的曝險是否
    # 自然收斂（部位絕對值趨近0或訊號翻動更頻繁），這裡只誠實檢查是否存在，
    # 不宣稱這是外掛overlay。
    realized_vol = series["ret"].rolling(20).std()
    high_vol_regime = realized_vol > realized_vol.expanding(min_periods=40).median()
    exposure_high_vol = position[high_vol_regime.reindex(position.index, fill_value=False)].abs().mean()
    exposure_low_vol = position[~high_vol_regime.reindex(position.index, fill_value=False)].abs().mean()
    print(f"  高波動regime平均曝險(|position|)={exposure_high_vol:.3f} vs 低波動regime={exposure_low_vol:.3f}")
    print(f"  （這是月頻訊號的被動觀察，不是外掛regime overlay——若使用者要求強制overlay，"
          f"屬於HYPOTHESIS_QUEUE.md#5「regime輪動」的後續工作，不在這條CTA假設本身的範圍內）")

    mdd_full = _mdd(merged["strat_ret"])
    bh_mdd_full = _mdd(merged["ret"])
    gate8_pass = mdd_full > bh_mdd_full  # 策略MDD（越接近0越好）優於買進持有MDD
    print(f"  第8關判定：{'PASS（策略MDD優於買進持有）' if gate8_pass else 'FAIL（策略MDD比買進持有更差，下檔沒守住）'}")
    if not gate8_pass:
        print("\n**第8關下檔保護未過，直接結案FAIL，不進前向paper**")
        return

    print("\n" + "=" * 70)
    print("**全部1~8關通過（CTA時序動量12個月月頻）！**")
    print("下一步：第9關前向paper——接`data/strategy_performance.json`前向模擬機制")
    print("（`update_strategy_performance.py`），逐日累積、不可回填。")
    print("此腳本本身不做前向paper（需要另外掛機制），交由下一步驟處理。")
    print("=" * 70)

    holdout_ok = holdout.is_holdout_consumed() is False
    print(f"\nholdout check (after): is_holdout_consumed() -> {not holdout_ok and 'TRUE -- VIOLATION' or 'False (OK)'}")
    assert holdout_ok, "holdout must remain untouched (after)"


if __name__ == "__main__":
    main()
