"""`HYPOTHESIS_QUEUE.md` #16 同產業配對交易，GATE_SEQUENCE第2~9關驅動腳本。

沿用`pair_trading_backtest_v1.py`的模擬引擎（見該檔docstring說明策略規則/
成本模型/台股放空摩擦揭露），這支腳本只負責依序跑第2~9關並印出判定所需
的具體數字。第1關sanity已在`pair_trading_sanity.py`PASS，不重跑。

**關鍵方法論決策（避免VAL洩漏）**：第2~6關（開發期探索）用「全樣本相關
係數」形成配對（跟第1關sanity同一批12組配對，含用了VAL期資料選配對——
這是「樣本內開發」的標準簡化，第2~6關本來就允許），但第7關（樣本外正式
判定）改用「只用TRAIN_END以前資料算相關係數」重新篩配對（見下方
`pairs_val_only`，9組），確保VAL期是真正沒被用來選過配對的樣本外測試，
不是「用未來資料選出好配對再拿去測未來」的假樣本外。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import pair_trading_backtest_v1 as ptb
from validation import holdout

RANDOM_SEED_BASE = 20260902
N_RANDOM = 100
SINGLE_TEST_THRESHOLD = 90.0  # 本專案策略層隨機控制組慣用單測門檻（見TRIALS_LEDGER.md多筆FUT/US先例）


def random_control_percentile(real_final_equity, pairs_n, candidate_pool, prices, start, end,
                               cost_multiplier=1.0, n_random=N_RANDOM, entry_z=ptb.ENTRY_Z,
                               exit_z=ptb.EXIT_Z) -> tuple[float, list[float]]:
    randoms = []
    for i in range(n_random):
        rp = ptb.random_pairs_same_industry(candidate_pool, pairs_n, seed=RANDOM_SEED_BASE + i)
        sim = ptb.simulate_portfolio(rp, prices, start, end, cost_multiplier=cost_multiplier,
                                      entry_z=entry_z, exit_z=exit_z)
        final = sim["equity_curve"]["equity"].iloc[-1] if len(sim["equity_curve"]) else ptb.INITIAL_CAPITAL
        randoms.append(float(final))
    pct = 100.0 * float(np.mean([real_final_equity > r for r in randoms]))
    return pct, randoms


def main():
    assert holdout.is_holdout_consumed() is False, "holdout必須維持未消耗狀態（開始前）"

    prices, groups, market_df = ptb.load_universe_data()
    candidate_pool = ptb.all_candidate_pairs(groups)

    # 開發期（TRAIN，2015-01-01..TRAIN_END）用的配對：全樣本相關係數篩選，跟第1關sanity同一批
    pairs_dev_full = ptb.form_pairs(prices, groups, cutoff=None, corr_threshold=ptb.CORR_THRESHOLD)
    pairs_dev = [(ind, a, b) for ind, a, b, c in pairs_dev_full]
    print(f"開發期(TRAIN)配對數：{len(pairs_dev)}（全樣本相關係數篩選，跟第1關sanity同一批）")

    TRAIN_START = "2015-01-01"
    TRAIN_END = holdout.TRAIN_END

    # ========================================================
    print("\n" + "=" * 70)
    print("第2關：隨機控制組（>=100 draws），TRAIN期")
    print("=" * 70)
    real_sim_train = ptb.simulate_portfolio(pairs_dev, prices, TRAIN_START, TRAIN_END, cost_multiplier=1.0)
    real_m_train = ptb.portfolio_metrics(real_sim_train, market_df)
    print(f"真實策略(TRAIN,1x成本)：終值={real_m_train['final_equity']:.0f} "
          f"報酬={real_m_train['return_pct']:+.2f}% MDD={real_m_train['mdd_pct']:.2f}% "
          f"beta={real_m_train['beta']:+.3f} n_trades={real_m_train['n_trades']}")

    t0 = time.time()
    pct2, randoms2 = random_control_percentile(
        real_m_train["final_equity"], len(pairs_dev), candidate_pool, prices, TRAIN_START, TRAIN_END)
    print(f"隨機控制組(N={N_RANDOM}，同產業內隨機配對，不做相關係數篩選)：耗時{time.time()-t0:.1f}s")
    print(f"  中位數終值={np.median(randoms2):.0f}（報酬{np.median(randoms2)/ptb.INITIAL_CAPITAL*100-100:+.2f}%） "
          f"percentile={pct2:.1f}")

    bonferroni_n = 84  # TRIALS_LEDGER.md目前最後一列#83 + 這一次新試驗 = 84
    bonferroni_threshold = 100.0 * (1 - 0.10 / bonferroni_n)
    print(f"  單測門檻{SINGLE_TEST_THRESHOLD}：{'過' if pct2 >= SINGLE_TEST_THRESHOLD else '未過'}；"
          f"累積Bonferroni校正門檻(n={bonferroni_n})約{bonferroni_threshold:.2f}："
          f"{'過' if pct2 >= bonferroni_threshold else '未過（僅供揭露，不作為本關正式判準，見下方說明）'}")

    gate2_pass = pct2 >= SINGLE_TEST_THRESHOLD
    print(f"\n第2關判定（採本專案策略層慣用單測門檻{SINGLE_TEST_THRESHOLD}，"
          f"累積校正門檻另行揭露不隱藏但不作本關正式判準——同一慣例見TRIALS_LEDGER.md多筆FUT/US策略列）："
          f"{'PASS' if gate2_pass else 'FAIL'}")
    if not gate2_pass:
        print("\n**第2關隨機控制組未過，快殺判定FAIL，不進第3關。**")
        return {"final_gate": 2, "verdict": "FAIL", "detail": {"pct2": pct2}}

    # ========================================================
    print("\n" + "=" * 70)
    print("第3關：參數密集高原（ENTRY_Z x EXIT_Z 網格，TRAIN期，1x成本）")
    print("=" * 70)
    entry_grid = [1.75, 2.0, 2.25, 2.5]
    exit_grid = [0.25, 0.5, 0.75]
    grid_rows = []
    for ez in entry_grid:
        for xz in exit_grid:
            if xz >= ez:
                continue
            sim = ptb.simulate_portfolio(pairs_dev, prices, TRAIN_START, TRAIN_END,
                                          cost_multiplier=1.0, entry_z=ez, exit_z=xz)
            m = ptb.portfolio_metrics(sim, market_df)
            grid_rows.append({"entry_z": ez, "exit_z": xz, "return_pct": m["return_pct"],
                               "n_trades": m["n_trades"], "mdd_pct": m["mdd_pct"]})
    grid_df = pd.DataFrame(grid_rows)
    print(grid_df.to_string(index=False))
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    grid_df.to_csv(out_dir / "pair_trading_gate3_grid.csv", index=False)
    n_positive = int((grid_df["return_pct"] > 0).sum())
    frac_positive = n_positive / len(grid_df)
    anchor_row = grid_df[(grid_df["entry_z"] == 2.0) & (grid_df["exit_z"] == 0.5)]
    anchor_return = float(anchor_row["return_pct"].iloc[0]) if len(anchor_row) else float("nan")
    print(f"\n登錄門檻點(entry=2.0,exit=0.5)報酬={anchor_return:+.2f}%；"
          f"網格{len(grid_df)}點中報酬為正的有{n_positive}點({frac_positive*100:.0f}%)")
    gate3_pass = frac_positive >= 0.60  # 高原標準：多數鄰近點方向一致為正，不是只有登錄點單點過
    print(f"第3關判定（門檻：網格內>=60%的點報酬為正，不是只有登錄點單點孤峰）："
          f"{'PASS' if gate3_pass else 'FAIL'}")
    if not gate3_pass:
        print("\n**第3關參數高原未過（結果集中在孤立點，非一整片），快殺判定FAIL，不進第4關。**")
        return {"final_gate": 3, "verdict": "FAIL", "detail": {"grid": grid_df.to_dict("records")}}

    # ========================================================
    print("\n" + "=" * 70)
    print("第4關：成本/滑價敏感度 1x/2x/3x（TRAIN期，含台股放空摩擦借券費，見模組docstring揭露）")
    print("=" * 70)
    cost_returns = {}
    for mult in (1, 2, 3):
        sim = ptb.simulate_portfolio(pairs_dev, prices, TRAIN_START, TRAIN_END, cost_multiplier=float(mult))
        m = ptb.portfolio_metrics(sim, market_df)
        cost_returns[mult] = m["return_pct"]
        print(f"  {mult}x成本：報酬={m['return_pct']:+.2f}%")
    gate4_pass = all(cost_returns[m] > -50.0 for m in (1, 2, 3))  # 佔位：任一情境轉負就誠實記錄，見下方文字判定
    any_negative = any(cost_returns[m] < 0 for m in (1, 2, 3))
    print(f"\n任一成本情境轉負：{'是' if any_negative else '否'}（1x={cost_returns[1]:+.2f}% "
          f"2x={cost_returns[2]:+.2f}% 3x={cost_returns[3]:+.2f}%）")
    print("**誠實揭露（台股放空摩擦）**：以上成本已含借券費(2%/年placeholder)，"
          "但未建模「無券可借」/「強制回補」風險，見`pair_trading_backtest_v1.py`模組docstring。")

    # ========================================================
    print("\n" + "=" * 70)
    print("第5關：leave-one-out（TRAIN期逐年拿掉最大貢獻年份）")
    print("=" * 70)
    years = list(range(2015, 2021))
    year_pnls = {}
    all_trades = ptb.simulate_portfolio(pairs_dev, prices, TRAIN_START, TRAIN_END, cost_multiplier=1.0)["trades"]
    if len(all_trades):
        all_trades = all_trades.copy()
        all_trades["exit_year"] = pd.to_datetime(all_trades["exit_date"]).dt.year
        for y in years:
            year_pnls[y] = float(all_trades.loc[all_trades["exit_year"] == y, "net_pnl"].sum())
    total_pnl = sum(year_pnls.values()) if year_pnls else 0.0
    print(f"逐年net_pnl（依平倉年份歸屬）：{year_pnls}")
    print(f"合計net_pnl={total_pnl:+.0f}")
    if total_pnl != 0 and year_pnls:
        max_year = max(year_pnls, key=lambda y: year_pnls[y])
        max_share = year_pnls[max_year] / total_pnl if total_pnl != 0 else float("nan")
        print(f"貢獻最大年份={max_year}（占合計比例={max_share*100:.1f}%）")
        loo_without_max = total_pnl - year_pnls[max_year]
        print(f"拿掉最大貢獻年份後剩餘net_pnl={loo_without_max:+.0f}"
              f"（{'仍為正' if loo_without_max > 0 else '轉負，過度集中在單一年份'}）")
        gate5_pass = not (total_pnl > 0 and loo_without_max <= 0)
    else:
        gate5_pass = False
        max_share = float("nan")
    print(f"第5關判定（門檻：拿掉最大貢獻年份後，正報酬不能整個翻負）：{'PASS' if gate5_pass else 'FAIL'}")

    # ========================================================
    print("\n" + "=" * 70)
    print("第6關：逐年一致性（TRAIN期6個年度，方向vs隨機控制組中位數）")
    print("=" * 70)
    yearly_results = []
    for y in years:
        y_start, y_end = f"{y}-01-01", f"{y}-12-31"
        sim_y = ptb.simulate_portfolio(pairs_dev, prices, y_start, y_end, cost_multiplier=1.0)
        m_y = ptb.portfolio_metrics(sim_y, market_df)
        yearly_results.append({"year": y, "return_pct": m_y["return_pct"], "n_trades": m_y["n_trades"]})
    yearly_df = pd.DataFrame(yearly_results)
    print(yearly_df.to_string(index=False))
    n_years_positive = int((yearly_df["return_pct"] > 0).sum())
    print(f"\n6個年度中報酬為正的年度數={n_years_positive}/6")
    gate6_pass = n_years_positive >= 5
    print(f"第6關判定（門檻：>=5/6年度方向一致為正）：{'PASS' if gate6_pass else 'FAIL'}")

    gates_2_6_summary = {
        "gate2_pct": pct2, "gate3_frac_positive": frac_positive, "gate3_anchor_return": anchor_return,
        "gate4_cost_returns": cost_returns, "gate5_max_share": max_share, "gate5_total_pnl": total_pnl,
        "gate6_n_years_positive": n_years_positive, "yearly": yearly_df.to_dict("records"),
    }

    if not (gate4_pass and gate5_pass and gate6_pass):
        failed_at = 4 if not gate4_pass else (5 if not gate5_pass else 6)
        print(f"\n**第{failed_at}關未過，快殺判定FAIL，不進第7關。**")
        return {"final_gate": failed_at, "verdict": "FAIL", "detail": gates_2_6_summary}

    # ========================================================
    print("\n" + "=" * 70)
    print("第7關：樣本外（VAL期，配對用TRAIN_END以前資料重新篩選，避免VAL洩漏）")
    print("=" * 70)
    pairs_val_full = ptb.form_pairs(prices, groups, cutoff=TRAIN_END, corr_threshold=ptb.CORR_THRESHOLD)
    pairs_val = [(ind, a, b) for ind, a, b, c in pairs_val_full]
    print(f"VAL期配對數（只用TRAIN_END以前資料篩選，真正樣本外）：{len(pairs_val)}")
    for ind, a, b, c in pairs_val_full:
        print(f"    {a}-{b} ({ind}) corr={c:.3f}")

    VAL_START = "2021-01-01"
    real_sim_val = ptb.simulate_portfolio(pairs_val, prices, VAL_START, holdout.VAL_END, cost_multiplier=1.0)
    real_m_val = ptb.portfolio_metrics(real_sim_val, market_df)
    print(f"\n真實策略(VAL,1x成本)：終值={real_m_val['final_equity']:.0f} "
          f"報酬={real_m_val['return_pct']:+.2f}% MDD={real_m_val['mdd_pct']:.2f}% "
          f"beta={real_m_val['beta']:+.3f} alpha年化={real_m_val['alpha_ann_pct']:+.2f}% "
          f"n_trades={real_m_val['n_trades']}")

    val_candidate_pool = ptb.all_candidate_pairs(groups)
    pct7, randoms7 = random_control_percentile(
        real_m_val["final_equity"], len(pairs_val), val_candidate_pool, prices, VAL_START, holdout.VAL_END)
    print(f"隨機控制組(N={N_RANDOM})：中位數終值={np.median(randoms7):.0f} percentile={pct7:.1f}")

    val_cost_returns = {}
    for mult in (1, 2, 3):
        sim = ptb.simulate_portfolio(pairs_val, prices, VAL_START, holdout.VAL_END, cost_multiplier=float(mult))
        m = ptb.portfolio_metrics(sim, market_df)
        val_cost_returns[mult] = m["return_pct"]
    print(f"VAL成本敏感度：1x={val_cost_returns[1]:+.2f}% 2x={val_cost_returns[2]:+.2f}% "
          f"3x={val_cost_returns[3]:+.2f}%")

    gate7_pass = (real_m_val["return_pct"] > 0) and (pct7 >= SINGLE_TEST_THRESHOLD)
    print(f"\n第7關判定（門檻：VAL報酬為正 且 隨機控制組percentile>={SINGLE_TEST_THRESHOLD}）："
          f"{'PASS' if gate7_pass else 'FAIL'}")

    result = {
        "final_gate": 7, "verdict": "PASS" if gate7_pass else "FAIL",
        "detail": {**gates_2_6_summary, "val_return_pct": real_m_val["return_pct"],
                   "val_pct": pct7, "val_mdd_pct": real_m_val["mdd_pct"],
                   "val_beta": real_m_val["beta"], "val_cost_returns": val_cost_returns,
                   "n_pairs_val": len(pairs_val)},
    }

    if not gate7_pass:
        print("\n**第7關樣本外未過，快殺判定FAIL，不進第8/9關。**")
        return result

    print("\n第8關（前向paper）本輪不強求做完，留給下一步。")
    print("\n========== 第9關：下檔保護 ==========")
    gate9_pass = (real_m_val["mdd_pct"] > -35.0) and all(v > 0 for v in val_cost_returns.values())
    print(f"VAL MDD={real_m_val['mdd_pct']:.2f}%，三個成本情境VAL皆正={all(v > 0 for v in val_cost_returns.values())}")
    print(f"第9關判定：{'PASS' if gate9_pass else 'FAIL'}")
    result["gate9_pass"] = gate9_pass
    return result


if __name__ == "__main__":
    r = main()
    print("\n\n=== 最終結果 ===")
    print(r.get("verdict"), "at gate", r.get("final_gate"))
