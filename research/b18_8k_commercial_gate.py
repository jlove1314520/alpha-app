"""B18 未來性濾網 (b) 類：SEC 8-K「純商業協議」Item 1.01 事件漂移，GATE_SEQUENCE 逐關判定。

規格（事前登記，執行前已 commit）：research/B18_8K_COMMERCIAL_SPEC.md。
本檔只實作規格，不在這裡重新決定任何參數；改參數＝新試驗。

輸出：research/b18_8k_commercial_gate_result.json（逐關數字與判定）。
SEC 請求：沿用 sec_edgar_client 的磁碟快取，未命中快取的請求後固定 sleep 0.2 秒
（約 5 req/秒，低於官方 10 req/秒，見 C:\\alpha\\CLAUDE.md 頻率清單）。
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import sec_edgar_client as sec  # noqa: E402
from control_group_standard import evaluate_vs_control  # noqa: E402
from us_8k_pead_gate52 import reaction_day_index  # noqa: E402
from validation import holdout  # noqa: E402
from validation.us_costs import round_trip_cost_pct  # noqa: E402
from yf_price_client import fetch_yf_index  # noqa: E402

PRICE_DIR = HERE / "data" / "dera_insider" / "prices"
PRICE_STATUS = HERE / "insider_dera_price_fetch_status.json"
OUT = HERE / "b18_8k_commercial_gate_result.json"

SAMPLE_SEED = 20261011_18
SAMPLE_N = 400
H = 20
H_GRID = [10, 14, 20, 26, 30]
BUFFER = 25
ALLOWED_ITEMS = {"1.01", "7.01", "8.01", "9.01"}
CONTROL_SEEDS = {"seed_a": 20261011_181, "seed_b": 20261011_182}
N_DRAWS = 200
POSITION_USD = 10_000.0
SEC_SLEEP = 0.2


def _sec_get(fn, *args):
    """未命中快取才 sleep；失敗回 None 並記錄，不讓單一 CIK 失敗中斷整輪。"""
    cache_name = None
    if fn is sec.get_submissions:
        cache_name = f"submissions_{str(args[0]).zfill(10)}"
    elif fn is sec.get_archive_filings:
        cache_name = f"archive_{args[1].replace('.json', '')}"
    p = sec._cache_path(cache_name) if cache_name else None
    cached = p is not None and p.exists() and (time.time() - p.stat().st_mtime) < sec._CACHE_MAX_AGE_SECONDS
    try:
        return fn(*args)
    finally:
        if not cached:
            time.sleep(SEC_SLEEP)


def get_8k_full(cik: int) -> list[dict]:
    data = _sec_get(sec.get_submissions, cik)

    def _extract(block: dict) -> list[dict]:
        n = len(block.get("form", []))
        return [{"acceptanceDateTime": block["acceptanceDateTime"][i], "items": block["items"][i]}
                for i in range(n) if block["form"][i] == "8-K"]

    out = _extract(data.get("filings", {}).get("recent", {}))
    for arc in data.get("filings", {}).get("files", []):
        out.extend(_extract(_sec_get(sec.get_archive_filings, cik, arc["name"])))
    return out


def is_commercial(items_raw: str | None) -> bool:
    if not items_raw:
        return False
    items = {x.strip() for x in items_raw.split(",") if x.strip()}
    return "1.01" in items and items <= ALLOWED_ITEMS


def period_of(d: str) -> str:
    if d <= holdout.TRAIN_END:
        return "TRAIN"
    if d <= holdout.VAL_END:
        return "VAL"
    return "OUT"


def load_px(ticker: str) -> pd.DataFrame | None:
    p = PRICE_DIR / f"px_{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p).rename(columns={"Date": "date"})
    d["date"] = d["date"].astype(str).str[:10]
    d = d[d["date"] <= holdout.VAL_END].dropna(subset=["adj_close"])
    d = d[d["adj_close"] > 0].reset_index(drop=True)
    return d if len(d) >= 60 else None


def main() -> int:
    # holdout（2025+）已於先前輪次依程序解鎖；本試驗只用 TRAIN/VAL，
    # 不以「已消耗」為由中止，改在下方用 assert_no_holdout_leakage 硬性檢查沒有越過 VAL_END。
    st = json.loads(PRICE_STATUS.read_text(encoding="utf-8"))["tickers"]
    cik_map = sec.get_cik_map()
    pool = sorted(t for t, v in st.items() if v.get("status") == "ok" and t in cik_map)
    tickers = random.Random(SAMPLE_SEED).sample(pool, min(SAMPLE_N, len(pool)))
    print(f"價格快取宇宙 ok 且對得到 CIK：{len(pool)} 檔；抽 {len(tickers)} 檔 seed={SAMPLE_SEED}")

    spy = fetch_yf_index("SPY", start_date="2005-01-01")
    spy_close = dict(zip(spy["date"], spy["close"].astype(float)))
    print(f"SPY {len(spy)} 列 {spy['date'].iloc[0]}~{spy['date'].iloc[-1]}")

    hmax = max(H_GRID)
    events = []          # dict per event
    ctrl = {}            # ticker -> (eligible idx array, closes, spy aligned)
    skips = {"sec_fail": 0, "no_price": 0, "dup_in_window": 0, "oob": 0, "spy_missing": 0}
    n_commercial_raw = 0
    n_any_101 = 0
    for k, t in enumerate(tickers):
        px = load_px(t)
        if px is None:
            skips["no_price"] += 1
            continue
        try:
            filings = get_8k_full(cik_map[t])
        except Exception as e:  # noqa: BLE001 - 單一 CIK 失敗只記錄，不中斷
            print(f"  [warn] {t} SEC 取得失敗：{e}")
            skips["sec_fail"] += 1
            continue
        cal = px["date"].tolist()
        closes = px["adj_close"].to_numpy(float)
        spy_al = np.array([spy_close.get(d, np.nan) for d in cal])
        n = len(cal)
        n_any_101 += sum(1 for f in filings if f["items"] and "1.01" in f["items"].split(","))
        com = [f for f in filings if is_commercial(f["items"])]
        n_commercial_raw += len(com)
        idxs = sorted({i for i in (reaction_day_index(f["acceptanceDateTime"], cal) for f in com) if i is not None})
        # 反應日必須落在該檔價格區間內（序列首日之前的申報 reaction_day_index 會給 0，排除）
        idxs = [i for i in idxs if i >= 1 and cal[i] >= cal[0]]
        last_kept = -10**9
        kept = []
        for i in idxs:
            if i - last_kept <= H:
                skips["dup_in_window"] += 1
                continue
            if i + hmax >= n:
                skips["oob"] += 1
                continue
            if np.isnan(spy_al[i]) or np.isnan(spy_al[i + hmax]):
                skips["spy_missing"] += 1
                continue
            kept.append(i)
            last_kept = i
        for i in kept:
            events.append({"ticker": t, "date": cal[i], "idx": i, "period": period_of(cal[i]),
                           "price": float(closes[i])})
        excl = set()
        for i in idxs:
            excl.update(range(i - BUFFER, i + BUFFER + 1))
        elig = np.array([i for i in range(1, n - hmax) if i not in excl
                         and not np.isnan(spy_al[i]) and not np.isnan(spy_al[i + hmax])], dtype=int)
        ctrl[t] = (elig, closes, spy_al)
        if (k + 1) % 50 == 0:
            print(f"  進度 {k+1}/{len(tickers)}，累計事件 {len(events)}")

    def excess(t, i, h):
        _, c, s = ctrl[t]
        return (c[i + h] / c[i] - 1.0) - (s[i + h] / s[i] - 1.0)

    for e in events:
        for h in H_GRID:
            e[f"x{h}"] = excess(e["ticker"], e["idx"], h)

    def control_draws(evs, h, seed):
        rng = np.random.default_rng(seed)
        out = []
        usable = [e for e in evs if len(ctrl[e["ticker"]][0]) > 0]
        for _ in range(N_DRAWS):
            vals = []
            for e in usable:
                elig = ctrl[e["ticker"]][0]
                j = int(elig[rng.integers(len(elig))])
                vals.append(excess(e["ticker"], j, h))
            out.append(float(np.mean(vals)))
        return out

    res = {"spec": "research/B18_8K_COMMERCIAL_SPEC.md", "sample_seed": SAMPLE_SEED,
           "n_tickers_sampled": len(tickers), "universe_pool": len(pool), "skips": skips,
           "n_8k_any_101": n_any_101, "n_commercial_raw": n_commercial_raw, "gates": {}}
    holdout.assert_no_holdout_leakage(pd.DataFrame(events), date_col="date", context="b18_8k_commercial_gate")
    by = {p: [e for e in events if e["period"] == p] for p in ("TRAIN", "VAL")}
    for p in ("TRAIN", "VAL"):
        print(f"{p}: {len(by[p])} 事件")
    G = res["gates"]

    # 第 1 關 sanity
    blowups = [(e["ticker"], e["date"], round(e[f"x{H}"], 3)) for e in events if abs(e[f"x{H}"]) > 3.0]
    nan_n = sum(1 for e in events if not np.isfinite(e[f"x{H}"]))
    g1 = len(by["TRAIN"]) >= 100 and len(by["VAL"]) >= 100 and nan_n == 0
    G["1_sanity"] = {"pass": g1, "n_train": len(by["TRAIN"]), "n_val": len(by["VAL"]),
                     "nan": nan_n, "blowups_gt300pct": blowups}

    def gate_vs_ctrl(evs, h, label):
        sig = float(np.mean([e[f"x{h}"] for e in evs]))
        draws = {name: control_draws(evs, h, seed) for name, seed in CONTROL_SEEDS.items()}
        flat = [x for v in draws.values() for x in v]
        v = evaluate_vs_control(signal_stat=sig, control_draws=draws, selection_spec=(
            f"事前綁定 B18_8K_COMMERCIAL_SPEC.md（commit 67122095c）：items⊆{{1.01,7.01,8.01,9.01}} 含1.01，"
            f"反應日收盤進場持有 {h} 日相對 SPY 超額報酬平均，{label}，同檔配對控制組±{BUFFER}日緩衝"))
        return sig, v, float(np.percentile(flat, 95)), draws

    sig_tr, v_tr, p95_tr, _ = gate_vs_ctrl(by["TRAIN"], H, "TRAIN")
    G["2_random_control_TRAIN"] = {"pass": bool(v_tr.passed), "signal_mean_excess": sig_tr,
                                   "control_max": v_tr.control_max, "control_mean": v_tr.control_mean,
                                   "percentile": v_tr.control_percentile, "reason": v_tr.reason}

    plateau = {}
    for h in H_GRID:
        s, v, p95, _ = gate_vs_ctrl(by["TRAIN"], h, "TRAIN 高原")
        plateau[h] = {"signal": s, "control_p95": p95, "ok": s > p95}
    G["3_plateau_TRAIN"] = {"pass": all(x["ok"] for x in plateau.values()), "grid": plateau}

    costs = {}
    for kx in (1, 2, 3):
        row = {}
        for p in ("TRAIN", "VAL"):
            nets = [e[f"x{H}"] - kx * round_trip_cost_pct(e["price"], shares=max(1.0, round(POSITION_USD / e["price"])))
                    for e in by[p]]
            row[p] = float(np.mean(nets)) if nets else float("nan")
        costs[f"{kx}x"] = row
    G["4_cost"] = {"pass": all(r["TRAIN"] > 0 and r["VAL"] > 0 for r in costs.values()), "net_mean": costs}

    tr = pd.DataFrame(by["TRAIN"])
    tr["year"] = tr["date"].str[:4]
    yr = tr.groupby("year")[f"x{H}"].agg(["mean", "sum", "count"])
    top_year = yr["sum"].idxmax()
    loo = tr[tr["year"] != top_year]
    loo_mean = float(loo[f"x{H}"].mean())
    G["5_leave_one_out"] = {"pass": loo_mean > 0 and loo_mean > p95_tr, "dropped_year": top_year,
                            "mean_after_drop": loo_mean, "train_control_p95": p95_tr}
    pos_ratio = float((yr["mean"] > 0).mean())
    G["6_yearly_consistency"] = {"pass": pos_ratio >= 5 / 6, "positive_year_ratio": pos_ratio,
                                 "by_year": {y: {"mean": float(r["mean"]), "n": int(r["count"])} for y, r in yr.iterrows()}}

    sig_va, v_va, _, _ = gate_vs_ctrl(by["VAL"], H, "VAL")
    G["7_oos_VAL"] = {"pass": bool(v_va.passed), "signal_mean_excess": sig_va, "control_max": v_va.control_max,
                      "control_mean": v_va.control_mean, "percentile": v_va.control_percentile, "reason": v_va.reason}

    order = ["1_sanity", "2_random_control_TRAIN", "3_plateau_TRAIN", "4_cost",
             "5_leave_one_out", "6_yearly_consistency", "7_oos_VAL"]
    first_fail = next((g for g in order if not G[g]["pass"]), None)
    res["first_failed_gate"] = first_fail
    res["verdict"] = "FAIL" if first_fail else "PASS_GATES_1_7（天條一/跨市場/前向待做，部署前停下提案）"
    res["note"] = ("依 GATE_SEQUENCE 第一個 FAIL 的關卡即為判定；其後各關數字僅供診斷，不構成任何通過主張。"
                   "存活者偏誤未完全修正：已下市股 7.1%（775／10,863 檔）無價格來源；本試驗價格宇宙另偏向存活者（yfinance 現存代號＋DERA 內部人買入發行人）。")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for g in order:
        print(g, "PASS" if G[g]["pass"] else "FAIL")
    print("判定：", res["verdict"], "首個 FAIL：", first_fail)
    print(json.dumps({k: {kk: vv for kk, vv in G[k].items() if kk not in ("by_year", "blowups_gt300pct", "grid")}
                      for k in order}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
