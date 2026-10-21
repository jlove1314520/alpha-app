"""先.一一四-3c：V1（等權再平衡 2007～2014 時點宇宙）資料備妥＋涵蓋率報告。可斷點續跑，DevQueue 夜間執行。

步驟：
1. 官方上市／上櫃日期：TWSE openapi `t187ap03_L`、TPEx `mopsfin_t187ap03_O` 各 1 次（存 research/data/raw/official_basic_*_20261018.json，存過不重抓；
   共用 data/rate_limit_state.json 來源名 twse_openapi／tpex_openapi，同源間隔 ≥3 秒，402/403/428/429 即停）。
2. 母體候選＝上市／上櫃日期 ≤ 2007-01-02 的 4 碼普通股 ∪ FinMind TaiwanStockDelisting 下市日 2007-01-03～2014-12-31 的 4 碼普通股；另加 0050（第 8 關基準）。
3. 每檔 `finmind_client.load_dev("TaiwanStockPrice"／"TaiwanStockDividend", 代號, "2006-01-01")`——有本機快取就不發請求（＝斷點續跑），
   頻率上限由 finmind_client 共用狀態控管；遇到額度用盡／封鎖就乾淨停下、寫進度，下次從頭掃（已抓的會直接命中快取）。
4. 全部抓完後算涵蓋率：母體＝2007-01-02 當天有價格列的候選；涵蓋＝從 2007-01-02 到 min(下市日, 2014-12-31) 有價格、
   相鄰價格列之間缺口 ≤ 10 個交易日。輸出每年在市檔數、母體涵蓋率、下市股涵蓋率到 research/data/var1018_v1_prep_status.json，
   **兩個涵蓋率都 ≥95% 才標 ready_to_register＝true**（先.一一四-3c：不到就停下回報）。
用法：python research/var1018_v1_prep.py [--max-fetch N]（N＝本次最多發幾檔新請求，預設不限）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd
import requests

import finmind_client as F

D = Path(__file__).parent / "data"
RAW = D / "raw"
STATUS = D / "var1018_v1_prep_status.json"
T0, END = pd.Timestamp("2007-01-02"), pd.Timestamp("2014-12-31")
TZ = timezone(timedelta(hours=8))
OFFICIAL = {"L": ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "公司代號", "上市日期", "成立日期"),
            "O": ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "SecuritiesCompanyCode", "DateOfListing", "DateOfIncorporation")}
UA = {"User-Agent": "AlphaApp-ResearchPrep contact@alpha-app-project.example"}
MAX_GAP_TD = 10


def _ymd(v) -> pd.Timestamp | None:
    x = re.sub(r"\D", "", str(v or ""))
    if len(x) != 8:
        return None
    try:
        return pd.Timestamp(f"{x[:4]}-{x[4:6]}-{x[6:]}")
    except ValueError:
        return None


def official_listing_dates() -> dict[str, tuple]:
    """代號 → (上市／上櫃日, 成立日)。"""
    out = {}
    for k, (url, cf, lf, inc) in OFFICIAL.items():
        cache = RAW / f"official_basic_{k}_20261018.json"
        if not cache.exists():
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code in (402, 403, 428, 429):
                raise RuntimeError(f"{url} 回 {r.status_code}，停下（不重試）")
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list):
                raise RuntimeError(f"{url} 回應不是 JSON 陣列")
            cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            time.sleep(3)
        rows = json.loads(cache.read_text(encoding="utf-8"))
        for row in rows:
            code = str(row.get(cf) or "").strip()
            if code:
                out[code] = (_ymd(row.get(lf)), _ymd(row.get(inc)))
    return out


def candidates() -> tuple[list[str], set[str]]:
    """上市／上櫃日 ≤ T0 的普通股＋上市日 > T0 但成立日 ≤ T0 的普通股（可能當時在另一個板，例如上櫃轉上市；
    是否真的在 t0 母體由 coverage() 看 2007-01-02 有沒有價格決定）＋期間下市股＋0050。"""
    lst = official_listing_dates()
    alive = {c for c, (lt, it) in lst.items() if re.fullmatch(r"[1-9]\d{3}", c)
             and ((lt is not None and lt <= T0) or (it is not None and it <= T0))}
    dl = pd.read_parquet(RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    dead = set(dl[(dl["date"] > T0) & (dl["date"] <= END) & dl["stock_id"].str.fullmatch(r"[1-9]\d{3}")]["stock_id"])
    return sorted(alive | dead | {"0050"}), dead


FETCH_START, FETCH_END = "2006-01-01", "2014-12-31"  # 只抓需要的段（load_dev 的快取檔名＝dataset__代號__起__迄）


def cached(dataset: str, code: str) -> bool:
    return F._cache_path(dataset, code, FETCH_START, FETCH_END).exists()


def in_t0(code: str) -> bool:
    if not cached("TaiwanStockPrice", code):
        return False
    d = F.load_dev("TaiwanStockPrice", code, FETCH_START, FETCH_END)
    if d.empty:
        return False
    t = pd.to_datetime(d["date"])
    return bool(((t >= T0 - pd.Timedelta(days=10)) & (t <= T0 + pd.Timedelta(days=10))).any())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-fetch", type=int, default=None)
    a = ap.parse_args(argv)
    st = {"started_at": datetime.now(TZ).isoformat(timespec="seconds")}
    try:
        cands, dead = candidates()
    except Exception as e:  # noqa: BLE001
        st["stopped"] = f"官方上市日期取得失敗：{type(e).__name__}: {e}"
        STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        print(st["stopped"])
        return 0
    fetched_new, stopped = 0, None
    for i, c in enumerate(cands):
        for ds in ("TaiwanStockPrice", "TaiwanStockDividend"):
            if ds == "TaiwanStockDividend" and c != "0050" and not in_t0(c):
                continue  # 不在 t0 母體就不需要股利
            was = cached(ds, c)
            if not was and a.max_fetch is not None and fetched_new >= a.max_fetch:
                stopped = f"達本次上限 --max-fetch {a.max_fetch}"
                break
            try:
                F.load_dev(ds, c, FETCH_START, FETCH_END)
            except Exception as e:  # noqa: BLE001 —— 額度／封鎖／網路：乾淨停下，下次續跑
                stopped = f"{c} {ds}：{type(e).__name__}: {str(e)[:160]}"
                break
            fetched_new += (not was)
        if stopped:
            break
        if i % 100 == 0:
            print(f"  進度 {i + 1}/{len(cands)}，本次新抓 {fetched_new}")
    st.update({"n_candidates": len(cands), "n_delisted_in_period": len(dead), "fetched_new_this_run": fetched_new, "stopped": stopped})
    if not stopped:
        st.update(coverage(cands, dead))
    st["finished_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    st["n_price_cached"] = sum(cached("TaiwanStockPrice", c) for c in cands)
    STATUS.write_text(json.dumps(st, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    try:
        update_shortlist(st)
    except Exception as e:  # noqa: BLE001 —— 進度回報失敗只警告（十二節）
        print(f"[警告] shortlist §6 進度更新失敗：{type(e).__name__}: {e}")
    print(json.dumps({k: v for k, v in st.items() if k != "per_year_in_market"}, ensure_ascii=False, default=str))
    return 0


SHORTLIST = Path(__file__).parent / "VARIANT_SHORTLIST_2026-10-18.md"


def update_shortlist(st: dict) -> None:
    """先.一一五-3：每批補完更新 shortlist §6 的 V1 那一列（已補檔數／候選數；補完後加每年在市檔數、母體與下市股涵蓋率）。"""
    s = SHORTLIST.read_text(encoding="utf-8")
    lines = s.split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("| V1 | 2007～2014 台股價格"))
    msg = (f"V1 時點宇宙補資料（先.一一四-3c／先.一一五-3，{st['finished_at'][:16].replace('T', ' ')} 更新）：已補價格 {st.get('n_price_cached')}／{st.get('n_candidates')} 檔候選；"
           + (f"本批停在：{st['stopped']}" if st.get("stopped") else
              f"**補完**：t0 母體 {st.get('n_universe_t0')} 檔、母體涵蓋率 {st.get('universe_coverage'):.1%}、下市股涵蓋率 {st.get('delisted_coverage'):.1%}"
              f"（期間下市 {st.get('n_delisted_period_total')} 檔中在 t0 母體 {st.get('n_delisted_in_universe')} 檔）；每年在市檔數 {st.get('per_year_in_market')}；"
              f"{'≥95%，可登記單發' if st.get('ready_to_register') else '未達 95%，停下回報、不登記'}"))
    lines[i] = f"| V1 | 2007～2014 台股價格（時點宇宙，FinMind 補 2006 起） | {msg} |"
    SHORTLIST.write_text("\n".join(lines), encoding="utf-8")


def coverage(cands: list[str], dead: set[str]) -> dict:
    dl = pd.read_parquet(RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    universe, covered, per_year = [], [], {y: 0 for y in range(2007, 2015)}
    for c in cands:
        if c == "0050":
            continue
        d = F.load_dev("TaiwanStockPrice", c, FETCH_START, FETCH_END)
        if d.empty:
            continue
        t = pd.to_datetime(d["date"])
        t = t[(t >= T0 - pd.Timedelta(days=10)) & (t <= END)].sort_values()
        if t.empty or t.iloc[0] > T0 + pd.Timedelta(days=10):
            continue  # 2007-01-02 前後沒有價格＝不在 t0 母體
        universe.append(c)
        end = min(ddate.get(c, END), END)
        tt = t[t <= end]
        for y in per_year:
            per_year[y] += int((tt.dt.year == y).any())
        bd = pd.bdate_range(tt.iloc[0], tt.iloc[-1])
        gaps = pd.Series(range(len(bd)), index=bd).reindex(tt.values).diff().max() if len(tt) > 1 else 0
        ok = (end - tt.iloc[-1]).days <= 20 and (gaps is None or pd.isna(gaps) or gaps <= MAX_GAP_TD)
        covered.append(ok)
    n = len(universe)
    dead_u = [c for c in universe if c in dead]
    dead_cov = [ok for c, ok in zip(universe, covered) if c in dead]
    uni_rate = sum(covered) / n if n else 0.0
    dead_rate = (sum(dead_cov) / len(dead_cov)) if dead_cov else 0.0
    return {"n_universe_t0": n, "universe_coverage": round(uni_rate, 4), "n_delisted_in_universe": len(dead_u),
            "n_delisted_period_total": len(dead), "delisted_coverage": round(dead_rate, 4),
            "delisted_in_universe_share_of_period_delistings": round(len(dead_u) / len(dead), 4) if dead else None,
            "per_year_in_market": per_year,
            "ready_to_register": bool(uni_rate >= 0.95 and dead_rate >= 0.95),
            "rule": "母體涵蓋率與下市股涵蓋率都 ≥95% 才登記單發（先.一一四-3c）；不到就停下回報"}


if __name__ == "__main__":
    raise SystemExit(main())
