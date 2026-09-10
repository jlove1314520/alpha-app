"""`HYPOTHESIS_QUEUE.md` #70 選擇權波動度偏斜（Volatility Skew）地基建置
(c)(d)：組裝逐日OTM put/call配對隱含波動度（IV）與skew指標時序。

**本輪範疇（只做(c)(d)，不進cheap gate）**：依`HYPOTHESIS_QUEUE.md` #70
條目「下一輪待辦(c)(d)」逐項完成——(c)改用`settlement_price`而非`close`
當OTM合約市價輸入，(d)組裝逐日OTM put/call配對+skew指標時序。**cheap
gate（skew vs 後續報酬相關性檢定）留給下一輪**，比照本假設過去每輪只做
一個字母步驟的節奏（(a)一輪、(b)一輪），維持「一輪一個有界工作單位」。

**(c) settlement_price而非close的理由（複述`#70`條目已查證結論，不重新
查證）**：TAIFEX官方頁確認`settlement_price`正常情況下等於當日最後一筆
成交價，但收盤前15分鐘內無成交或最後成交價不合理時，由交易所內部方式
決定——這對深度價外、流動性稀疏的合約（`#70`已知風險第3點）是關鍵：
`close`是單純陳舊掛單價，`settlement_price`在無成交時有交易所主動介入
機制，本模組全面改用`settlement_price`。

**近月合約選取（完全比照`vrp_gate.py`/`#35`既有結論，不重新發明）**：
只用月合約（排除週合約，覆蓋期間不對稱）、`trading_session`==`position`
（日盤）、每個交易日挑到期天數最接近30天且落在[10,45]天區間的合約。
直接`import``vrp_gate.py`的`third_wednesday()`/`MONTHLY_CONTRACT_RE`/
`DTE_BAND`/`TARGET_DTE`，不重複實作同一段邏輯。

**OTM履約價選取規則（本輪事前決定，寫明理由，不得挑好看的規則）**：
- 目標名目距離`TARGET_OTM_PCT=0.05`（5%）——選擇權文獻常用25-delta
  衡量skew，但delta本身需要先知道IV才能算（雞生蛋問題），本模組尚未
  對每個候選履約價都算delta（那需要對整條履約價鏈都做IV反推才能篩選，
  複雜度顯著提高），改用固定名目%距離當簡化替代，比照`vrp_gate.py`
  對ATM選取同樣用「離現貨最近的履約價」這種簡化精神，一致性優先。
- 允許範圍`OTM_BAND=(0.0, 0.15]`——call只接受K>S（真OTM，`moneyness=
  K/S>1.0`）、put只接受K<S（真OTM，`moneyness=K/S<1.0`），且距離現貨
  不超過15%——**這個上限不是隨便挑的，是直接對齊`bs_iv_solver.py`
  round-trip核心驗證已證明可信賴的範圍**（call測試grid上界moneyness=
  1.15、put測試grid下界moneyness=0.85），超出這個範圍的履約價即使
  技術上能反推出數字，也未經過交叉驗證，不予採用。
- 每個交易日在允許範圍內找離`TARGET_OTM_PCT`目標距離最近的一檔（call
  和put分開挑），若該日在允許範圍內完全沒有候選履約價（例如可用履約價
  間距太寬、或當日成交/結算價全為0），該日該側直接跳過，不強湊、不用
  範圍外的履約價替代。

**IV反推與skew計算**：
- `T = dte_calendar / 365.25`（複用`vrp_gate.py`的`dte_calendar`日曆天
  定義）。
- `r`：`cbc_rf_rate_client.rf_rate_for_date()`回傳當月定存利率代理值
  （百分比年化），經`bs_iv_solver.cbc_pct_to_continuous_rate()`轉換成
  Black-Scholes要求的連續複利。
- `call_iv = implied_vol(call_settlement, S, K_call, T, r, 'call')`、
  `put_iv = implied_vol(put_settlement, S, K_put, T, r, 'put')`——任一
  反推拋出`ValueError`（價格超出理論範圍，通常代表過期/雜訊報價）該筆
  觀測整筆丟棄並記錄原因分類（`CLAUDE.md`「失敗要記錄原因分類，禁止
  靜默記None」），不是靜默略過。
- `skew = put_iv - call_iv`（事前綁定定義，`HYPOTHESIS_QUEUE.md` #70
  條目：Skew與後續報酬呈負向IC，比照Xing et al. 2010原始文獻方向）。

**已知簡化的傳遞（非本輪新增，複述自`bs_iv_solver.py`）**：股利率q=0，
本模組計算的IV為q=0假設下的近似值，skew是put_iv−call_iv的差值，若q
造成的偏誤方向相近會部分抵消，仍留待未來若發現顯著影響再處理。

**時序對齊（無未來函數）**：本模組只組裝「訊號本身」的時序（skew在
date當天收盤後即可得），**不涉及任何forward return計算**——那是下一輪
cheap gate的工作，本輪不觸碰任何t+1以後的資料，`is_holdout_consumed()`
本輪開工/收工前皆確認`False`，全程零新增API呼叫（全用`#31`/`#69`留下的
`TaiwanOptionDaily`parquet快取、`cbc_rf_rate_client`既有快取、
`yf_price_client`既有`^TWII`快取）。

2026-09-10由`HYPOTHESIS_QUEUE_PROTOCOL.md`自動排程接續，佇列#70地基
建置(c)(d)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from finmind_client import load_dev
from yf_price_client import fetch_yf_index
from validation.holdout import VAL_END
from vrp_gate import third_wednesday, MONTHLY_CONTRACT_RE, DTE_BAND, TARGET_DTE
from cbc_rf_rate_client import load_risk_free_rate_series, rf_rate_for_date
from bs_iv_solver import implied_vol, cbc_pct_to_continuous_rate

OPTION_ID = "TXO"
OPTION_START = "2015-01-01"
TARGET_OTM_PCT = 0.05  # 目標OTM名目距離（見docstring理由）
OTM_BAND = (0.0, 0.15)  # 對齊bs_iv_solver.py round-trip核心驗證已證明可信賴的範圍


def build_option_frame() -> pd.DataFrame:
    """回傳columns: date, contract_date, expiry, dte_calendar, strike_price,
    call_put, settlement。只含月合約、日盤、settlement_price>0的觀測。
    複製`vrp_gate.py::build_option_frame()`的抓取/過濾邏輯，但保留兩腳
    (call/put)分開的長格式（VRP只需要ATM單一履約價的call+put配對，本
    模組需要在同一天同一合約裡對call/put分別掃整條履約價鏈找OTM）。"""
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
        raise RuntimeError("TaiwanOptionDaily(TXO)逐年抓取後仍全數空資料，(c)(d)無法起跑")
    opt = pd.concat(frames, ignore_index=True)
    opt = opt[opt["trading_session"] == "position"].copy()
    opt = opt[opt["contract_date"].astype(str).str.match(MONTHLY_CONTRACT_RE)].copy()
    opt["date"] = pd.to_datetime(opt["date"])
    opt["settlement"] = pd.to_numeric(opt["settlement_price"], errors="coerce")
    opt["strike_price"] = pd.to_numeric(opt["strike_price"], errors="coerce")
    opt = opt.dropna(subset=["settlement", "strike_price"])
    opt = opt[opt["settlement"] > 0].copy()

    expiry_cache: dict[str, pd.Timestamp] = {}

    def _expiry(cd: str) -> pd.Timestamp:
        if cd not in expiry_cache:
            y, m = int(cd[:4]), int(cd[4:6])
            expiry_cache[cd] = third_wednesday(y, m)
        return expiry_cache[cd]

    opt["expiry"] = opt["contract_date"].astype(str).map(_expiry)
    opt["dte_calendar"] = (opt["expiry"] - opt["date"]).dt.days
    lo, hi = DTE_BAND
    opt = opt[(opt["dte_calendar"] >= lo) & (opt["dte_calendar"] <= hi)].copy()
    return opt[["date", "contract_date", "expiry", "dte_calendar", "strike_price", "call_put", "settlement"]]


def _select_near_month_contract(opt: pd.DataFrame) -> pd.DataFrame:
    """每個交易日挑到期天數最接近TARGET_DTE的合約（可能同一天有多個月
    合約落在DTE_BAND內），完全比照`vrp_gate.py::select_atm_observations()`
    的合約選取那一段。"""
    df = opt.copy()
    df["dte_dist"] = (df["dte_calendar"] - TARGET_DTE).abs()
    idx_contract = df.groupby("date")["dte_dist"].idxmin()
    chosen = df.loc[idx_contract, ["date", "contract_date"]]
    return df.merge(chosen, on=["date", "contract_date"], how="inner")


def _pick_otm_strike(day_side: pd.DataFrame, spot: float, target_moneyness: float) -> pd.Series | None:
    """在單一(date, contract_date, call_put一側)的履約價候選裡，挑離
    target_moneyness*spot最近、且落在OTM_BAND允許範圍內的一檔。回傳
    None代表當天該側無合格候選（不強湊）。"""
    d = day_side.copy()
    d["moneyness"] = d["strike_price"] / spot
    lo, hi = OTM_BAND
    d = d[(d["moneyness"] - 1.0).abs() > lo]  # 排除等於ATM(moneyness==1.0，浮點寬容用>lo而非>0)
    d = d[(d["moneyness"] - 1.0).abs() <= hi]
    if d.empty:
        return None
    d["dist"] = (d["moneyness"] - target_moneyness).abs()
    return d.sort_values("dist").iloc[0]


def build_skew_series() -> pd.DataFrame:
    """組裝逐日OTM put/call配對IV與skew。回傳columns: date, dte_calendar,
    spot, call_strike, call_moneyness, call_settlement, call_iv,
    put_strike, put_moneyness, put_settlement, put_iv, skew。"""
    opt = build_option_frame()
    chosen = _select_near_month_contract(opt)

    taiex = fetch_yf_index(ticker="^TWII", start_date="2010-01-01")
    tw = taiex[["date", "close"]].rename(columns={"close": "spot"}).copy()
    tw["date"] = pd.to_datetime(tw["date"])
    merged = chosen.merge(tw, on="date", how="inner")

    rf_monthly = load_risk_free_rate_series()

    calls = merged[merged["call_put"] == "call"]
    puts = merged[merged["call_put"] == "put"]

    rows = []
    skip_reasons: dict[str, int] = {}

    def _bump(reason: str) -> None:
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    for date, g_call in calls.groupby("date"):
        g_put = puts[puts["date"] == date]
        if g_put.empty:
            _bump("該日無put候選")
            continue
        spot = float(g_call["spot"].iloc[0])
        dte = int(g_call["dte_calendar"].iloc[0])

        call_row = _pick_otm_strike(g_call, spot, 1.0 + TARGET_OTM_PCT)
        put_row = _pick_otm_strike(g_put, spot, 1.0 - TARGET_OTM_PCT)
        if call_row is None:
            _bump("call側無合格OTM候選(超出OTM_BAND或無資料)")
            continue
        if put_row is None:
            _bump("put側無合格OTM候選(超出OTM_BAND或無資料)")
            continue

        try:
            rf_pct = rf_rate_for_date(date, rf_monthly)
        except ValueError:
            _bump("無風險利率序列涵蓋範圍之前，跳過")
            continue
        r = cbc_pct_to_continuous_rate(rf_pct)
        T = dte / 365.25

        try:
            call_iv = implied_vol(float(call_row["settlement"]), spot, float(call_row["strike_price"]), T, r, "call")
        except ValueError as e:
            _bump(f"call IV反推失敗: {e}")
            continue
        try:
            put_iv = implied_vol(float(put_row["settlement"]), spot, float(put_row["strike_price"]), T, r, "put")
        except ValueError as e:
            _bump(f"put IV反推失敗: {e}")
            continue

        rows.append({
            "date": date, "dte_calendar": dte, "spot": spot,
            "call_strike": float(call_row["strike_price"]), "call_moneyness": float(call_row["moneyness"]),
            "call_settlement": float(call_row["settlement"]), "call_iv": call_iv,
            "put_strike": float(put_row["strike_price"]), "put_moneyness": float(put_row["moneyness"]),
            "put_settlement": float(put_row["settlement"]), "put_iv": put_iv,
            "skew": put_iv - call_iv,
        })

    out = pd.DataFrame(rows).sort_values("date").reset_index(drop=True) if rows else pd.DataFrame()
    total_candidate_days = calls["date"].nunique()
    return out, skip_reasons, total_candidate_days


def main() -> dict:
    print("=== #70地基建置(c)(d)：組裝逐日OTM put/call配對IV與skew時序 ===")
    print(f"OTM選取規則: TARGET_OTM_PCT={TARGET_OTM_PCT}, OTM_BAND={OTM_BAND}"
          f"（對齊bs_iv_solver.py round-trip核心驗證範圍）")
    skew_df, skip_reasons, total_candidate_days = build_skew_series()

    print(f"\n候選交易日總數（有call資料的日子）: {total_candidate_days}")
    print(f"成功組出skew的交易日數: {len(skew_df)}")
    print(f"跳過原因統計:")
    for reason, cnt in sorted(skip_reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {reason}: {cnt}")

    if skew_df.empty:
        print("\nFATAL: 無任何觀測成功組出skew，(c)(d)無法交付可用時序")
        return {"n": 0, "ok": False}

    print(f"\n涵蓋日期範圍: {skew_df['date'].min().date()} ~ {skew_df['date'].max().date()}")
    print(f"call_moneyness描述統計: mean={skew_df['call_moneyness'].mean():.4f} "
          f"min={skew_df['call_moneyness'].min():.4f} max={skew_df['call_moneyness'].max():.4f}")
    print(f"put_moneyness描述統計: mean={skew_df['put_moneyness'].mean():.4f} "
          f"min={skew_df['put_moneyness'].min():.4f} max={skew_df['put_moneyness'].max():.4f}")
    print(f"call_iv描述統計: mean={skew_df['call_iv'].mean():.4f} "
          f"min={skew_df['call_iv'].min():.4f} max={skew_df['call_iv'].max():.4f}")
    print(f"put_iv描述統計: mean={skew_df['put_iv'].mean():.4f} "
          f"min={skew_df['put_iv'].min():.4f} max={skew_df['put_iv'].max():.4f}")
    print(f"skew(put_iv-call_iv)描述統計: mean={skew_df['skew'].mean():+.4f} "
          f"median={skew_df['skew'].median():+.4f} std={skew_df['skew'].std():.4f} "
          f"min={skew_df['skew'].min():+.4f} max={skew_df['skew'].max():+.4f}")
    pct_positive_skew = float((skew_df["skew"] > 0).mean())
    print(f"skew為正（put IV高於call IV，符合避險需求集中在下檔的先驗）比例: {pct_positive_skew:.3f}")

    # sanity: moneyness確實落在OTM_BAND允許範圍內、call>1.0、put<1.0（真OTM，非ATM/ITM）
    call_ok = (skew_df["call_moneyness"] > 1.0).all() and (skew_df["call_moneyness"] <= 1.0 + OTM_BAND[1]).all()
    put_ok = (skew_df["put_moneyness"] < 1.0).all() and (skew_df["put_moneyness"] >= 1.0 - OTM_BAND[1]).all()
    print(f"\nsanity: 所有call履約價確實為真OTM且落在驗證範圍內: {call_ok}")
    print(f"sanity: 所有put履約價確實為真OTM且落在驗證範圍內: {put_ok}")

    skew_df.to_csv("data/option_skew_series.csv", index=False)
    print("\n完整逐日skew時序已存 data/option_skew_series.csv")
    print("\n**本輪(c)(d)到此為止，尚未進cheap gate（skew vs後續報酬相關性檢定）"
          "，留給下一輪，不跳關直接判定。**")
    return {"n": len(skew_df), "ok": bool(call_ok and put_ok), "skip_reasons": skip_reasons}


if __name__ == "__main__":
    result = main()
