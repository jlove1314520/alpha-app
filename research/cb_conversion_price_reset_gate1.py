"""`HYPOTHESIS_QUEUE.md` #51 子事件3（可轉換公司債轉換價格重設）第1關cheap gate。

**經濟機制（跟已FAIL的子事件1/子事件2同屬#51「強制/準結構性交易者」大類，
但換第三種機制）**：可轉債轉換價格向下重設（例如反稀釋條款觸發、或除權息
後例行調整），代表同一張債券未來可轉換的股數變多——轉換的「有效成本」
變低。重設幅度越大，債券持有人未來執行轉換、再賣出換來的股票變現的誘因
越強（轉換後立刻賣出鎖利是常見操作），對應到#51核心主張「有一群人不管
價格都必須交易/有強誘因交易，而且日期事前已知」——重設生效日
（`effective_date`）本身就是公告內容明訂的未來日期，PIT無虞。

**事前綁定假設**：`reset_magnitude = (old_price - new_price) / old_price`
（只看向下重設，`new_price < old_price`；向上重設是不同機制，另外統計但
不納入本次假設檢定）越大，`effective_date`之後N個交易日的累積超額報酬
（CAR）應該越**負**——潛在轉換套利賣壓越大。跟子事件2
（`cash_increase_dilution_gate1.py`）同一個方向與同一套Spearman IC +
VAL期洗牌permutation null框架，只是換了觸發事件跟強制交易者身分（可轉債
持有人 vs 現金增資認股人）。

**資料來源**：`mops_cb_conversion_price_client.py::fetch_conversion_price_events()`
（MOPS `t108sb08_1_q2`功能，2026-09-07本輪之前已確認可行，見
`HYPOTHESIS_QUEUE.md` #51條目(g)段落）。本檔案新增**歷史回填**：民國
99~113年（對應`factor_ic.START_DATE`=2010起、`holdout.VAL_END`=2024-12-31
止）× 兩個市場（sii上市/otc上櫃），共30次查詢，沿用客戶端既有per-
(市場,年)parquet快取，重跑本腳本不會重複打MOPS。

**PIT檢查**：只保留`announcement_date <= effective_date`的事件（公告日
不晚於生效日，才代表市場在生效前就已經知情，能事前反應/事前已知未來會
發生）——`effective_date`早於`announcement_date`的事件視為回溯性公告
（實際生效已經發生後才對外說明），這種情況PIT不安全，本檔案直接排除
不納入樣本，不強行用announcement_date替代分析（避免混淆兩種不同資訊
結構）。

**跟子事件2的方法論差異（沿用同一套框架，僅換資料源與CAR起算日）**：CAR
用`effective_date`當t=0（而非announcement_date），因為`effective_date`
才是轉換價格實際變動、真正影響轉換經濟性的時點（跟子事件2用`ex_date`
當t=0是同一種選擇邏輯：t=0選「新條件真正生效」的日子，事件特徵
（discount／reset_magnitude）在t=0之前就已公開可得）。

**事前綁定樣本數門檻**：沿用子事件2的`MIN_EVENTS_PER_PERIOD=15`（同屬
全市場層級稀有公司行動事件，資料密度數量級接近，不是逐日連續觀測型的
子事件1）。

2026-09-07 hypothesis_queue排程接續，接續`HYPOTHESIS_QUEUE.md` #51條目
(g)段落「下一輪待辦(a)」：用子事件3已確認可行的新資料設計第1關cheap
gate，比照子事件2`cash_increase_dilution_gate1.py`同一套事件研究框架。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factor_ic import START_DATE
from mops_cb_conversion_price_client import fetch_conversion_price_events
from validation import holdout

N_PERMUTATIONS = 200
PERM_SEED = 20260907
BASE_ALPHA = 0.10
MIN_EVENTS_PER_PERIOD = 15
CAR_WINDOW_DAYS = 20  # ~1個月交易日，跟子事件2同一個窗口長度，事前綁定
SLEEP_BETWEEN_YEAR_QUERIES = 1.0  # 額外禮儀性間隔，疊加在客戶端內建的2.0秒之上

ROC_YEARS = [str(y) for y in range(99, 114)]  # 民國99~113年 = 西元2010~2024
MARKETS = ["sii", "otc"]


def _backfill_events() -> pd.DataFrame:
    """回填全部年度×市場的轉換價格變更公告，沿用客戶端per-(市場,年)快取。"""
    frames = []
    for typek in MARKETS:
        for year in ROC_YEARS:
            try:
                df = fetch_conversion_price_events(typek, year, use_cache=True)
            except Exception as e:  # noqa: BLE001 -- 單一(市場,年)查詢失敗不中斷整批回填
                print(f"  [{typek}/{year}] 查詢失敗，跳過：{e}")
                continue
            if not df.empty:
                df = df.copy()
                df["typek"] = typek
                df["roc_year"] = year
                frames.append(df)
            time.sleep(SLEEP_BETWEEN_YEAR_QUERIES)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _price_map(stock_id: str) -> dict | None:
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟cash_increase_dilution_gate1.py同一個容錯尺度
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return None
    if px.empty or len(px) < 260:
        return None
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in cb_conversion_price_reset_gate1")
    px = px.sort_values("date").reset_index(drop=True)
    return {"dates": px["date"].tolist(), "adj_close": px["adj_close"].to_numpy(dtype=float)}


def _car_window(dates: list[str], t0_date: str) -> tuple[int, int] | None:
    candidates = [d for d in dates if d >= t0_date]
    if not candidates:
        return None
    i0 = dates.index(candidates[0])
    i1 = i0 + CAR_WINDOW_DAYS
    if i1 >= len(dates):
        return None
    return i0, i1


def _market_map() -> dict:
    from finmind_client import load_dev
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in cb_conversion_price_reset_gate1")
    m = market_raw.sort_values("date").reset_index(drop=True)
    return {"dates": m["date"].tolist(), "close": m["close"].astype(float).to_numpy()}


def _car_for(dates, adj_close, mkt_date_idx, mkt_close, i0: int, i1: int) -> float | None:
    p0, p1 = adj_close[i0], adj_close[i1]
    if p0 <= 0 or np.isnan(p0) or np.isnan(p1):
        return None
    stock_ret = p1 / p0 - 1
    d0, d1 = dates[i0], dates[i1]
    mi0, mi1 = mkt_date_idx.get(d0), mkt_date_idx.get(d1)
    if mi0 is None or mi1 is None:
        return None
    m0, m1 = mkt_close[mi0], mkt_close[mi1]
    if m0 <= 0:
        return None
    return stock_ret - (m1 / m0 - 1)


def _ic_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n < 10:
        return {"label": label, "n": n, "ic": float("nan"), "p": float("nan")}
    rho, p = spearmanr(df["reset_magnitude"], df["car"])
    return {"label": label, "n": n, "ic": float(rho), "p": float(p)}


def main():
    print("=== 假設#51子事件3(可轉債轉換價格重設) 事件條件式CAR 第1關cheap gate ===")
    print(f"回填{len(MARKETS)}個市場 x {len(ROC_YEARS)}個民國年（{ROC_YEARS[0]}~{ROC_YEARS[-1]}），"
          f"沿用客戶端per-(市場,年)快取，重跑不重複打MOPS")
    raw = _backfill_events()
    if raw.empty:
        print("SANITY FAIL: 回填後零事件（不是無訊號，是資料層有問題）。")
        return {"passes": False, "reason": "no_events_found"}
    print(f"回填完成：{len(raw)}筆轉換價格變更公告原始列（含向上/向下/未解析出價格）")

    # 只留下向下重設（本假設核心主張）且新舊價格皆已成功解析
    down = raw[
        raw["old_price"].notna() & raw["new_price"].notna() & (raw["new_price"] < raw["old_price"])
    ].copy()
    down["reset_magnitude"] = (down["old_price"] - down["new_price"]) / down["old_price"]
    n_up_or_unparsed = len(raw) - len(down)
    print(f"向下重設且成功解析新舊價格：{len(down)}筆（另有{n_up_or_unparsed}筆向上重設/未解析出價格，不納入）")

    # PIT檢查：公告日不得晚於生效日
    down = down[down["announcement_date"].notna() & down["effective_date"].notna()].copy()
    pit_ok = down[down["announcement_date"] <= down["effective_date"]].copy()
    n_pit_dropped = len(down) - len(pit_ok)
    print(f"PIT檢查（公告日<=生效日）：保留{len(pit_ok)}筆，排除{n_pit_dropped}筆回溯性公告")
    if pit_ok.empty:
        print("SANITY FAIL: PIT檢查後零事件可用。")
        return {"passes": False, "reason": "no_pit_safe_events"}

    stock_ids = sorted(pit_ok["co_id"].unique().tolist())
    mkt = _market_map()
    mkt_date_idx = {d: i for i, d in enumerate(mkt["dates"])}

    rows = []
    n_price_ok = 0
    for i, sid in enumerate(stock_ids):
        pm = _price_map(sid)
        if pm is None:
            continue
        n_price_ok += 1
        dates = pm["dates"]
        sub_events = pit_ok[pit_ok["co_id"] == sid]
        for _, e in sub_events.iterrows():
            win = _car_window(dates, e["effective_date"])
            if win is None:
                continue
            i0, i1 = win
            car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt["close"], i0, i1)
            if car is None:
                continue
            rows.append({
                "stock_id": sid, "effective_date": e["effective_date"],
                "announcement_date": e["announcement_date"],
                "window_start": dates[i0], "window_end": dates[i1],
                "reset_magnitude": e["reset_magnitude"], "car": car,
            })
        if (i + 1) % 20 == 0:
            print(f"  progress {i+1}/{len(stock_ids)}檔, {n_price_ok}檔有價格, {len(rows)}筆事件可用 so far")

    if not rows:
        print("SANITY FAIL: 零事件可用（不是無訊號，是資料層問題）。")
        return {"passes": False, "reason": "no_events_usable"}

    ev = pd.DataFrame(rows).drop_duplicates(subset=["stock_id", "effective_date"])
    holdout.assert_no_holdout_leakage(ev, date_col="window_end", context="cb_conversion_price_reset_gate1 events (final)")
    print(f"\n{n_price_ok}/{len(stock_ids)}檔股票有可用價格，最終窗口+重設幅度資料皆可用事件數={len(ev)}")
    print(f"reset_magnitude: mean={ev['reset_magnitude'].mean():.4f} median={ev['reset_magnitude'].median():.4f} "
          f"min={ev['reset_magnitude'].min():.4f} max={ev['reset_magnitude'].max():.4f}")

    train = holdout.cap_to_train(ev, date_col="window_end")
    val = holdout.validation_slice(ev, date_col="window_end")

    train_stats = _ic_stats(train, "TRAIN")
    val_stats = _ic_stats(val, "VAL")
    print(f"\nTRAIN IC={train_stats['ic']:+.4f} (p={train_stats['p']:.4f}, n={train_stats['n']})")
    print(f"VAL   IC={val_stats['ic']:+.4f} (p={val_stats['p']:.4f}, n={val_stats['n']})")

    same_sign = (
        not pd.isna(train_stats["ic"]) and not pd.isna(val_stats["ic"])
        and np.sign(train_stats["ic"]) == np.sign(val_stats["ic"]) and train_stats["ic"] != 0
    )

    rng = np.random.RandomState(PERM_SEED)
    val_x = val["reset_magnitude"].to_numpy()
    val_car = val["car"].to_numpy()
    perm_ics = []
    if len(val) >= 10:
        for _ in range(N_PERMUTATIONS):
            shuffled = rng.permutation(val_x)
            rho, _ = spearmanr(shuffled, val_car)
            if not np.isnan(rho):
                perm_ics.append(float(rho))
    perm_ics = np.array(perm_ics)

    real_val_ic = val_stats["ic"]
    # 事前綁定方向為負（reset_magnitude越大→car越負），percentile鏡射：
    # 觀測IC比多少比例的null draw更負才算贏過隨機控制組（跟子事件2同一套鏡射）
    if len(perm_ics) > 0 and not pd.isna(real_val_ic):
        null_pct = 100.0 * float(np.mean(perm_ics >= real_val_ic))
    else:
        null_pct = float("nan")
    required_pct = 100.0 * (1 - BASE_ALPHA)
    print(f"\nVAL IC={real_val_ic:+.4f} vs {len(perm_ics)}次洗牌控制組null分布"
          f"percentile={null_pct:.1f}（事前綁定方向為負，需要>={required_pct:.1f}）")
    print(f"same_sign(TRAIN/VAL)={same_sign}")

    if len(val) >= 20:
        val_q = val.copy()
        val_q["q"] = pd.qcut(val_q["reset_magnitude"].rank(method="first"), 4, labels=False)
        q_means = val_q.groupby("q")["car"].mean()
        print(f"VAL四分位mean_CAR (q0最小重設幅度 -> q3最大重設幅度): {q_means.to_dict()}")

    reasons = []
    if train_stats["n"] < MIN_EVENTS_PER_PERIOD or val_stats["n"] < MIN_EVENTS_PER_PERIOD:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']}, 門檻{MIN_EVENTS_PER_PERIOD})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(val_stats["ic"]) or val_stats["ic"] >= 0:
        reasons.append("VAL期IC非負（事前綁定方向為負：重設幅度越大，生效後CAR應越負）")
    if pd.isna(null_pct) or null_pct < required_pct:
        reasons.append(f"null percentile={null_pct:.1f}未過門檻{required_pct:.1f}")
    if pd.isna(val_stats["p"]) or val_stats["p"] >= BASE_ALPHA:
        reasons.append(f"VAL Spearman p={val_stats['p']:.4f}未達顯著水準({BASE_ALPHA})")

    passes = len(reasons) == 0
    print(f"\n=== CHEAP GATE {'PASS' if passes else 'FAIL'} ===" + (f"  reasons: {reasons}" if reasons else ""))

    return {
        "passes": passes, "reasons": reasons,
        "train": train_stats, "val": val_stats,
        "null_percentile": null_pct, "required_percentile": required_pct,
        "same_sign": same_sign, "n_stocks_usable": n_price_ok, "n_events_usable": len(ev),
        "n_raw_announcements": len(raw), "n_down_resets": len(down), "n_pit_safe": len(pit_ok),
    }


if __name__ == "__main__":
    main()
