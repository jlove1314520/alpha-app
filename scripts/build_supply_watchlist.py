"""先.八-三：供給吃緊觀察清單資料產生器（描述性資料，非訊號、非回測、非建議）。

輸出 data/supply_watchlist.json：最新一季「法定期限已過」之財報的 I1-I4 原始 YoY 變化值，
以及該股在產業桶內的百分位（同 docs/PREREG_supply_tightness_v2_FORWARD.md §4 定義：
產業內成員 <8 檔併入「其他」桶；I1-I4 至少 3 個可得才進桶計分）。

硬規則：
- 只輸出描述性數字：無綜合分數、無排名、無價格、無績效。
- 只用已公告資料：基準季 = 法定期限早於今日的最近一季（pit.statutory_quarterly_pit_date，與紙.二同一函式）；
  某檔尚未入庫該季財報者標「未入庫」，不補猜、不用估計值。
- 唯讀借用紙.二的 quarter_table_from_frames（I1-I4 定義單一來源）；不 import 任何寫入紙.二紀錄的路徑，
  不讀寫 research/data/paper_supply_v2_*；與紙.二共用同一份 FinMind 逐檔財報快取（research/data/raw，同路徑同起日），只讀寫快取、不碰紙.二紀錄。
- FinMind 抓取每次自限額度（--budget，預設 500 次），遇封鎖／額度錯誤立即停止抓取、只用既有快取產出（降級不中斷）。
- 不印出任何金鑰。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
sys.path.insert(0, str(RESEARCH))
import finmind_client as fc  # noqa: E402

TZ = timezone(timedelta(hours=8))
OUT_PATH = ROOT / "data" / "supply_watchlist.json"
REAL_RAW = fc.DATA_DIR
DEFAULT_CACHE = REAL_RAW
INFO_NAME = "TaiwanStockInfo__ALL__2000-01-01__latest.parquet"
STMT_RETRY_DAYS = 7
MIN_BUCKET = 8
MIN_IND = 3
COLS = ["I1", "I2", "I3", "I4"]
DISCLAIMER = "描述性資料，未經回測驗證；紙上追蹤中，滿8季前不得作為真錢依據"


def now_tw() -> datetime:
    return datetime.now(TZ)


def setup_cache(cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    fc.DATA_DIR = cache_dir
    dst = cache_dir / INFO_NAME
    src = REAL_RAW / INFO_NAME
    if src != dst and src.exists() and (not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime):
        shutil.copy2(src, dst)
    if not dst.exists():
        raise RuntimeError("找不到 TaiwanStockInfo 快取，無法建立名冊")


def universe(cache_dir: Path) -> pd.DataFrame:
    import precheck_supply_tightness as pt

    info = pd.read_parquet(cache_dir / INFO_NAME).drop_duplicates("stock_id")
    info["stock_id"] = info["stock_id"].astype(str)
    info = info[info["stock_id"].str.fullmatch(r"\d{4}") & info["type"].isin(["twse", "tpex"])]
    ind = info["industry_category"].astype(str)
    info = info[~ind.isin(pt.FINANCIAL) & ~ind.str.contains(pt.NON_STOCK)]
    return pd.DataFrame({"code": info["stock_id"].values, "name": info["stock_name"].astype(str).values,
                         "industry": info["industry_category"].astype(str).values}).sort_values("code").reset_index(drop=True)


def stmt_paths(code: str, ds_map, start: str):
    return {k: fc._cache_path(ds, code, start, None) for k, ds in ds_map}


def has_period(path: Path, period: pd.Period) -> bool:
    try:
        df = pd.read_parquet(path)
    except Exception:  # noqa: BLE001  壞檔視為未入庫，下輪會重抓
        return False
    if df is None or df.empty or "date" not in df.columns:
        return False
    return bool((pd.PeriodIndex(pd.to_datetime(df["date"]), freq="Q") == period).any())


def plan_fetch(codes, ds_map, start, period, now_ts):
    """回傳 [(優先序, code, ds)]：先補沒有快取者，其次基準季尚未入庫且上次抓取已逾 STMT_RETRY_DAYS 天者。"""
    missing, stale = [], []
    for c in codes:
        for k, ds in ds_map:
            p = fc._cache_path(ds, c, start, None)
            if not p.exists():
                missing.append((c, ds))
            elif not has_period(p, period) and (now_ts - p.stat().st_mtime) > STMT_RETRY_DAYS * 86400:
                stale.append((c, ds))
    return missing, stale


def fetch_phase(codes, ds_map, start, period, budget, throttle):
    st = {"calls": 0, "ok": 0, "fail": 0, "stopped": None, "todo_missing": 0, "todo_stale": 0}
    missing, stale = plan_fetch(codes, ds_map, start, period, time.time())
    st["todo_missing"], st["todo_stale"] = len(missing), len(stale)
    for c, ds in missing + stale:
        if st["calls"] >= budget:
            st["stopped"] = "budget"
            break
        st["calls"] += 1
        try:
            fc._fetch(ds, c, start, None, force_refresh=True)
            st["ok"] += 1
            time.sleep(throttle)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            st["fail"] += 1
            if "封鎖" in msg or "冷卻" in msg or "402" in msg or "403" in msg or "428" in msg:
                st["stopped"] = "blocked"
                print(f"[降級] FinMind 封鎖／額度錯誤，停止本輪抓取：{msg[:120]}", flush=True)
                break
            if "HTTP 400" in msg:
                continue
            print(f"[警告] {ds} {c} 抓取失敗：{msg[:100]}", flush=True)
            if st["fail"] >= 25:
                st["stopped"] = "too_many_failures"
                break
    return st


def compute(uni: pd.DataFrame, ds_map, start, period, pv2):
    rows, n_cache, n_period = [], 0, 0
    for c, name, industry in zip(uni["code"], uni["name"], uni["industry"]):
        fr = {}
        for k, ds in ds_map:
            p = fc._cache_path(ds, c, start, None)
            try:
                fr[k] = pd.read_parquet(p) if p.exists() else None
            except Exception:  # noqa: BLE001
                fr[k] = None
        got = all(fr[k] is not None and len(fr[k]) for k, _ in ds_map)
        n_cache += int(any(fr[k] is not None for k, _ in ds_map))
        vals = {k: np.nan for k in COLS}
        stmt_in = False
        if got:
            tab = pv2.quarter_table_from_frames(fr["fs"], fr["bs"], fr["cf"])
            if tab is not None and period in tab.index:
                stmt_in = True
                for k in COLS:
                    vals[k] = float(tab.at[period, k])
        n_period += int(stmt_in)
        rows.append({"code": c, "name": name, "industry": industry, "in": stmt_in, **vals})
    df = pd.DataFrame(rows)
    X = df[COLS].astype(float)
    df["n_ind"] = np.isfinite(X.values).sum(1)
    df["scored"] = df["in"] & (df["n_ind"] >= MIN_IND)
    sc = df[df["scored"]]
    cnt = sc["industry"].value_counts()
    small = set(cnt[cnt < MIN_BUCKET].index)
    df["bucket"] = np.where(df["industry"].isin(small) | (df["industry"] == "其他"), "其他", df["industry"])
    for k in COLS:
        df["p" + k[1:]] = np.nan
    for b, g in df[df["scored"]].groupby("bucket"):
        for k in COLS:
            v = g[k].astype(float)
            fin = v[np.isfinite(v)]
            if len(fin) >= 2:
                df.loc[fin.index, "p" + k[1:]] = (fin.rank(method="average") / len(fin)).round(4)
    bsize = df[df["scored"]].groupby("bucket").size().to_dict()
    n_bucket_scorable = {b: int(n) for b, n in bsize.items()}
    return df, n_cache, n_period, n_bucket_scorable


def r6(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 6)


def build_payload(df, uni, period, D, n_cache, n_period, n_bucket, fstat, as_of):
    out_rows = []
    for _, r in df[df["in"]].iterrows():
        out_rows.append({
            "c": r["code"], "n": r["name"], "i": r["industry"], "b": r["bucket"],
            "in": bool(r["in"]), "ni": int(r["n_ind"]), "sc": bool(r["scored"]),
            "v": [r6(r[k]) for k in COLS],
            "p": [None if not np.isfinite(r["p" + k[1:]]) else float(r["p" + k[1:]]) for k in COLS],
        })
    return {
        "meta": {
            "title": "供給吃緊觀察清單", "disclaimer": DISCLAIMER,
            "period": str(period), "period_deadline": str(D.date()),
            "as_of": as_of,
            "n_universe": int(len(uni)), "n_cache": int(n_cache),
            "n_with_period": int(n_period), "n_scored": int(df["scored"].sum()),
            "coverage_period": round(n_period / max(1, len(uni)), 4),
            "indicators": {
                "I1": "預收增加：(其他流動負債＋流動合約負債)／總資產 之 YoY 變化（百分點；原始為比例差）",
                "I2": "存貨周轉加快：TTM 銷貨成本／近5季存貨端點平均 之 YoY 變化（次）",
                "I3": "毛利率改善：TTM 毛利率 之 YoY 變化（百分點；原始為比例差）",
                "I4": "資本支出擴張：TTM 取得不動產廠房及設備／TTM 營收 之 YoY 變化（百分點；原始為比例差）",
            },
            "percentile_def": "同產業桶內、同指標、原始值由小到大的平均名次／該桶有值檔數（0-1，越高＝該指標在桶內越大）；"
                              "產業內可計分檔數<8 併入「其他」桶；I1-I4 可得<3 個者不進桶、不給百分位",
            "source": "FinMind 逐檔財報（損益、資產負債、現金流量），I1-I4 定義取自 paper_supply_v2.quarter_table_from_frames",
            "limits": [
                "FinMind 財報無公布日；基準季採法定期限已過之最近一季，已入庫者才顯示，未入庫者標「未入庫」",
                "產業分類為 TaiwanStockInfo 當下快照，非時點資料",
                "未套用價格存活篩選（本頁不含任何價格資料）",
                "財報入庫覆蓋率未達 80% 前，頁面不顯示桶內百分位，只顯示「資料準備中（已涵蓋 x／N 檔）」與原始變化值（先.十-三）",
            ],
            "fetch": {"calls": fstat.get("calls", 0), "ok": fstat.get("ok", 0), "fail": fstat.get("fail", 0),
                      "stopped": fstat.get("stopped"), "todo_missing": fstat.get("todo_missing", 0),
                      "todo_stale": fstat.get("todo_stale", 0)},
        },
        "rows": out_rows,
    }


def same_content(a: dict, b: dict) -> bool:
    def strip(d):
        m = dict(d["meta"])
        m.pop("as_of", None)
        m.pop("fetch", None)
        return {"meta": m, "rows": d["rows"]}
    return strip(a) == strip(b)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=500, help="本輪 FinMind 呼叫上限")
    ap.add_argument("--throttle", type=float, default=0.0, help="每次成功呼叫後額外等待秒數")
    ap.add_argument("--force", action="store_true", help="同日也覆寫輸出")
    ap.add_argument("--no-fetch", action="store_true", help="（保留相容）本腳本自先.十-二起一律只讀快取，不再抓取")
    ap.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    ap.add_argument("--out", default=str(OUT_PATH))
    a = ap.parse_args(argv)
    cache_dir, out = Path(a.cache_dir), Path(a.out)
    setup_cache(cache_dir)
    import paper_supply_v2 as pv2  # noqa: E402  唯讀借用 I1-I4 定義與法定期限函式

    now = now_tw()
    today = pd.Timestamp(now.date())
    period = pv2.target_period(today)
    D = pv2.deadline(period)
    uni = universe(cache_dir)
    ds_map, start = pv2.STMT_DS, pv2.STMT_START
    fstat = {"calls": 0, "note": "只讀快取；唯一抓取者為 research/finmind_warmup.py（先.十-二）"}
    df, n_cache, n_period, n_bucket = compute(uni, ds_map, start, period, pv2)
    payload = build_payload(df, uni, period, D, n_cache, n_period, n_bucket, fstat, now.strftime("%Y-%m-%d"))
    old = None
    if out.exists():
        try:
            old = json.loads(out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = None
    if old is not None and same_content(old, payload):
        print("[略過] 內容與既有檔相同，不改寫", flush=True)
    elif old is not None and not a.force and old.get("meta", {}).get("as_of") == payload["meta"]["as_of"]:
        print("[略過] 今日已產出過，每日只更新一次（--force 可覆寫）", flush=True)
    else:
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(out)
        print(f"[寫出] {out.name}：基準季 {period}（期限 {D.date()}），名冊 {len(uni)}，已入庫該季 {n_period}，可計分 {int(df['scored'].sum())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
