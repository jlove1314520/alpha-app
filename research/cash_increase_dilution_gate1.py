"""`HYPOTHESIS_QUEUE.md` #51 子事件2（現金增資除權參考價）第1關cheap gate。

**經濟機制（跟已測過的子事件1不同，但同屬#51「強制交易者」大類）**：
子事件1測的是「除息停止過戶前的強制回補視窗」，強制交易者是**空頭**（融券
部位必須回補）。這裡測的是現金增資的**另一群結構性交易者**：參與現金增資
認股的股東，是用比市價**折價**的認股價格拿到新股。折價幅度越大，代表這批
新股一旦可以流通（除權參考價生效之後），持有人「用折價成本换市價賣出」的
套利誘因越強——**折價幅度本身是公開已知的資訊（來自公告日的認股價格與
市價），日期（除權交易日）也是事前已知的**，完全符合`#51`「有一群人不管
價格都必須交易，而且日期事前已知」的核心主張，只是換了另一種強制交易者
（認股套利者 vs 融券回補者），機制方向也相反（子事件1預測強制買盤推升
超額報酬為正，這裡預測強制/準結構性賣壓使超額報酬為負）。

**事前綁定假設**：`discount`（認股價相對公告日前市價的折價幅度）越大，
除權交易日之後N個交易日的累積超額報酬（CAR）應該越**負**——折價套利誘因
越強，潛在賣壓越大。`discount = (announce_price - CashIncreaseSubscriptionpRrice)
/ announce_price`，其中`announce_price`是`AnnouncementDate`當天或之前
最近一筆的還原後收盤價（PIT安全：折價幅度在事件發生前就已公開可得）。

**資料可行性（`HYPOTHESIS_QUEUE.md` #51條目「資料可行性查證」段落已於
本輪之前完成查證，本檔案沿用結論，不重新查證）**：FinMind
`TaiwanStockDividend`（本機快取2170檔，零新增API呼叫即可篩出事件清單）
含`CashIncreaseSubscriptionRate`（配股率，篩事件用）、
`CashIncreaseSubscriptionpRrice`（認股價，FinMind原始欄位拼字本身如此，
非本檔案筆誤）、`CashExDividendTradingDate`（除權交易日，t=0）、
`AnnouncementDate`（公告日，已驗證118/118事件`AnnouncementDate<
ex_date`成立，PIT無虞）。

**跟子事件1的方法論差異（刻意，不是疏漏）**：子事件1用`factor_ic.py`
固定300檔隨機樣本（跨因子比較用），但現金增資是**稀有公司行動事件**，
限制在300檔隨機樣本會把全市場僅約118筆事件砍到剩約20筆、遠不足以拆
TRAIN/VAL兩期分別檢定。**改用「全市場曾發生過現金增資事件的公司」當
宇宙**——這跟`#40`買回股份CAR gate（`buyback_car_gate.py`，宇宙是MOPS
抓到的全市場買回公告公司，同樣不是固定300檔抽樣）同一種事件研究設計
慣例，不是為了製造樣本數而破例。

**控制組/顯著性檢定**：跟`forced_short_covering_gate1.py`同一套Spearman
IC + VAL期洗牌permutation null框架，但方向相反（預測`discount`與`car`
呈**負相關**），null percentile計算據此鏡射：`null_pct = 100 * mean(
perm_ics >= real_val_ic)`（觀測IC比大多數null draw更負，才算贏過隨機
控制組），需要>=90.0（跟其餘cheap gate同一個alpha=0.10單邊門檻）。

**事前綁定的樣本數門檻（比子事件1的30更低，原因寫在這裡，不是看到結果
後才調整）**：現金增資是全市場層級的稀有事件（全歷史僅約118筆，遠少於
子事件1每日連續觀測的融券部位），`MIN_EVENTS_PER_PERIOD=15`，低於子
事件1的30，因為這是不同資料密度的事件類別，一樣要求TRAIN/VAL兩期各自
達標、不得混併計算規避門檻。

**bug修正記錄（本輪首次跑出結果後發現並修正，不是事後調參）**：第一版
用`adjust.py::adjusted_price_series()`的還原後收盤價（`adj_close`）計算
`announce_price`，結果`discount`出現不合理的極端值（min=-3.49），因為
`adj_close`是**還原股價**（依`adjust.py`docstring說明：backward
adjustment讓「最新一筆價格等於原始價格」，較舊日期的價格會被後續所有
公司行動的累積調整因子縮放）——拿它去跟`CashIncreaseSubscriptionpRrice`
這種**原始名目認股價**比較是蘋果比橘子，對距今越久、期間公司行動越多的
事件失真越嚴重。已修正為改用`TaiwanStockPrice`**原始收盤價**（`close`，
未還原）計算`announce_price`／`discount`（折價幅度本質上是名目金額
比較，理應用當時的名目市價，不是還原價），CAR計算維持用`adj_close`
不變（累積報酬需要還原股價才能正確跨越除權息，這部分沒有問題）。

2026-09-07 hypothesis_queue排程接續，接續round(e)「下一輪TW軌接手」選項
(iii)：用子事件2（已確認可行）設計對等的第1關cheap gate，作為子事件1
（已FAIL，僅連續比例規格）的獨立對照/補強，不是重測同一個子事件。
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from adjust import adjusted_price_series
from factor_ic import START_DATE
from validation import holdout

N_PERMUTATIONS = 200
PERM_SEED = 20260907
BASE_ALPHA = 0.10
MIN_EVENTS_PER_PERIOD = 15
CAR_WINDOW_DAYS = 20  # ~1 個月交易日，事前綁定，不因結果調整


def _load_cash_increase_events() -> pd.DataFrame:
    """掃描本機`TaiwanStockDividend`全量快取，篩出現金增資事件清單。

    零新增API呼叫——複用`forced_trader_events_probe.py::
    probe_cash_increase_announcement_lag()`已驗證過的同一批本機快取檔案。
    """
    files = glob.glob("data/raw/TaiwanStockDividend__*.parquet")
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f))
        except Exception:  # noqa: BLE001 -- 個別壞檔跳過，不中斷整批掃描
            continue
    if not frames:
        return pd.DataFrame()
    all_df = pd.concat(frames, ignore_index=True)
    needed = {
        "stock_id", "CashIncreaseSubscriptionRate", "CashIncreaseSubscriptionpRrice",
        "CashExDividendTradingDate", "AnnouncementDate",
    }
    if not needed.issubset(all_df.columns):
        return pd.DataFrame()
    sub = all_df[all_df["CashIncreaseSubscriptionRate"].fillna(0) != 0].copy()
    sub["ex_date"] = sub["CashExDividendTradingDate"].replace("", None)
    sub = sub[sub["ex_date"].notna()].copy()
    sub["subscription_price"] = pd.to_numeric(sub["CashIncreaseSubscriptionpRrice"], errors="coerce")
    sub = sub[sub["subscription_price"] > 0].copy()
    sub["announce_date"] = sub["AnnouncementDate"].replace("", None)
    sub = sub[sub["announce_date"].notna()].copy()
    # PIT安全門檻（已在#51資料可行性查證確認118/118成立，這裡再次強制檢查，
    # 不假設既有查證結果永遠成立）
    sub = sub[sub["announce_date"] < sub["ex_date"]].copy()
    return sub[["stock_id", "ex_date", "announce_date", "subscription_price"]].drop_duplicates()


def _price_map(stock_id: str) -> dict | None:
    try:
        px = adjusted_price_series(stock_id, START_DATE)
    except Exception as e:  # noqa: BLE001 -- 跟forced_short_covering_gate1.py同一個容錯尺度
        print(f"  [{stock_id}] price ERROR ({e}), dropping")
        return None
    if px.empty or len(px) < 260:
        return None
    holdout.assert_no_holdout_leakage(px, context=f"price {stock_id} in cash_increase_dilution_gate1")
    px = px.sort_values("date").reset_index(drop=True)

    from finmind_client import load_dev
    raw = load_dev("TaiwanStockPrice", stock_id, START_DATE)
    if raw.empty:
        return None
    holdout.assert_no_holdout_leakage(raw, context=f"raw price {stock_id} in cash_increase_dilution_gate1")
    raw = raw.sort_values("date").reset_index(drop=True)
    raw_close_by_date = dict(zip(raw["date"], pd.to_numeric(raw["close"], errors="coerce")))

    return {
        "dates": px["date"].tolist(),
        "adj_close": px["adj_close"].to_numpy(dtype=float),
        "raw_close_by_date": raw_close_by_date,
    }


def _announce_price(raw_close_by_date: dict, dates: list[str], announce_date: str) -> float | None:
    """最近一筆日期 <= announce_date的**原始（未還原）**收盤價，PIT安全。

    用原始收盤價而非還原股價，理由見本檔案模組docstring「bug修正記錄」
    小節——折價幅度是名目金額比較，須用當時的名目市價。
    """
    candidates = [d for d in dates if d <= announce_date]
    if not candidates:
        return None
    for d in reversed(candidates):
        p = raw_close_by_date.get(d)
        if p is not None and not pd.isna(p) and p > 0:
            return float(p)
    return None


def _car_window(dates: list[str], ex_date: str) -> tuple[int, int] | None:
    try:
        i0 = dates.index(ex_date)
    except ValueError:
        return None
    i1 = i0 + CAR_WINDOW_DAYS
    if i1 >= len(dates):
        return None
    return i0, i1


def _market_map() -> dict:
    from finmind_client import load_dev
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in cash_increase_dilution_gate1")
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
    rho, p = spearmanr(df["discount"], df["car"])
    return {"label": label, "n": n, "ic": float(rho), "p": float(p)}


def main():
    print("=== 假設#51子事件2(現金增資折價) 事件條件式CAR 第1關cheap gate ===")
    events = _load_cash_increase_events()
    if events.empty:
        print("SANITY FAIL: 本機快取掃描零事件（不是無訊號，是資料層有問題）。")
        return {"passes": False, "reason": "no_events_found"}
    stock_ids = sorted(events["stock_id"].unique().tolist())
    print(f"本機快取掃描：{len(events)}筆現金增資事件（含重複除權日去重後），"
          f"涉及{len(stock_ids)}檔不同股票（全市場層級，非固定300檔抽樣）")

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
        sub_events = events[events["stock_id"] == sid]
        for _, ev in sub_events.iterrows():
            announce_price = _announce_price(pm["raw_close_by_date"], dates, ev["announce_date"])
            if announce_price is None:
                continue
            discount = (announce_price - ev["subscription_price"]) / announce_price
            win = _car_window(dates, ev["ex_date"])
            if win is None:
                continue
            i0, i1 = win
            car = _car_for(dates, pm["adj_close"], mkt_date_idx, mkt["close"], i0, i1)
            if car is None:
                continue
            rows.append({
                "stock_id": sid, "ex_date": ev["ex_date"], "announce_date": ev["announce_date"],
                "window_start": dates[i0], "window_end": dates[i1],
                "discount": discount, "car": car,
            })
        if (i + 1) % 20 == 0:
            print(f"  progress {i+1}/{len(stock_ids)}檔, {n_price_ok}檔有價格, {len(rows)}筆事件可用 so far")

    if not rows:
        print("SANITY FAIL: 零事件可用（不是無訊號，是資料層有問題）。")
        return {"passes": False, "reason": "no_events_usable"}

    ev = pd.DataFrame(rows)
    holdout.assert_no_holdout_leakage(ev, date_col="window_end", context="cash_increase_dilution_gate1 events (final)")
    print(f"\n{n_price_ok}/{len(stock_ids)}檔股票有可用價格，最終窗口+折價資料皆可用事件數={len(ev)}")
    print(f"discount: mean={ev['discount'].mean():.4f} median={ev['discount'].median():.4f} "
          f"min={ev['discount'].min():.4f} max={ev['discount'].max():.4f}")

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
    val_discount = val["discount"].to_numpy()
    val_car = val["car"].to_numpy()
    perm_ics = []
    if len(val) >= 10:
        for _ in range(N_PERMUTATIONS):
            shuffled = rng.permutation(val_discount)
            rho, _ = spearmanr(shuffled, val_car)
            if not np.isnan(rho):
                perm_ics.append(float(rho))
    perm_ics = np.array(perm_ics)

    real_val_ic = val_stats["ic"]
    # 事前綁定方向為負（discount越大→car越負），percentile鏡射：
    # 觀測IC比多少比例的null draw更負才算贏過隨機控制組
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
        val_q["q"] = pd.qcut(val_q["discount"].rank(method="first"), 4, labels=False)
        q_means = val_q.groupby("q")["car"].mean()
        print(f"VAL四分位mean_CAR (q0最低discount -> q3最高discount): {q_means.to_dict()}")

    reasons = []
    if train_stats["n"] < MIN_EVENTS_PER_PERIOD or val_stats["n"] < MIN_EVENTS_PER_PERIOD:
        reasons.append(f"樣本數過少 (train_n={train_stats['n']}, val_n={val_stats['n']}, 門檻{MIN_EVENTS_PER_PERIOD})")
    if not same_sign:
        reasons.append("train/val正負號不一致")
    if pd.isna(val_stats["ic"]) or val_stats["ic"] >= 0:
        reasons.append("VAL期IC非負（事前綁定方向為負：折價幅度越大，除權後CAR應越負）")
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
    }


if __name__ == "__main__":
    main()
