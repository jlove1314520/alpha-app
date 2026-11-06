# -*- coding: utf-8 -*-
"""先.一五五-2 F17：#446 core_tilt v2 成分內傾斜延長到 2025 起（紙上優化軌，描述性，不寫 TRIALS_LEDGER）。

做法（零新外部請求）：
- 本行程把 socket 連線封死（任何網路請求直接拋例外），finmind_client._fetch 改成「只讀本機 data/raw 聯集快取」；
- 執行期把各模組的 VAL_END 屬性改成 EXT_END（只改本行程記憶體，**不改任何原始碼**，含十三節核心檔 adjust.py／validation/）；
  〔自行裁量：F12 那批是自己重寫還原；這支量尺（重建臺灣50 市值排名＋股本＋除權息＋A_4pass 因子）牽涉模組太多，
   重寫會跟原版分岔，所以改成執行期覆寫截止日、原程式照跑，2024 底前結果拿來核對原表〕
- EXT_END＝2026-10-02（本機 2025 起個股價格快取 362／400 檔最後一日）。
- 格子與第一批 `reaudit_optimized_batch2_coretilt.py` 相同（32 格＋不傾斜臂），先跑不傾斜臂與原最優組，可分批斷點續跑。
用法：python research/reaudit_ext2025_coretilt.py [--report]
"""
from __future__ import annotations

import mem_guard
mem_guard.install()

import itertools
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OLD_END = "2024-12-31"
EXT_END = "2026-10-02"
CACHE = HERE / "data" / "reaudit_ext2025_coretilt_cells.json"
OUT_JSON = HERE / "data" / "reaudit_ext2025_coretilt.json"
PNG = HERE / "data" / "reaudit_curves" / "ext2025_F17.png"
ORIG_BEST = (0.02, 0.03, 63, 1)


# ---- 1. 封網 ----
def _no_net(*a, **k):
    raise RuntimeError("reaudit_ext2025_coretilt：本行程禁止網路請求（只讀本機快取）")


socket.socket.connect = _no_net  # type: ignore[assignment]
socket.create_connection = _no_net  # type: ignore[assignment]
# 2026-11-07 20261107-013102 第一次執行漏擋：yfinance 走 curl_cffi（C 層 libcurl）不經 Python socket，
# adjusted_price_series 的 yfinance 主路徑快取檔名綁截止日，覆寫截止日後對不上快取 → 實際送出約 100 次 yfinance 請求。
# 修法：requests／curl_cffi 一律拋例外，yfinance 路徑直接回空表（退回 FinMind 本機快取路徑）。
import requests as _rq  # noqa: E402
_rq.Session.request = _no_net  # type: ignore[assignment]
try:
    import curl_cffi.requests as _cc  # noqa: E402
    _cc.Session.request = _no_net  # type: ignore[assignment]
except Exception:  # noqa: BLE001
    pass
import yf_price_client as _yf  # noqa: E402
_yf.fetch_yf_adjusted = lambda *a, **k: pd.DataFrame(columns=[
    "date", "stock_id", "open", "high", "low", "close", "volume", "source",
    "max", "min", "Trading_Volume", "Trading_money"])

# ---- 2. FinMind 只讀聯集快取 ----
import finmind_client as FC  # noqa: E402

_IDX: dict = {}


def _index():
    if not _IDX:
        for name in os.listdir(FC.DATA_DIR):
            if name.endswith(".parquet"):
                p = name.split("__")
                if len(p) >= 3:
                    _IDX.setdefault((p[0], p[1]), []).append(FC.DATA_DIR / name)
        for v in _IDX.values():
            v.sort(key=lambda x: (x.name.endswith("latest.parquet"), x.name))   # latest 檔最後讀、去重時保留
    return _IDX


def _cache_only_fetch(dataset, data_id="", start_date="2000-01-01", end_date=None, force_refresh=False, **_):
    files = _index().get((dataset, data_id or "ALL"), [])
    frames = []
    for f in files:
        try:
            d = pd.read_parquet(f)
        except Exception as e:  # noqa: BLE001
            print(f"  [快取讀取失敗，略過] {f.name}: {type(e).__name__}", flush=True)
            continue
        if not d.empty:
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "date" in df.columns:
        ds = df["date"].astype(str).str[:10]
        m = ds >= str(start_date)[:10]
        if end_date:
            m &= ds <= str(end_date)[:10]
        df = df[m]
        sub = [c for c in ("date", "stock_id", "type", "origin_name") if c in df.columns]
        df = df.drop_duplicates(sub, keep="last").sort_values("date").reset_index(drop=True)
    else:
        df = df.drop_duplicates()
    return df


FC._fetch = _cache_only_fetch

# ---- 3. 匯入原程式，再覆寫截止日 ----
import validation.holdout as H  # noqa: E402
import core_tilt_v2_stage1 as C  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402
import leveraged_bb90_backtest as LB  # noqa: E402,F401
from validation.costs import round_trip_cost_pct  # noqa: E402

_patched = []
for name, mod in list(sys.modules.items()):
    if mod is not None and getattr(mod, "VAL_END", None) == OLD_END:
        try:
            setattr(mod, "VAL_END", EXT_END)
            _patched.append(name)
        except Exception:  # noqa: BLE001
            pass
LB.END = "2099-12-31"   # 只在本行程延長央行定存讀取範圍（同 reaudit_ext2025_engine.py）
import pit_mktcap_rank as pmr  # noqa: E402
pmr._raw_index.cache_clear(); pmr.shares_table.cache_clear(); pmr.close_series.cache_clear()

TILTS, BANDS, REBALS, SIGNS = (0.02, 0.05, 0.10, 0.20), (0.03, 1.0), (21, 63), (1, -1)
key = lambda c: f"{c[0]}_{c[1]}_{c[2]}_{c[3]}"
prog = S.prog


def run_cells(deadline: float) -> int:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    grid = list(itertools.product(TILTS, BANDS, REBALS, SIGNS))
    order = ["untilted", ORIG_BEST] + [c for c in grid if c != ORIG_BEST]
    todo = [c for c in order if (c if c == "untilted" else key(c)) not in cache]
    if not todo:
        return 0
    t0 = time.time()
    prog(f"已覆寫 VAL_END 的模組：{_patched}")
    inp = C.load_inputs()
    prog(f"載入 {time.time()-t0:.0f}s：交易日 {inp['days'][0]}～{inp['days'][-1]}、成分聯集 {len(inp['members'])}、"
         f"有因子 {len(inp['data'])}、剔除 {len(inp['dropped'])}")
    cache["_meta"] = {"days": [inp["days"][0], inp["days"][-1]], "members": len(inp["members"]),
                      "with_factors": len(inp["data"]), "dropped": inp["dropped"][:200],
                      "last_sched": [{k: v for k, v in s.items() if k != "members"} | {"n": len(s["members"])}
                                     for s in inp["sched"][-4:]]}
    cost_rt = round_trip_cost_pct()
    sc: dict = {}

    def scores(b, m):
        k = (b, tuple(m))
        if k not in sc:
            sc[k] = C.scores_at(b, m, inp)
        return sc[k]
    segc: dict = {}
    for c in todo:
        if time.time() > deadline:
            prog("時間到，存斷點")
            break
        t1 = time.time()
        if c == "untilted":
            C.REBAL_EVERY = 21
            segs = segc.setdefault(21, C.segments(inp))
            _, r, _, _, log = C.simulate(inp, segs, None, cost_rt)
        else:
            tp, band, reb, sign = c
            C.TILT_PP, C.INDUSTRY_BAND_PP, C.REBAL_EVERY = tp, band, reb
            if reb not in segc:
                segc[reb] = C.segments(inp)
            fn = (lambda b, m: scores(b, m)) if sign > 0 else (lambda b, m: -scores(b, m))
            _, _, _, r, log = C.simulate(inp, segc[reb], fn, cost_rt)
        r = r.dropna()
        r = r[r.index <= EXT_END]
        eq = (1 + r).cumprod()
        pts = [x["base"] for x in log if x["base"] in eq.index] + [eq.index[-1]]
        per = [float(eq[b] / eq[a] - 1) for a, b in zip(pts[:-1], pts[1:])]
        cache[c if c == "untilted" else key(c)] = {
            "dates": [str(x)[:10] for x in r.index], "ret": [float(x) for x in r], "n_rebalances": len(log),
            "win_rate": float(np.mean([p > 0 for p in per])) if per else None}
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
        prog(f"{c} 完成（{time.time()-t1:.0f}s）")
    left = [c for c in order if (c if c == "untilted" else key(c)) not in cache]
    prog(f"尚餘 {len(left)} 格")
    return 2 if left else 0


def _curve(c, L, stop):
    dates = pd.to_datetime(pd.Series(c["dates"]))
    eq = np.concatenate([[1.0], np.cumprod(1 + np.array(c["ret"], float))])
    d2 = pd.concat([pd.Series([dates.iloc[0] - pd.Timedelta(days=1)]), dates], ignore_index=True)
    curve, _ = S.overlay(eq, LB.load_tw_rf_daily(d2), L, stop)
    return pd.Series(np.asarray(curve, float), index=d2.values)


def _seg(curve: pd.Series, a=None, b=None):
    s = curve
    if a is not None:
        prev = s[s.index < pd.Timestamp(a)]
        s = pd.concat([prev.iloc[-1:], s[s.index >= pd.Timestamp(a)]]) if len(prev) else s[s.index >= pd.Timestamp(a)]
    if b is not None:
        s = s[s.index <= pd.Timestamp(b)]
    cagr, mdd, sh = S.stats(s.to_numpy() / float(s.iloc[0]), pd.Series(s.index))   # 段起點歸一
    return {"cagr": float(cagr), "mdd": float(mdd), "sharpe": float(sh), "start": str(s.index[0])[:10], "end": str(s.index[-1])[:10]}


def report() -> int:
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "ext_end": EXT_END, "meta": cache.get("_meta"),
           "orig_best": {"tilt_pp": 0.02, "band": 0.03, "rebalance_days": 63, "direction": "順向", "L": 1.0, "stop": 0.1}}
    rows = {}
    for name, k, L, st in (("原最優組", key(ORIG_BEST), 1.0, 0.1), ("不傾斜臂 1×", "untilted", 1.0, None),
                           ("不傾斜臂 1× 止損10%", "untilted", 1.0, 0.1)):
        if k not in cache:
            continue
        cv = _curve(cache[k], L, st)
        rows[name] = {"pre2025": _seg(cv, None, OLD_END), "post2025": _seg(cv, "2025-01-01"), "full": _seg(cv),
                      "trades": cache[k]["n_rebalances"], "win_rate": cache[k]["win_rate"]}
    out["rows"] = rows
    grid = [key(c) for c in itertools.product(TILTS, BANDS, REBALS, SIGNS)]
    done = [k for k in grid if k in cache]
    out["grid_done"] = f"{len(done)}/{len(grid)}"
    if len(done) == len(grid):
        best = None
        for k in done:
            for L, st in itertools.product(S.LEVS, S.STOPS):
                st2 = None if st is None or st != st else st
                cv = _curve(cache[k], L, st2)
                f = _seg(cv)
                if f["mdd"] < -0.50:
                    continue
                cal = f["cagr"] / abs(f["mdd"]) if f["mdd"] < 0 else 0
                if best is None or cal > best[0]:
                    best = (cal, k, L, st2, f, _seg(cv, "2025-01-01"))
        cal, k, L, st, f, p = best
        tp, band, reb, sign = k.split("_")
        out["reopt_full"] = {"tilt_pp": float(tp), "band": float(band), "rebalance_days": int(reb),
                             "direction": "順向" if int(sign) > 0 else "反向", "L": L, "stop": st,
                             "full": f, "post2025": p, "calmar": cal}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    if key(ORIG_BEST) in cache and "untilted" in cache:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(_curve(cache[key(ORIG_BEST)], 1.0, 0.1), label="orig best (2pp,63d,1x,stop10%)", color="#2a6fdb")
        ax.plot(_curve(cache["untilted"], 1.0, None), label="untilted rebuilt 0050 (1x)", color="#999999")
        ax.axvline(pd.Timestamp("2025-01-01"), color="#c33", ls="--", lw=1)
        ax.set_yscale("log"); ax.legend(); ax.set_title("F17 core_tilt v2 extended to 2026-10 (params fixed from 2013-2024)")
        fig.tight_layout(); fig.savefig(PNG, dpi=110)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float)[:4000])
    return 0


if __name__ == "__main__":
    if "--report" in sys.argv:
        sys.exit(report())
    budget = float(os.environ.get("REAUDIT_BUDGET_SEC", "1200"))
    rc = run_cells(time.time() + budget)
    report()
    sys.exit(rc)
