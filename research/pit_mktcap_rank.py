# -*- coding: utf-8 -*-
"""先.八十三-2a-1：台股上市普通股「時點正確」的市值排名（含已下市股）。

來源：先.八十三-2a 診斷（research/AUTOPSY_ACTIONS.md「A 類先修診斷」）——core_tilt #281／#283
用 300 檔抽樣宇宙＋當下 PER 快取估市值，宇宙錯誤；修法①就是這支：

    市值(d) ＝ 股數(d) × 未還原收盤(d)
    股數(d) ＝ 最近一期「法定公告日 ≤ d」的資產負債表 OrdinaryShare（普通股股本，元）÷ 面額

- 法定公告日：沿用 `pit.statutory_quarterly_pit_date()`（Q1～Q3 期末＋45 天、Q4 次年 3/31）。
  只呼叫、不修改 pit.py（CLAUDE.md 十三節單一寫入者檔）。
- 面額：預設 10 元；`TaiwanStockParValueChange`（全市場檔）有變更面額者，依
  「變更後參考價÷變更前收盤」換算新面額（例：長科 6548 2019-09-09 312→31.2 ⇒ 面額 1 元）。
- 宇宙：TaiwanStockInfo 最新快取（含已下市股的殘留列）type＝twse 的普通股
  （`universe.classify_security` 同一套判斷，排除 ETF／特別股／存託憑證等），
  且日期 ≥ TWSE 上市日（`twse_listing_dates.json` 有記錄者；櫃轉市股票的上市日就是轉上市日，
  之前的上櫃期間不算進上市排名）。已下市股：價格列自然在下市後消失，不另外截斷。
- 價格：TaiwanStockPrice 未還原收盤；當天沒成交者往前找最多 5 個交易日。

**只讀本機 FinMind 快取**（同一代號多個快取檔取聯集），**自己強制 VAL_END（2024-12-31）上限**——
直接讀 parquet 不經過 `load_dev()`，所以上限要在這裡自己做，否則會讀到 holdout。
查不到快取的代號**不猜**：列進 `coverage_report()`，由 `--backfill` 照 FinMind 每小時上限補抓。

已知限制（照實寫，驗證腳本會量化）：
1. 0050 依「流通股數」加權（且 2023 起有單檔權重上限規則），這裡用總股數 → 重建
   不可能完全一致，TE 有下限。
2. 季間增減資（現增、可轉債轉換、庫藏股註銷）要到下一期法定公告日才反映，股數會落後。
3. 資產負債表快取有空檔的代號（FinMind 回空）沒有股數，排不進名次（coverage_report 列出）。

不登記試驗、不計 N（這是宇宙建構工具，不是策略）。

用法：
    python research/pit_mktcap_rank.py --coverage            # 覆蓋率報告（0 次請求）
    python research/pit_mktcap_rank.py --top 2015-06-30      # 某日前 50 大
    python research/pit_mktcap_rank.py --backfill 30         # 補抓最多 30 檔缺的資產負債表（照 FinMind 限速）
    python research/pit_mktcap_rank.py --backfill-events 2880 2887   # 補抓含息還原用的事件快取
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pit import statutory_quarterly_pit_date  # noqa: E402  只讀呼叫，不改 pit.py
from universe import classify_security  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

RAW = HERE / "data" / "raw"
INFO_LATEST = RAW / "TaiwanStockInfo__ALL__2000-01-01__latest.parquet"
TWSE_LISTING = HERE / "data" / "twse_listing_dates.json"
PRICE_LOOKBACK_DAYS = 5


@lru_cache(maxsize=1)
def _raw_index() -> dict[tuple[str, str], list[str]]:
    """raw/ 目錄有近 4 萬個快取檔：每檔股票各 glob 一次要 0.15 秒 × 上千檔 × 2 種資料，
    是 2026-10-14 第一次執行逾時的主因 → 只列一次目錄、建 (dataset, sid) → 檔名 索引。"""
    idx: dict[tuple[str, str], list[str]] = {}
    for name in os.listdir(RAW):
        if not name.endswith(".parquet"):
            continue
        parts = name.split("__")
        if len(parts) >= 3:
            idx.setdefault((parts[0], parts[1]), []).append(str(RAW / name))
    return idx


def _union_cache(dataset: str, sid: str) -> pd.DataFrame:
    files = _raw_index().get((dataset, sid), [])
    frames = []
    for f in files:
        try:
            df = pd.read_parquet(f)
        except Exception as e:  # noqa: BLE001 — 單一壞檔不拖垮整個排名，照實警告
            print(f"  [快取讀取失敗，略過] {os.path.basename(f)}: {type(e).__name__}", flush=True)
            continue
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df[df["date"].astype(str) <= VAL_END]          # holdout 上限：自己做
    return df


@lru_cache(maxsize=1)
def twse_common_universe() -> pd.DataFrame:
    """回傳 stock_id, stock_name, listing_date（TWSE 上市日，查不到為 None）。"""
    info = pd.read_parquet(INFO_LATEST)
    twse_ids = set(info.loc[info["type"] == "twse", "stock_id"])
    info = info[info["stock_id"].isin(twse_ids)].sort_values("date").drop_duplicates("stock_id", keep="last")
    keep = []
    for r in info.itertuples():
        try:
            st = classify_security(r.stock_id, r.stock_name, r.industry_category)
        except Exception as e:  # noqa: BLE001
            print(f"  [分類失敗，保守排除] {r.stock_id}: {type(e).__name__}", flush=True)
            continue
        # 上市普通股代號一律 4 碼數字；TaiwanStockInfo 的 type＝twse 還混有指數列（TAIEX、Cement…）、
        # 特別股（2887E）、ETN（02001L），classify_security 會漏判 → 這裡再加一道格式限制
        if st == "普通股" and len(r.stock_id) == 4 and r.stock_id.isdigit():
            keep.append((r.stock_id, r.stock_name))
    ld = json.loads(TWSE_LISTING.read_text(encoding="utf-8")).get("listing_dates", {})
    rows = [(s, n, (f"{ld[s][:4]}-{ld[s][4:6]}-{ld[s][6:]}" if s in ld else None)) for s, n in keep]
    df = pd.DataFrame(rows, columns=["stock_id", "stock_name", "listing_date"])
    # 查不到上市日的列，pandas 會把 None 轉成 NaN（float、且為真值）→ 與字串比較會 TypeError；轉回空字串
    df["listing_date"] = df["listing_date"].fillna("").astype(str)
    return df


@lru_cache(maxsize=1)
def _par_events() -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    frames = []
    for f in _raw_index().get(("TaiwanStockParValueChange", "ALL"), []):
        try:
            frames.append(pd.read_parquet(f))
        except Exception as e:  # noqa: BLE001
            print(f"  [面額變更快取讀取失敗] {os.path.basename(f)}: {type(e).__name__}", flush=True)
    if not frames:
        return out
    pv = pd.concat(frames).drop_duplicates(["stock_id", "date"])
    pv = pv[pv["date"].astype(str) <= VAL_END]
    for r in pv.sort_values("date").itertuples():
        if r.before_close and r.after_ref_close:
            out.setdefault(r.stock_id, []).append((str(r.date)[:10], float(r.after_ref_close) / float(r.before_close)))
    return out


def par_value(sid: str, d: str) -> float:
    p = 10.0
    for dt, ratio in _par_events().get(sid, []):
        if dt <= d:
            p *= ratio
    return p


@lru_cache(maxsize=4096)
def shares_table(sid: str) -> pd.DataFrame:
    """columns: pit_date(str), period(str), capital(元)。依 pit_date 排序。"""
    bs = _union_cache("TaiwanStockBalanceSheet", sid)
    if bs.empty or "type" not in bs.columns:
        return pd.DataFrame(columns=["pit_date", "period", "capital"])
    os_ = bs[bs["type"] == "OrdinaryShare"].drop_duplicates("date", keep="last")
    os_ = os_[pd.to_numeric(os_["value"], errors="coerce") > 0]
    out = pd.DataFrame({
        "period": os_["date"].astype(str).str[:10],
        "pit_date": [statutory_quarterly_pit_date(x).strftime("%Y-%m-%d") for x in os_["date"]],
        "capital": pd.to_numeric(os_["value"]).astype(float),
    })
    return out.sort_values("pit_date").reset_index(drop=True)


@lru_cache(maxsize=4096)
def close_series(sid: str) -> pd.Series:
    px = _union_cache("TaiwanStockPrice", sid)
    if px.empty:
        return pd.Series(dtype=float)
    px = px[pd.to_numeric(px["close"], errors="coerce") > 0]
    px = px.assign(date=px["date"].astype(str).str[:10]).drop_duplicates("date", keep="last")
    s = px.set_index("date")["close"].astype(float)
    return s.sort_index()


def shares_on(sid: str, d: str) -> float | None:
    t = shares_table(sid)
    t = t[t["pit_date"] <= d]
    if t.empty:
        return None
    return float(t["capital"].iloc[-1]) / par_value(sid, d)


def close_on(sid: str, d: str) -> float | None:
    s = close_series(sid)
    if s.empty:
        return None
    s = s[s.index <= d]
    if s.empty:
        return None
    last = s.index[-1]
    if (pd.Timestamp(d) - pd.Timestamp(last)).days > PRICE_LOOKBACK_DAYS + 4:   # 5 個交易日≈9 個日曆天
        return None
    return float(s.iloc[-1])


def mktcap_rank(d: str) -> pd.DataFrame:
    """d 當天（含）可得資訊下的上市普通股市值排名。d 不得晚於 VAL_END。"""
    if d > VAL_END:
        raise ValueError(f"{d} 晚於 VAL_END {VAL_END}：不得用這支碰 holdout")
    uni = twse_common_universe()
    rows = []
    for r in uni.itertuples():
        if r.listing_date and r.listing_date > d:
            continue
        c = close_on(r.stock_id, d)
        if c is None:
            continue
        sh = shares_on(r.stock_id, d)
        if sh is None:
            continue
        rows.append((r.stock_id, r.stock_name, sh, c, sh * c))
    df = pd.DataFrame(rows, columns=["stock_id", "stock_name", "shares", "close", "mktcap"])
    df = df.sort_values("mktcap", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


def mktcap_panel(dates: list[str]) -> pd.DataFrame:
    """多個日期一次算（驗證腳本用）：每檔只讀一次快取，用 searchsorted 查「d 以前最近一筆」。
    結果與逐日呼叫 mktcap_rank() 相同（同一套股數／價格／上市日規則），只是快。
    回傳長表：date, stock_id, stock_name, shares, close, mktcap, rank。"""
    import numpy as np
    if any(d > VAL_END for d in dates):
        raise ValueError(f"日期晚於 VAL_END {VAL_END}：不得用這支碰 holdout")
    dates = sorted(dates)
    dts = np.array(dates)
    rows = []
    for r in twse_common_universe().itertuples():
        cs = close_series(r.stock_id)
        st = shares_table(r.stock_id)
        if cs.empty or st.empty:
            continue
        cidx = cs.index.to_numpy().astype(str)
        cval = cs.to_numpy()
        sp = st["pit_date"].to_numpy().astype(str)
        sc = st["capital"].to_numpy()
        ci = np.searchsorted(cidx, dts, side="right") - 1
        si = np.searchsorted(sp, dts, side="right") - 1
        for k, d in enumerate(dates):
            if (r.listing_date and r.listing_date > d) or ci[k] < 0 or si[k] < 0:
                continue
            if (pd.Timestamp(d) - pd.Timestamp(str(cidx[ci[k]]))).days > PRICE_LOOKBACK_DAYS + 4:
                continue
            sh = float(sc[si[k]]) / par_value(r.stock_id, d)
            c = float(cval[ci[k]])
            rows.append((d, r.stock_id, r.stock_name, sh, c, sh * c))
    df = pd.DataFrame(rows, columns=["date", "stock_id", "stock_name", "shares", "close", "mktcap"])
    df = df.sort_values(["date", "mktcap"], ascending=[True, False]).reset_index(drop=True)
    df["rank"] = df.groupby("date").cumcount() + 1
    return df


@lru_cache(maxsize=4096)
def total_return_index(sid: str) -> pd.Series:
    """還原（含息）收盤序列，**只讀本機快取**：事件（股利／分割／減資／面額變更）用
    adjust._combine_adjustment_events 同一套因子算法（只呼叫、不改 adjust.py），
    但事件來源是這裡的聯集快取，不經 load_dev（避免為了驗證去打網路）。
    該代號沒有任何事件快取時回原始收盤，並在 attrs 標 no_event_cache=True（驗證腳本會計數揭露）。"""
    from adjust import _combine_adjustment_events
    px = _union_cache("TaiwanStockPrice", sid)
    if px.empty:
        return pd.Series(dtype=float)
    px = px[pd.to_numeric(px["close"], errors="coerce") > 0]
    px = px.assign(date=px["date"].astype(str).str[:10]).drop_duplicates("date", keep="last").sort_values("date")
    px = px.reset_index(drop=True)
    div = _union_cache("TaiwanStockDividend", sid)
    spl = _union_cache("TaiwanStockSplitPrice", sid)
    cr = _union_cache("TaiwanStockCapitalReductionReferencePrice", sid)
    pv_all = _union_cache("TaiwanStockParValueChange", "ALL")
    pv = pv_all[pv_all["stock_id"] == sid].drop_duplicates("date") if not pv_all.empty else pd.DataFrame()
    no_cache = div.empty and spl.empty and cr.empty
    for name, df in (("div", div), ("spl", spl), ("cr", cr)):
        if not df.empty:
            key = [c for c in ("date", "stock_id") if c in df.columns]
            df.drop_duplicates(key, keep="last", inplace=True)
    try:
        ev = _combine_adjustment_events(div, spl, cr, pv, dict(zip(px["date"], px["close"])), px["date"].tolist())
    except Exception as e:  # noqa: BLE001 — 單檔事件解析失敗只影響該檔，照實警告、退回原始價
        print(f"  [還原因子失敗，用原始價] {sid}: {type(e).__name__}: {str(e)[:120]}", flush=True)
        ev = pd.DataFrame()
        no_cache = True
    fac = pd.Series(1.0, index=px.index)
    if not ev.empty:
        for e in ev.sort_values("ex_date", ascending=False).itertuples():
            m = px["date"] < str(e.ex_date)[:10]
            fac.loc[m] = fac.loc[m] * float(e.factor)
    out = pd.Series(px["close"].astype(float).to_numpy() * fac.to_numpy(), index=px["date"].to_numpy())
    out.attrs["no_event_cache"] = bool(no_cache)
    return out


def top_n(d: str, n: int = 50) -> pd.DataFrame:
    return mktcap_rank(d).head(n)


def coverage_report(d: str | None = None) -> dict:
    """有價格但沒有股數（資產負債表快取缺／空）的上市普通股清單。d 給了就只看 d 當天有成交者。"""
    uni = twse_common_universe()
    no_price, no_bs, ok = [], [], 0
    for r in uni.itertuples():
        s = close_series(r.stock_id)
        if d is not None:
            if r.listing_date and r.listing_date > d:
                continue
            if close_on(r.stock_id, d) is None:
                continue
        elif s.empty:
            no_price.append(r.stock_id)
            continue
        if shares_table(r.stock_id).empty:
            no_bs.append(r.stock_id)
        else:
            ok += 1
    return {"as_of": d, "universe_twse_common": len(uni), "ok": ok,
            "no_price_cache": sorted(no_price), "no_balance_sheet": sorted(no_bs)}


def backfill(max_n: int) -> None:
    """補抓缺資產負債表的代號：走 finmind_client.load_dev（共用限速與 402/429 封鎖），
    額度/封鎖類錯誤一出現就停（不重試、不換來源）。"""
    from finmind_client import load_dev
    allmiss = coverage_report()["no_balance_sheet"]
    # 已有快取檔但內容空（FinMind 回空、多為早年下市股）的不重抓：同一參數重打只會再拿到空的，白耗額度
    miss = [s for s in allmiss if ("TaiwanStockBalanceSheet", s) not in _raw_index()]
    print(f"缺資產負債表 {len(allmiss)} 檔（其中 {len(allmiss) - len(miss)} 檔已抓過但回空、不重抓），"
          f"本次最多補 {max_n} 檔", flush=True)
    for i, sid in enumerate(miss[:max_n], 1):
        try:
            df = load_dev("TaiwanStockBalanceSheet", sid, "2003-01-01")
            print(f"  {i:>3} {sid}: {len(df)} 列", flush=True)
        except RuntimeError as e:
            print(f"  [停止] {sid}: {str(e)[:160]}", flush=True)
            break


EVENT_DATASETS = ("TaiwanStockDividend", "TaiwanStockSplitPrice", "TaiwanStockCapitalReductionReferencePrice")


def backfill_events(ids: list[str]) -> None:
    """補抓除權息／分割／減資事件快取（含息還原用）。只補「三種都沒有快取檔」的代號，
    走 load_dev（共用限速、402/429 即停、不重試）。"""
    from finmind_client import load_dev
    # 判斷「VAL_END 以前有沒有事件列」，不是「有沒有檔案」：不少代號只有 2025-01-01__latest 快取（App 抓的），
    # 對 2024 年以前等於沒有（2026-10-14 實測 15／18 檔是這種）
    todo = [s for s in ids if all(_union_cache(ds, s).empty for ds in EVENT_DATASETS)]
    print(f"事件快取缺 {len(todo)} 檔（每檔 {len(EVENT_DATASETS)} 個請求）", flush=True)
    for sid in todo:
        for ds in EVENT_DATASETS:
            try:
                df = load_dev(ds, sid, "2003-01-01")
                print(f"  {sid} {ds}: {len(df)} 列", flush=True)
            except RuntimeError as e:
                print(f"  [停止] {sid} {ds}: {str(e)[:160]}", flush=True)
                return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--top")
    ap.add_argument("--backfill", type=int)
    ap.add_argument("--backfill-events", nargs="+", metavar="SID",
                    help="補抓這些代號的事件快取（驗證腳本 holdings_without_event_cache 清單）")
    a = ap.parse_args()
    if a.coverage:
        rep = coverage_report()
        print(json.dumps({k: (v if not isinstance(v, list) else {"n": len(v), "ids": v[:40]})
                          for k, v in rep.items()}, ensure_ascii=False, indent=1))
    if a.top:
        print(top_n(a.top).to_string())
    if a.backfill:
        backfill(a.backfill)
    if a.backfill_events:
        backfill_events(a.backfill_events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
