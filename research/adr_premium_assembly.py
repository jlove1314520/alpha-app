"""`HYPOTHESIS_QUEUE.md` #45 存託憑證（ADR）溢價/折價收斂——地基建置第(c)步：
PIT時序對齊邏輯 + 資料組裝腳本。**本腳本只組裝並輸出premium時間序列，不做
第1關cheap gate統計檢定**（那是下一輪的事，見協定第2節「先把地基做好...
不用強求一次做完全部」）。

依`HYPOTHESIS_QUEUE.md` #45條目「下一輪待辦」完成前置事項：
1. CHT官方比率：已用SEC EDGAR FY2006 20-F(`cht-20f...d20f.htm`)逐字確認
   "each of which represents ten of our common shares"，1 ADS = 10股，
   WebSearch交叉比對FY2020 20-F摘要同為10股，判定為可信官方數字（非網路
   二手轉述）。
2. ASX斷點處理：採用「本輪先聚焦2018年合併後（ASX對應3711日月光投控）
   這段乾淨區間」方案，2018年前的2311日月光半導體工業直接排除，理由見
   `HYPOTHESIS_QUEUE.md` #45條目。用`adr_convergence_probe.py`發現的兩次
   跳空日期（2018-04-18/2018-05-02）+ 3711本地股價實際最早交易日
   （2018-05-02，見本輪查證），確認斷點日=2018-05-02（第二次跳空日，
   同時是3711新股掛牌首個交易日，早於此日ASX對應的是舊法人2311，資料
   組裝直接排除）。
3. TSM/UMC比率：未查到存託銀行逐年正式文件，網路二手來源一致（皆為5股
   =1ADR，未提及變動記錄），依#45條目「下一輪待辦3」判準視為可信度中等
   但可接受的證據，帶著已知限制往下走（不等同資料不可及判FAIL）。本腳本
   額外用premium量級是否落在合理範圍（數個百分點，而非數倍離譜）交叉
   驗證比率方向與大小是否明顯錯誤——如果錯了會在描述統計裡一眼看出來。

**PIT對齊邏輯（本腳本設計核心，事前綁定，不是跑完看結果才選）**：
台股與美股ADR不同時區交易，同一個日期標籤(date)代表的並非同一個時間點。
台股「T日」收盤發生於協調世界時(UTC)約當日05:30；美股「T日」（美股行事曆
標籤）開盤在UTC同日14:30、收盤在UTC同日21:00——也就是說，美股標籤T日的
收盤，時間上發生在台股標籤T日收盤「之後」約15.5小時，而不是之前。因此：
- 用台股T日收盤去比對「美股標籤T日」的ADR收盤，等於拿了台股T日收盤當下
  還沒發生的未來資訊（未來函數）。
- 正確做法：台股T日收盤應該比對「嚴格早於T的最近一個美股交易日」收盤
  （通常是T-1，但遇假期錯開時可能更早），因為那才是台股T日收盤當下已經
  公開、確定存在的最新ADR價格。
實作用`pandas.merge_asof(..., direction="backward", allow_exact_matches=False)`
達成「嚴格早於」的比對，`allow_exact_matches=False`是關鍵，否則會誤用
同標籤日期的ADR價格（未來函數）。

**匯率**：沿用`fx_twd_gate.py`（#32）已驗證可行的`TaiwanExchangeRate`
`spot_sell`欄位+逐年分批抓取模式（避免FinMind 502），邏輯照搬但`FX_START`
改用更早的2006年（實測查證資料實際涵蓋起點約在此，早於此常態回傳空）——
#32原函式寫死2015年是那個橫斷面研究的刻意選擇，本假設是N僅4檔的時序
研究，需要盡量長的歷史，不宜直接沿用同一個常數。匯率跟台股同一個交易
日曆(台灣銀行報價)，用台股T日當天的匯率報價是PIT安全的（跟ADR不同，
不存在時區領先問題）。

**價格口徑選擇（本輪方法論決定，事前綁定）**：兩邊都用**原始未還原
收盤價**（非還原股價），不用`adjust.py`的還原序列。理由：ADR存託銀行機制
設計上，發放股票股利/現金股利時是由存託銀行對等調整ADS流通數量或走
pass-through配發，經濟上兩邊股東應同步反映在「當時的原始市價」上，不需要
（也不應該）對其中一邊做時間拉長的還原調整——若用還原價比對原始ADR價，
會隨著回溯時間拉長產生單邊系統性偏誤（還原價越往前墊得越高，ADR原始價
沒有對應墊高），這是本腳本刻意迴避的一個潛在bug，不是遺漏。

Author: hypothesis_queue排程，2026-09-06接續。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from finmind_client import load_dev
from validation.holdout import VAL_END

# 沿用`fx_twd_gate.py`（#32）逐年分批抓取TaiwanExchangeRate的既有模式（避免
# 一次跨多年呼叫`load_dev`遇到FinMind 502），但**不直接import該模組的
# `build_fx_series()`**——原函式的`FX_START`寫死在"2015-01-01"，是#32那個
# cross-sectional橫斷面研究刻意的選擇，跟本假設(#45)是時序極短(N僅4檔)的
# 時間序列研究不同，這裡需要盡量長的歷史（實測查證FinMind
# `TaiwanExchangeRate`資料實際從約2006年才有，早於此常態回傳空，非bug）。
FX_START = "2006-01-01"
FX_DATASET = "TaiwanExchangeRate"
FX_DATA_ID = "USD"
FX_RATE_COL = "spot_sell"


def build_fx_series(start_date: str = FX_START) -> pd.DataFrame:
    """回傳 columns: date(Timestamp,已排序), rate(spot_sell即期匯率)。

    邏輯與`fx_twd_gate.build_fx_series()`完全相同（逐年分批避免502），僅
    start_date可調整。
    """
    frames = []
    start_year = int(start_date[:4])
    end_year = int(VAL_END[:4])
    for yr in range(start_year, end_year + 1):
        yr_start = f"{yr}-01-01"
        yr_end = f"{yr}-12-31"
        chunk = load_dev(FX_DATASET, FX_DATA_ID, yr_start, end_date=yr_end, date_col="date")
        if not chunk.empty:
            frames.append(chunk)
    if not frames:
        raise RuntimeError(f"{FX_DATASET}({FX_DATA_ID})逐年抓取後仍全數空資料，地基組裝無法進行")
    fx = pd.concat(frames, ignore_index=True)
    if FX_RATE_COL not in fx.columns:
        raise RuntimeError(f"{FX_DATASET}回傳缺少{FX_RATE_COL!r}欄位，實際欄位: {list(fx.columns)}")
    fx["date"] = pd.to_datetime(fx["date"])
    fx["rate"] = pd.to_numeric(fx[FX_RATE_COL], errors="coerce")
    fx = fx.dropna(subset=["rate"])
    fx = fx[fx["rate"] > 0].copy()
    fx = fx.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    return fx[["date", "rate"]]


@dataclass(frozen=True)
class AdrSpec:
    ticker: str          # FinMind USStockPrice 代碼
    local_id: str        # FinMind TaiwanStockPrice 代碼
    ratio: float         # 1 ADR/ADS = ratio 股本地普通股
    start_date: str      # 本腳本組裝起始日（已排除已知結構性斷點區間）
    label: str
    ratio_confidence: str  # "official_sec_filing" | "secondary_source_consistent"


SPECS: list[AdrSpec] = [
    AdrSpec("TSM", "2330", 5.0, "2006-01-01", "台積電 (2330/TSM)", "secondary_source_consistent"),
    # UMC/CHT: 2026-09-06本輪實測發現重大結構性斷點——用比率5:1(UMC)/10:1(CHT)
    # 算出的premium在2006~2010年持續偏高(UMC年均34~54%、CHT年均15~37%)，
    # 2010~2011之交驟降到趨近0%並穩定至今，型態跟全程穩定的TSM(2~8%)明顯
    # 不同。查證發現UMC存管契約日期為"October 21, 2009"（WebSearch摘要，
    # 未逐字確認原始6-K/20-F文件），暗示比率極可能在該時點附近變更過，且
    # CHT同時間出現幾乎相同型態的斷點並非巧合，較可能是2009~2010年前後
    # 一波台灣ADR比率調整浪潮（非本輪查證範圍，留給未來需要更長歷史時再
    # 查證舊比率數字）。**本輪保守處置：兩者起始日皆設在斷點確定結束之後
    # 的2011-01-01，犧牲2006-2010這段比率有疑慮的早期歷史，換取乾淨可信的
    # 2011年後資料**——不是刪除證據，是誠實記錄成已知限制，若未來要用到
    # 更長歷史需先查到官方比率變更公告與確切生效日期。
    AdrSpec("UMC", "2303", 5.0, "2011-01-01", "聯電 (2303/UMC，2011年起，排除疑似比率變更的2006-2010)", "secondary_source_consistent_post2011_only"),
    AdrSpec("CHT", "2412", 10.0, "2011-01-01", "中華電信 (2412/CHT，2011年起，排除疑似比率變更的2006-2010)", "official_sec_filing_post2011_only"),
    # ASX對應3711日月光投控——2018年前(2311日月光半導體工業)舊法人直接排除，
    # 斷點日=2018-05-02（3711新股掛牌首日，見模組docstring）。
    AdrSpec("ASX", "3711", 2.0, "2018-05-02", "日月光投控 (3711/ASX，僅2018合併後區間)", "secondary_source_consistent"),
]


def _load_local(spec: AdrSpec) -> pd.DataFrame:
    df = load_dev("TaiwanStockPrice", spec.local_id, start_date=spec.start_date, end_date=VAL_END)
    if df.empty:
        return pd.DataFrame(columns=["date", "local_close"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["local_close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["local_close"])
    df = df[df["local_close"] > 0]
    return df[["date", "local_close"]].drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def _load_adr(spec: AdrSpec) -> pd.DataFrame:
    df = load_dev("USStockPrice", spec.ticker, start_date=spec.start_date, end_date=VAL_END)
    if df.empty:
        return pd.DataFrame(columns=["date", "adr_close"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["adr_close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["adr_close"])
    df = df[df["adr_close"] > 0]
    return df[["date", "adr_close"]].drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def assemble_one(spec: AdrSpec, fx: pd.DataFrame) -> pd.DataFrame:
    """回傳單一標的的PIT對齊premium時間序列。

    columns: ticker, date(本地台股交易日), local_close, adr_date(比對到的美股
    交易日，嚴格早於date), adr_close, adr_lag_days(date與adr_date相差日曆天數，
    用來檢查是否有異常長的缺口), fx_rate, implied_local_twd, premium。
    """
    local = _load_local(spec)
    adr = _load_adr(spec)
    if local.empty or adr.empty:
        print(f"  [{spec.ticker}] 本地或ADR資料為空（local={len(local)}列, adr={len(adr)}列），略過")
        return pd.DataFrame()

    adr_sorted = adr.rename(columns={"date": "adr_date"}).sort_values("adr_date").reset_index(drop=True)
    local_sorted = local.sort_values("date").reset_index(drop=True)

    merged = pd.merge_asof(
        local_sorted,
        adr_sorted,
        left_on="date",
        right_on="adr_date",
        direction="backward",
        allow_exact_matches=False,  # 關鍵：禁止同日期標籤比對，避免未來函數（見docstring PIT邏輯）
    )
    merged = merged.dropna(subset=["adr_date", "adr_close"]).reset_index(drop=True)

    merged = pd.merge(merged, fx[["date", "rate"]], on="date", how="inner")
    merged = merged.dropna(subset=["rate"])
    if merged.empty:
        print(f"  [{spec.ticker}] 對齊後(含匯率)為空，略過")
        return pd.DataFrame()

    merged["adr_lag_days"] = (merged["date"] - merged["adr_date"]).dt.days
    merged["implied_local_twd"] = (merged["adr_close"] / spec.ratio) * merged["rate"]
    merged["premium"] = merged["implied_local_twd"] / merged["local_close"] - 1.0
    merged["ticker"] = spec.ticker
    merged["fx_rate"] = merged["rate"]

    cols = ["ticker", "date", "local_close", "adr_date", "adr_close", "adr_lag_days",
            "fx_rate", "implied_local_twd", "premium"]
    return merged[cols]


def main() -> dict:
    print("=== #45 ADR premium PIT對齊資料組裝 ===")
    fx = build_fx_series()
    print(f"匯率序列(spot_sell): {len(fx)}列, {fx['date'].min()} ~ {fx['date'].max()}")

    all_frames = []
    summary = {}
    for spec in SPECS:
        print(f"\n--- {spec.label} (ratio=1:{spec.ratio}, confidence={spec.ratio_confidence}) ---")
        aligned = assemble_one(spec, fx)
        if aligned.empty:
            summary[spec.ticker] = {"n": 0}
            continue
        n = len(aligned)
        lag_desc = aligned["adr_lag_days"].describe()
        prem_desc = aligned["premium"].describe()
        n_long_gap = int((aligned["adr_lag_days"] > 5).sum())
        print(f"  對齊筆數: {n}, 日期範圍: {aligned['date'].min().date()} ~ {aligned['date'].max().date()}")
        print(f"  adr_lag_days: min={lag_desc['min']:.0f} median={aligned['adr_lag_days'].median():.0f} "
              f"max={lag_desc['max']:.0f}  (>5天缺口筆數: {n_long_gap}, {100.0*n_long_gap/n:.1f}%)")
        print(f"  premium描述統計: mean={prem_desc['mean']:+.4f} median={aligned['premium'].median():+.4f} "
              f"std={prem_desc['std']:.4f} min={prem_desc['min']:+.4f} max={prem_desc['max']:+.4f}")
        sane = abs(prem_desc["mean"]) < 0.5 and abs(aligned["premium"].median()) < 0.5
        print(f"  量級合理性檢查(|mean|,|median|<50%): {'PASS' if sane else 'FAIL——比率或方向可能有誤，需人工複查'}")
        summary[spec.ticker] = {
            "n": n, "date_range": (str(aligned["date"].min().date()), str(aligned["date"].max().date())),
            "premium_mean": float(prem_desc["mean"]), "premium_median": float(aligned["premium"].median()),
            "premium_std": float(prem_desc["std"]), "n_long_gap_pct": 100.0 * n_long_gap / n,
            "magnitude_sane": bool(sane),
        }
        all_frames.append(aligned)

    if not all_frames:
        print("\n所有標的皆組裝失敗，判定資料不可及")
        return {"verdict": "DATA_UNAVAILABLE", "summary": summary}

    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_csv("data/adr_premium_aligned.csv", index=False)
    print(f"\n已輸出 data/adr_premium_aligned.csv，共{len(combined)}列，{combined['ticker'].nunique()}檔標的。")
    print("狀態：地基建置(c)完成，尚未進第1關cheap gate（統計檢定留待下一輪）。")
    return {"verdict": "ASSEMBLY_DONE", "summary": summary, "n_total": len(combined)}


if __name__ == "__main__":
    main()
