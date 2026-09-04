"""`HYPOTHESIS_QUEUE.md` #28 市場廣度背離（Breadth Divergence）當regime擇時
訊號 —— 第1關 sanity（`HYPOTHESIS_QUEUE_PROTOCOL.md` 排程，2026-09-04）。

**背景**：`#28`條目已完整說明經濟理由與跟已FAIL的`#2`/`#10`/`#15`/`#26`四者
的區隔（不是價格趨勢、不是波動度、不是融資水位，是「指數上漲時參與上漲的
個股比例」）。這輪只做sanity：確認`breadth_pct`時間序列本身非結構性no-op、
且在已知的市場頭部/回檔期間真的表現出「領先指數走弱」的背離型態、方向沒有
反過來——不是最終PASS/FAIL判定，是`#10`（regime_overlay.py）同一種sanity
精神的延伸。

**廣度指標定義（沿用既有300檔快取樣本，`factor_ic.SAMPLE_SIZE`/`SAMPLE_SEED`
不變，跟`#77`/`#79`/`#100`/`#101`同一份快取樣本）**：對樣本內每一檔股票，
用`adjusted_price_series()`拿到的還原收盤價算自身200日滾動均線（`rolling(200)`，
PIT-safe，不看未來），布林值「收盤價 > 自身200日均線」。逐日聚合樣本內「有
足夠歷史可計算200日均線」的股票中，處於該布林值為True的比例，得到`breadth_pct`
——這條時間序列跟TAIEX指數本身走勢是分開算的（不是TAIEX的200日均線）。

**背離訊號定義（見`#28`條目「具體假設定義」第2點）**：
  taiex_mom20 = TAIEX收盤 20交易日報酬（`pct_change(20)`）
  breadth_60d_change = breadth_pct[d] - breadth_pct[d-60]（純用過去資料，
    PIT-safe，不是跟未來比）
  divergence_flag[d] = (taiex_mom20[d] > 0) AND (breadth_60d_change[d] < 0)
  ——指數仍在漲、但參與上漲的個股比例正在萎縮，判定「背離警戒」。

**這輪sanity要驗證的三件事（協定第28條目「下一輪從sanity開始」的具體要求）**：
  ① breadth_pct非結構性常數/no-op（有變異、不是卡在0%或100%附近）。
  ② divergence_flag非結構性0事件/永遠觸發（觸發比例落在合理範圍）。
  ③ 方向正確、非反過來——用兩種獨立角度交叉驗證：
     (a) 已知市場頭部/回檔期間（沿用`regime_overlay.py`
         `KNOWN_CRISIS_WINDOWS`同一組歷史事件）「回檔開始前」的run-up窗口
         內，breadth下降的比例是否明顯高於全樣本無條件基準率（領先指標該有
         的行為，不是巧合）。
     (b) divergence_flag觸發後（用`shift(1)`避免未來函數）緊接著的20交易日
         TAIEX前瞻報酬，平均值是否確實低於無條件的平均前瞻報酬（背離警戒
         之後指數表現該比平常差，不是比平常好）。
若①②③皆合理，判「sanity PASS，非結構性no-op、方向正確」，下一輪可以進
第2關（隨機控制組——打亂breadth_pct時間序列跟TAIEX報酬的時序對齊，證明贏的
是「廣度惡化領先指數走弱」這個時序關係本身，不是任意曝險縮放都會贏）。若
方向反過來或觀測層級無訊號，依協定快殺標準直接判FAIL，不進第2關。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, START_DATE, sample_universe_ids
from finmind_client import load_dev
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

MA_WINDOW = 200
TAIEX_MOM_WINDOW = 20
BREADTH_LOOKBACK = 60
FORWARD_HORIZON = 20

# 沿用 regime_overlay.py 同一組已知歷史危機/回檔期間，不重新發明。
KNOWN_CRISIS_WINDOWS = {
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}
# run-up 窗口：每個危機期間「開始前」的一段觀察期，測的是「危機爆發前，
# breadth 有沒有已經在惡化」（領先指標該有的行為），不是危機期間本身。
RUNUP_DAYS = 60  # 交易日


def load_breadth_panel(sample_ids: list[str]) -> pd.DataFrame:
    """回傳寬表：index=date, columns=stock_id, value=bool(above_own_200dma)。
    每檔股票各自的還原收盤價已透過 adjusted_price_series() -> load_dev() 天然
    capped 在 VAL_END，不需要額外再 cap 一次。"""
    frames = {}
    for i, sid in enumerate(sample_ids):
        try:
            px = adjusted_price_series(sid, START_DATE)
        except Exception as e:  # noqa: BLE001 -- 跟 factor_ic.py 同一種容錯級別
            print(f"  [{i+1}/{len(sample_ids)}] {sid}: price ERROR ({e}), dropping")
            continue
        if px.empty or len(px) < MA_WINDOW + 20:
            continue
        s = px.set_index("date")["adj_close"].astype(float)
        ma = s.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean()
        # bool dtype 無法直接塞 NaN（LossySetitemError），改用 float(1.0/0.0/NaN)
        # 表示：warm-up 期還沒有200日均線的天數標成 NaN，不是 False。
        above = (s > ma).astype(float)
        above = above.mask(ma.isna())
        frames[sid] = above
    if not frames:
        raise RuntimeError("no usable stock in sample -- breadth panel is empty")
    panel = pd.DataFrame(frames)
    panel.index = pd.to_datetime(panel.index)
    panel = panel.sort_index()
    return panel


def compute_breadth_series(panel: pd.DataFrame) -> pd.DataFrame:
    """回傳含 date/breadth_pct/n_valid 三欄的 DataFrame（逐日聚合）。"""
    n_valid = panel.notna().sum(axis=1)
    breadth_pct = panel.mean(axis=1, skipna=True)  # NaN 天數自動被 skipna 排除分母
    out = pd.DataFrame({
        "date": panel.index,
        "breadth_pct": breadth_pct.values,
        "n_valid": n_valid.values,
    }).reset_index(drop=True)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out


def build_divergence_frame(breadth_df: pd.DataFrame, market_df: pd.DataFrame) -> pd.DataFrame:
    """合併 TAIEX 動量與 breadth 序列，算出 breadth_60d_change / divergence_flag /
    以及供方向性檢查用的 fwd_taiex_ret（未來20日TAIEX報酬，只用於sanity判讀，
    不是策略本身的訊號輸入）。"""
    m = market_df[["date", "close"]].copy().sort_values("date").reset_index(drop=True)
    m["taiex_mom20"] = m["close"].pct_change(TAIEX_MOM_WINDOW)
    m["fwd_taiex_ret"] = m["close"].shift(-FORWARD_HORIZON) / m["close"] - 1

    d = breadth_df.merge(m, on="date", how="inner").sort_values("date").reset_index(drop=True)
    d["breadth_60d_change"] = d["breadth_pct"] - d["breadth_pct"].shift(BREADTH_LOOKBACK)
    # bool 欄位無法直接塞 NaN（LossySetitemError），先轉成 object dtype 再遮罩。
    raw_flag = (d["taiex_mom20"] > 0) & (d["breadth_60d_change"] < 0)
    # 只有 taiex_mom20 / breadth_60d_change 兩者皆有值才算數，warm-up 期不判定
    valid = d["taiex_mom20"].notna() & d["breadth_60d_change"].notna()
    d["divergence_flag"] = raw_flag.astype(object).where(valid, np.nan)
    return d


def sanity_distribution(d: pd.DataFrame) -> dict:
    valid = d.dropna(subset=["breadth_pct"])
    stats = {
        "n_days": len(valid),
        "breadth_min": float(valid["breadth_pct"].min()),
        "breadth_max": float(valid["breadth_pct"].max()),
        "breadth_mean": float(valid["breadth_pct"].mean()),
        "breadth_std": float(valid["breadth_pct"].std()),
    }
    flag_valid = d.dropna(subset=["divergence_flag"])
    stats["n_flag_days"] = len(flag_valid)
    stats["flag_rate_pct"] = (100.0 * float(flag_valid["divergence_flag"].astype(bool).mean())
                               if len(flag_valid) else float("nan"))
    return stats


def sanity_crisis_runup(d: pd.DataFrame) -> list[dict]:
    """檢查①：已知危機/回檔期間開始前 RUNUP_DAYS 個交易日內，breadth下降
    （breadth_60d_change < 0）的比例是否明顯高於全樣本無條件基準率。"""
    unconditional_decline_rate = float((d["breadth_60d_change"] < 0).mean())
    rows = []
    dates_sorted = d["date"].tolist()
    for name, (start, _end) in KNOWN_CRISIS_WINDOWS.items():
        if start not in dates_sorted:
            # 找最接近但不晚於 start 的日期索引
            before = [i for i, dt in enumerate(dates_sorted) if dt <= start]
            if not before:
                rows.append({"crisis": name, "note": "危機開始日之前無資料，跳過"})
                continue
            start_idx = before[-1]
        else:
            start_idx = dates_sorted.index(start)
        runup_start_idx = max(0, start_idx - RUNUP_DAYS)
        window = d.iloc[runup_start_idx:start_idx]
        window = window.dropna(subset=["breadth_60d_change"])
        if window.empty:
            rows.append({"crisis": name, "note": "run-up窗口內無有效資料，跳過"})
            continue
        decline_rate = float((window["breadth_60d_change"] < 0).mean())
        rows.append({
            "crisis": name,
            "runup_window": f"{window['date'].iloc[0]}~{window['date'].iloc[-1]}",
            "n_days": len(window),
            "decline_rate_pct": decline_rate * 100,
            "unconditional_rate_pct": unconditional_decline_rate * 100,
            "leading_correct": decline_rate > unconditional_decline_rate,
        })
    return rows


def sanity_forward_return_direction(d: pd.DataFrame) -> dict:
    """檢查③(b)：divergence_flag（lag 1避免未來函數）觸發後的20日TAIEX前瞻
    報酬，平均值是否確實低於無條件平均——方向正確代表背離警戒之後指數表現
    確實比平常差，不是反過來。"""
    lagged_flag = d["divergence_flag"].shift(1)
    valid = d["fwd_taiex_ret"].notna() & lagged_flag.notna()
    sub = d[valid].copy()
    sub["lagged_flag"] = lagged_flag[valid]
    unconditional_mean = float(sub["fwd_taiex_ret"].mean())
    flagged = sub[sub["lagged_flag"] == True]  # noqa: E712
    not_flagged = sub[sub["lagged_flag"] == False]  # noqa: E712
    return {
        "n_obs": len(sub),
        "unconditional_mean_fwd_ret_pct": unconditional_mean * 100,
        "n_flagged": len(flagged),
        "flagged_mean_fwd_ret_pct": float(flagged["fwd_taiex_ret"].mean()) * 100 if len(flagged) else float("nan"),
        "n_not_flagged": len(not_flagged),
        "not_flagged_mean_fwd_ret_pct": float(not_flagged["fwd_taiex_ret"].mean()) * 100 if len(not_flagged) else float("nan"),
        "direction_correct": (float(flagged["fwd_taiex_ret"].mean()) < unconditional_mean) if len(flagged) else False,
    }


def main():
    print("載入TAIEX市場資料...")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in breadth_divergence_sanity")
    market_df = prepare_market_data(market_raw)
    market_df = holdout.cap_to_dev(market_df)
    print(f"  TRAIN+VAL範圍: {market_df['date'].min()} ~ {market_df['date'].max()}, n={len(market_df)}天")

    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    print(f"\n載入{len(sample_ids)}檔樣本股價（cached after first run）...")
    panel = load_breadth_panel(sample_ids)
    print(f"  {panel.shape[1]}/{len(sample_ids)}檔可用（>= {MA_WINDOW+20}個交易日歷史）")

    breadth_df = compute_breadth_series(panel)
    d = build_divergence_frame(breadth_df, market_df)
    holdout.assert_no_holdout_leakage(d, context="divergence frame in breadth_divergence_sanity")

    print("\n--- Sanity①：breadth_pct分布 + divergence_flag觸發率（非結構性0/常數）---")
    dist = sanity_distribution(d)
    print(f"  breadth_pct: n={dist['n_days']}天, min={dist['breadth_min']:.3f} "
          f"max={dist['breadth_max']:.3f} mean={dist['breadth_mean']:.3f} std={dist['breadth_std']:.3f}")
    print(f"  divergence_flag: n_valid={dist['n_flag_days']}天, 觸發率={dist['flag_rate_pct']:.1f}%")
    # breadth_pct 貼到 0%（極端崩盤日全部股票同時跌破自身200日均線）本身是合理的
    # 真實讀數，不是bug——退化的判準是「幾乎沒有變異」，不是「min/max不能碰到邊界」。
    non_degenerate = (dist["breadth_std"] > 0.02 and 0.0 <= dist["breadth_min"] < dist["breadth_max"] <= 1.0
                       and 1.0 <= dist["flag_rate_pct"] <= 70.0)
    print(f"  判定：{'PASS（非結構性no-op）' if non_degenerate else 'FAIL（常數/退化分布或觸發率不合理）'}")

    print("\n--- Sanity②：已知危機/回檔期間「開始前」run-up窗口breadth下降比例（領先指標檢查）---")
    runup_rows = sanity_crisis_runup(d)
    n_leading_correct = 0
    n_checkable = 0
    for r in runup_rows:
        if "note" in r:
            print(f"  {r['crisis']}: {r['note']}")
            continue
        n_checkable += 1
        n_leading_correct += int(r["leading_correct"])
        print(f"  {r['crisis']} (run-up {r['runup_window']}, n={r['n_days']}天): "
              f"breadth下降比例={r['decline_rate_pct']:.1f}% vs 全樣本無條件基準率={r['unconditional_rate_pct']:.1f}% "
              f"-> {'領先方向正確' if r['leading_correct'] else '未見領先(未過此項)'}")
    print(f"  {n_leading_correct}/{n_checkable}個可檢查危機期間顯示領先方向正確")

    print("\n--- Sanity③：divergence_flag觸發後20日TAIEX前瞻報酬方向檢查（lag1避免未來函數）---")
    fwd = sanity_forward_return_direction(d)
    print(f"  n_obs={fwd['n_obs']}, 無條件平均前瞻20日報酬={fwd['unconditional_mean_fwd_ret_pct']:+.2f}%")
    print(f"  divergence_flag觸發後(n={fwd['n_flagged']}): 平均前瞻20日報酬="
          f"{fwd['flagged_mean_fwd_ret_pct']:+.2f}%")
    print(f"  未觸發(n={fwd['n_not_flagged']}): 平均前瞻20日報酬={fwd['not_flagged_mean_fwd_ret_pct']:+.2f}%")
    print(f"  判定：{'方向正確（觸發後前瞻報酬確實較低）' if fwd['direction_correct'] else '方向反過來或無差異（未過此項）'}")

    print("\n--- 綜合結論（第1關sanity，非最終PASS/FAIL——判準見docstring）---")
    crisis_majority_correct = n_checkable > 0 and n_leading_correct >= (n_checkable + 1) // 2
    overall_pass = non_degenerate and crisis_majority_correct and fwd["direction_correct"]
    print(f"  ①非結構性no-op: {'PASS' if non_degenerate else 'FAIL'}")
    print(f"  ②危機期間領先方向多數正確({n_leading_correct}/{n_checkable}): "
          f"{'PASS' if crisis_majority_correct else 'FAIL'}")
    print(f"  ③前瞻報酬方向正確: {'PASS' if fwd['direction_correct'] else 'FAIL'}")
    print(f"  第1關sanity總判定: {'PASS，下一輪可進第2關隨機控制組' if overall_pass else 'FAIL，依快殺標準結案，不進第2關'}")

    return {
        "distribution": dist,
        "non_degenerate": non_degenerate,
        "crisis_runup": runup_rows,
        "crisis_majority_correct": crisis_majority_correct,
        "forward_return_direction": fwd,
        "overall_sanity_pass": overall_pass,
    }


if __name__ == "__main__":
    main()
