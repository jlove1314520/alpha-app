"""`HYPOTHESIS_QUEUE.md` #35 賣出台指選擇權波動度風險溢酬（VRP）第1關
最便宜檢定：確認IV是否系統性高於後續已實現波動度（RV），不需要真的建立
選擇權部位模擬。

**資料可行性查證結論（本輪，2026-09-05 hypothesis_queue排程）**：
`TaiwanOptionDaily`（FinMind，欄位見下）**不含隱含波動度欄位**，需要
從選擇權價格反推。經查有兩條路：①用Black-Scholes數值解（需要無風險
利率+股利率假設+數值解法，較貴）、②用Brenner-Subrahmanyam(1988)
近似公式（ATM選擇權：C≈0.4×S×σ×√T，跨式：straddle≈0.8×S×σ×√T，
不需要利率/股利假設、不需要數值解，是文獻上公認的「快速反推ATM隱含
波動度」標準做法）——本輪採用②，符合`HYPOTHESIS_QUEUE_PROTOCOL.md`
「第1關只能用便宜且決定性的證據」的精神，且`HYPOTHESIS_QUEUE.md` #35
條目本身也明講「這是第1關最便宜的檢定」。

`TaiwanOptionDaily`實測欄位：date/option_id/contract_date/strike_price/
call_put/open/max/min/close/volume/settlement_price/open_interest/
trading_session。`contract_date`格式為`YYYYMM`（月合約）或`YYYYMMWn`
（週合約，2018年後才有）——**本輪只用月合約**（`^\\d{6}$`），排除週合約，
理由跟#31排除夜盤同一個精神：週合約覆蓋期間不對稱（2015-2017沒有），
混用會在早期/晚期造成人為口徑斷點。

**方法（沿用專案既有基礎設施，不重新發明）**：
- `finmind_client.load_dev()`（唯一sanctioned entry point，已holdout-safe
  截斷在VAL_END）逐年抓`TaiwanOptionDaily`（沿用#31`option_pcr_gate.py`
  逐年抓取模式，本輪執行時發現全部年度已有本機parquet快取，無需真的
  打API）。
- `yf_price_client.fetch_yf_index()`（沿用#34同一個基礎設施）取TAIEX
  (^TWII)日收盤，同樣holdout-safe。
- 只用`trading_session=='position'`（日盤），跟#31同一個口徑決定。
- 台指選擇權結算日=合約月份第三個星期三（TXO/TX標準規則），本輪內建
  `third_wednesday()`計算，不依賴外部行事曆資料源。
- 每個交易日，在當天可用的月合約中，挑**距到期天數（日曆天）最接近
  30天、且落在[10,45]天區間**的合約（避開到期週雜訊+避開太遠期流動性
  稀薄的合約），非該區間的候選一律跳過那一天（不強湊）。
- 在挑中的(date, contract_date)組合裡，找**價平履約價**（離當日TAIEX
  收盤最近、且call/put兩邊收盤價都>0的履約價，兩者皆為0代表當天無成交
  可用，跳過）。
- straddle_price = call_close + put_close，IV_approx = straddle_price /
  (0.8 × TAIEX收盤 × √(到期天數/365.25))（Brenner-Subrahmanyam）。
- RV_forward：以該筆觀測的到期天數為窗口長度，往未來抓TAIEX同等長度
  期間的日對數報酬年化標準差（std×√252）。**此為歷史VRP存在性診斷
  分析，非即時交易訊號**——用到option發行當下之後的已實現波動度是VRP
  文獻的標準做法（Carr-Wu 2009等），不是未來函數污染即時決策；但仍
  嚴格要求該窗口終點不得超過VAL_END，超過就跳過整筆觀測，holdout
  邊界不因為是診斷分析就放寬。
- **抽樣頻率**：每5個交易日抽一筆觀測（而非逐日），理由：同一合約下
  逐日觀測的RV窗口高度重疊（今天到期30天、明天到期29天，兩者RV窗口
  幾乎完全重合），逐日使用會嚴重高估有效樣本數、低估真實顯著性，
  抽樣降低但不完全消除序列相關，是VRP診斷分析的常見做法，非任意
  湊數。

**判定標準（比照本佇列「幅度非零/train-val同號/統計顯著」三項判準
精神，但本測試的自然虛無假設是「IV-RV價差平均=0」，直接用單樣本
t檢定/Wilcoxon符號檢定更適合這種時序價差診斷，取代本佇列cross-
sectional因子慣用的洗牌null——這是方法論調整，不是迴避既有框架，
理由已寫在此docstring）**：
1. 幅度非零：TRAIN/VAL兩期平均IV-RV價差幅度需明顯偏離雜訊量級
   （事前定門檻：|mean spread|>=1個百分點年化波動度）。
2. train/val同號：兩期價差方向一致（依VRP文獻預期為正，IV系統性
   高於RV）。
3. 統計顯著：兩期單樣本t檢定（H1: mean>0）p<0.05，且Wilcoxon符號
   檢定同樣顯著（穩健性交叉確認，避免t檢定常態假設不成立時誤判）。
三項皆過才判CHEAP_PASS，任一項未過依協定直接判FAIL，不做主觀裁量。

2026-09-05由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程新增，佇列#35第1關
起跑。
"""
from __future__ import annotations

import re
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import stats

from finmind_client import load_dev
from yf_price_client import fetch_yf_index
from validation.holdout import TRAIN_END, VAL_END

OPTION_ID = "TXO"
OPTION_START = "2015-01-01"
SAMPLE_STRIDE = 5  # 每5個交易日抽一筆，降低同合約重疊窗口的序列相關
TARGET_DTE = 30  # 目標到期天數(日曆天)
DTE_BAND = (10, 45)  # 允許的到期天數區間
MONTHLY_CONTRACT_RE = re.compile(r"^\d{6}$")


def third_wednesday(year: int, month: int) -> pd.Timestamp:
    """台指選擇權/期貨標準結算日：合約月份第三個星期三。"""
    first_day = pd.Timestamp(year=year, month=month, day=1)
    # weekday(): Monday=0 ... Wednesday=2
    offset = (2 - first_day.weekday()) % 7
    first_wed = first_day + timedelta(days=offset)
    return first_wed + timedelta(weeks=2)


def build_option_frame() -> pd.DataFrame:
    """回傳columns: date, contract_date, expiry, strike_price, call_close,
    put_close。只含月合約、日盤、call/put皆有收盤價>0的(date,contract_date,
    strike)組合。"""
    frames = []
    start_year = int(OPTION_START[:4])
    end_year = int(VAL_END[:4])
    for yr in range(start_year, end_year + 1):
        yr_start = f"{yr}-01-01"
        yr_end = f"{yr}-12-31"
        chunk = load_dev("TaiwanOptionDaily", OPTION_ID, yr_start, end_date=yr_end, date_col="date")
        if not chunk.empty:
            frames.append(chunk)
    if not frames:
        raise RuntimeError("TaiwanOptionDaily(TXO)逐年抓取後仍全數空資料，第1關無法起跑")
    opt = pd.concat(frames, ignore_index=True)
    opt = opt[opt["trading_session"] == "position"].copy()
    opt = opt[opt["contract_date"].astype(str).str.match(MONTHLY_CONTRACT_RE)].copy()
    opt["date"] = pd.to_datetime(opt["date"])
    opt["close"] = pd.to_numeric(opt["close"], errors="coerce")
    opt["strike_price"] = pd.to_numeric(opt["strike_price"], errors="coerce")
    opt = opt.dropna(subset=["close", "strike_price"])
    opt = opt[opt["close"] > 0]

    calls = opt[opt["call_put"] == "call"][["date", "contract_date", "strike_price", "close"]].rename(
        columns={"close": "call_close"}
    )
    puts = opt[opt["call_put"] == "put"][["date", "contract_date", "strike_price", "close"]].rename(
        columns={"close": "put_close"}
    )
    merged = calls.merge(puts, on=["date", "contract_date", "strike_price"], how="inner")

    expiry_cache: dict[str, pd.Timestamp] = {}
    def _expiry(cd: str) -> pd.Timestamp:
        if cd not in expiry_cache:
            y, m = int(cd[:4]), int(cd[4:6])
            expiry_cache[cd] = third_wednesday(y, m)
        return expiry_cache[cd]

    merged["expiry"] = merged["contract_date"].astype(str).map(_expiry)
    return merged


def select_atm_observations(opt: pd.DataFrame, taiex: pd.DataFrame) -> pd.DataFrame:
    """每個交易日挑到期天數最接近30天(限[10,45]區間)的合約，再挑該合約
    裡離TAIEX收盤最近的價平履約價。回傳columns: date, dte_calendar,
    taiex_close, straddle_price, iv_approx。"""
    tw = taiex[["date", "close"]].rename(columns={"close": "taiex_close"}).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    df = opt.merge(tw, on="date", how="inner")
    df["dte_calendar"] = (df["expiry"] - df["date"]).dt.days
    lo, hi = DTE_BAND
    df = df[(df["dte_calendar"] >= lo) & (df["dte_calendar"] <= hi)].copy()
    if df.empty:
        return pd.DataFrame(columns=["date", "dte_calendar", "taiex_close", "straddle_price", "iv_approx"])

    df["dte_dist"] = (df["dte_calendar"] - TARGET_DTE).abs()
    # 每天先挑dte最接近目標的合約(可能同一天有多個月合約落在區間內)
    idx_contract = df.groupby("date")["dte_dist"].idxmin()
    chosen_contract = df.loc[idx_contract, ["date", "contract_date", "dte_calendar"]]
    df2 = df.merge(chosen_contract, on=["date", "contract_date", "dte_calendar"], how="inner")

    df2["strike_dist"] = (df2["strike_price"] - df2["taiex_close"]).abs()
    idx_strike = df2.groupby("date")["strike_dist"].idxmin()
    atm = df2.loc[idx_strike].copy()

    atm["straddle_price"] = atm["call_close"] + atm["put_close"]
    t_years = atm["dte_calendar"] / 365.25
    atm["iv_approx"] = atm["straddle_price"] / (0.8 * atm["taiex_close"] * np.sqrt(t_years))
    atm = atm.replace([np.inf, -np.inf], np.nan).dropna(subset=["iv_approx"])
    return atm[["date", "dte_calendar", "taiex_close", "straddle_price", "iv_approx"]].sort_values("date").reset_index(drop=True)


def compute_forward_rv(atm: pd.DataFrame, taiex: pd.DataFrame) -> pd.DataFrame:
    """對每筆觀測，用TAIEX從date起、往未來dte_calendar個日曆天的日報酬
    年化標準差當RV_forward。窗口終點超過VAL_END的觀測整筆丟棄(holdout
    邊界不因診斷分析而放寬)。"""
    tw = taiex[["date", "close"]].copy()
    tw["date"] = pd.to_datetime(tw["date"])
    tw = tw.sort_values("date").reset_index(drop=True)
    tw["log_ret"] = np.log(tw["close"] / tw["close"].shift(1))
    val_end_ts = pd.Timestamp(VAL_END)

    rows = []
    for _, r in atm.iterrows():
        window_end = r["date"] + timedelta(days=int(r["dte_calendar"]))
        if window_end > val_end_ts:
            continue
        mask = (tw["date"] > r["date"]) & (tw["date"] <= window_end)
        rets = tw.loc[mask, "log_ret"].dropna()
        if len(rets) < 5:
            continue
        rv = rets.std(ddof=1) * np.sqrt(252)
        rows.append({
            "date": r["date"],
            "dte_calendar": r["dte_calendar"],
            "iv_approx": r["iv_approx"],
            "rv_forward": rv,
            "spread": r["iv_approx"] - rv,
        })
    return pd.DataFrame(rows)


def evaluate_period(spread: pd.Series, label: str) -> dict:
    n = len(spread)
    if n < 8:
        return {"label": label, "n": n, "mean": np.nan, "median": np.nan,
                "pct_positive": np.nan, "t_p": np.nan, "wilcoxon_p": np.nan}
    mean_spread = float(spread.mean())
    median_spread = float(spread.median())
    pct_positive = float((spread > 0).mean())
    t_stat, t_p_two = stats.ttest_1samp(spread, 0.0)
    t_p_one = t_p_two / 2 if t_stat > 0 else 1 - t_p_two / 2
    try:
        w_stat, w_p_two = stats.wilcoxon(spread, alternative="greater")
        w_p = w_p_two
    except ValueError:
        w_p = np.nan
    return {
        "label": label, "n": n, "mean": mean_spread, "median": median_spread,
        "pct_positive": pct_positive, "t_p": float(t_p_one), "wilcoxon_p": float(w_p),
    }


def main() -> None:
    print("=== VRP第1關cheap gate：載入選擇權資料 ===")
    opt = build_option_frame()
    print(f"月合約call/put皆有成交的(date,contract,strike)列數: {len(opt)}")

    print("=== 載入TAIEX日收盤 ===")
    taiex = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    print(f"TAIEX資料筆數: {len(taiex)}, 範圍: {taiex['date'].min()}~{taiex['date'].max()}")

    print("=== 挑選每日ATM觀測 ===")
    atm = select_atm_observations(opt, taiex)
    print(f"ATM觀測筆數(挑合約+挑履約價後): {len(atm)}")
    if atm.empty:
        print("FATAL: 挑不出任何ATM觀測，第1關無法判定")
        return

    print("=== 計算前瞻已實現波動度(RV) ===")
    result = compute_forward_rv(atm, taiex)
    print(f"含有效RV的觀測筆數(已剔除窗口超出VAL_END者): {len(result)}")
    if result.empty:
        print("FATAL: 無任何觀測通過holdout邊界檢查，第1關無法判定")
        return

    result = result.sort_values("date").reset_index(drop=True)
    sampled = result.iloc[::SAMPLE_STRIDE].reset_index(drop=True)
    print(f"每{SAMPLE_STRIDE}個交易日抽樣後觀測筆數: {len(sampled)}")

    train = sampled[sampled["date"] <= pd.Timestamp(TRAIN_END)]
    val = sampled[(sampled["date"] > pd.Timestamp(TRAIN_END)) & (sampled["date"] <= pd.Timestamp(VAL_END))]

    train_eval = evaluate_period(train["spread"], "TRAIN")
    val_eval = evaluate_period(val["spread"], "VAL")

    print("\n=== 結果 ===")
    for ev in (train_eval, val_eval):
        print(f"{ev['label']}: n={ev['n']}, mean_spread={ev['mean']:.4f}, "
              f"median_spread={ev['median']:.4f}, pct_IV>RV={ev['pct_positive']:.3f}, "
              f"t檢定p(H1:mean>0)={ev['t_p']:.4f}, Wilcoxon p={ev['wilcoxon_p']:.4f}")

    result.to_csv("data/vrp_gate_observations.csv", index=False)
    sampled.to_csv("data/vrp_gate_sampled.csv", index=False)
    print("\n完整觀測已存 data/vrp_gate_observations.csv, 抽樣後 data/vrp_gate_sampled.csv")

    mag_ok = (abs(train_eval["mean"]) >= 0.01) and (abs(val_eval["mean"]) >= 0.01)
    same_sign = np.sign(train_eval["mean"]) == np.sign(val_eval["mean"]) and train_eval["mean"] > 0
    sig_ok = (train_eval["t_p"] < 0.05) and (val_eval["t_p"] < 0.05) and \
             (train_eval["wilcoxon_p"] < 0.05) and (val_eval["wilcoxon_p"] < 0.05)

    print(f"\n判準1(幅度非零>=1pp): {mag_ok}")
    print(f"判準2(train/val同號且為正): {same_sign}")
    print(f"判準3(t檢定+Wilcoxon皆p<0.05): {sig_ok}")
    verdict = "CHEAP_PASS" if (mag_ok and same_sign and sig_ok) else "FAIL"
    print(f"\n=== 第1關判定: {verdict} ===")


if __name__ == "__main__":
    main()
