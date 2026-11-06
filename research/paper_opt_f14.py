# -*- coding: utf-8 -*-
"""先.一五四-1a ⑥ 紙上優化軌 F14（ML 價量選股，HGB）每日訊號產生器——研究帽產物，零外部請求。

策略（照 reaudit_optimized_batch2_ml.py，C15 成員用的 orig 曲線 key `63_0_30_0.15`，這裡不調參）：
  模型：sklearn HistGradientBoostingRegressor 預設參數、random_state=20261021；10 個價量特徵（同 ml_pricevol_oneshot.FEATURES）；
    標籤＝每月第一個交易日起持有 63 個交易日報酬的當日橫斷面百分位；訓練樣本＝#133 抽樣宇宙（research/data/reaudit_ssu_loaded.pkl）
    2011-01-01 起、標籤到期日 < 2025-01-01。
    〔自行裁量〕回測是逐年擴張重訓（測試年 Y 用標籤到期 < Y-01-01 的樣本）；紙上照同一規則接「測試年 2025」那一版後就凍結，
    不拿 2025 起（holdout 期間）的資料重訓。第一次跑時訓練一次，存 research/data/paper_opt/f14_model.joblib＋SHA256，之後不重訓。
  底層（1×，逐條對照 research/backtest/engine.py run_backtest() 重寫，因引擎擋 2025 起資料）：同 paper_opt_f12.py 的四步流程，差別：
    最多 30 檔、起跑日起每 63 個交易日換股、分數＝模型預測（當天有價格的宇宙股票全部給分，特徵缺值交給 HGB 原生處理，同回測）、
    出場＝第一層 還原收盤 < 自身 150 日均線（ml prep() 同 R.prep 補 ma150）＋第三層 還原收盤 ≤ 進場價×(1−15%)；大盤閘門關；
    沒有帳戶層（1×、無組合止損）。成本 validation.costs 1×、滑價 5bps（同引擎預設）。
特徵：research/paper_8_ml_tracker.py price_features()（照 factors.py 同一公式、scripts/selftest_paper_8_features.py 已在歷史資料核對）。
  大盤收盤用 paper_opt_f12 的 taiex_closes.json（官方＋更早用 0050 往前接，標 proxy_0050）——回測特徵用 FinMind 加權指數，
  前段口徑不同（只影響 f_rel_strength／f_idio_vol／f_bab／f_residual_momentum），照實揭露。
資料：同 F12（模擬 I 回看期官方日檔 2025-10-28～2026-10-30＋之後 data/price_history），另存成交量（股）與成交值（元），
  合併快取 research/data/paper_opt/f14_bars.json。回看期約 250 天，252 日類特徵（f_residual_momentum）11 月中以前可能 NaN。
輸出（append-only）：research/data/paper_opt/ledger_F14.jsonl、state_F14.json；每次換股另記特徵覆蓋率。
用法：python research/paper_opt_f14.py [--probe]
非投資建議。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402  （共用工具：宇宙、加權指數序列、成本常數）

costmod = F12.costmod
OUT = F12.OUT
LEDGER = OUT / "ledger_F14.jsonl"
STATE = OUT / "state_F14.json"
BARS = OUT / "f14_bars.json"
MODEL = OUT / "f14_model.joblib"
MODEL_META = OUT / "f14_model_meta.json"

START = F12.START
TOP_N, REBAL, PSTOP, MA_N = 30, 63, 0.15, 150
H = 63
RANDOM_STATE = 20261021
TRAIN_FROM, LABEL_END_BEFORE = "2011-01-01", "2025-01-01"
FEATURES = ["f_low_vol", "f_idio_vol", "f_bab", "f_short_reversal_1m", "f_short_term_reversal_1w", "f_amihud_illiq",
            "f_52w_high_prox", "f_residual_momentum", "f_rel_strength", "f_ma_breakout"]
SLIP = F12.SLIP_BPS / 10_000
BUY_RATE = F12.BUY_RATE
INIT = F12.INIT


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ 模型（只訓練一次）
def load_model():
    import joblib
    if MODEL.exists():
        meta = F12._rj(MODEL_META, {})
        if meta.get("sha256") and meta["sha256"] != _sha(MODEL):
            raise RuntimeError("f14_model.joblib 雜湊與登記不符，拒絕使用（不自動重訓）")
        return joblib.load(MODEL), meta
    import pickle
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingRegressor
    data = pickle.loads((HERE / "data" / "reaudit_ssu_loaded.pkl").read_bytes())
    frames = []
    for sid, df in data.items():
        d = df.sort_values("date").reset_index(drop=True)
        px = d["adj_close"].astype(float)
        f = d[["date"] + FEATURES].copy()
        f["date"] = pd.to_datetime(f["date"])
        f["fwd"] = px.shift(-H) / px - 1
        f["lab_end"] = f["date"].shift(-H)
        frames.append(f)
    P = pd.concat(frames, ignore_index=True)
    assert P["date"].max() < pd.Timestamp("2025-01-01"), "訓練資料含 2025 起資料"
    first_days = set(P.groupby(P["date"].dt.to_period("M"))["date"].min())
    S_ = P[P["date"].isin(first_days) & P["fwd"].notna()].copy()
    S_["label"] = S_.groupby("date")["fwd"].rank(pct=True)
    tr = S_[(S_["lab_end"] < pd.Timestamp(LABEL_END_BEFORE)) & (S_["date"] >= pd.Timestamp(TRAIN_FROM))]
    m = HistGradientBoostingRegressor(random_state=RANDOM_STATE).fit(tr[FEATURES], tr["label"])
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, MODEL)
    import sklearn
    meta = {"sha256": _sha(MODEL), "n_train_rows": int(len(tr)), "train_first": str(tr["date"].min())[:10],
            "train_last": str(tr["date"].max())[:10], "label_end_max": str(tr["lab_end"].max())[:10],
            "sklearn": sklearn.__version__, "features": FEATURES, "horizon": H, "random_state": RANDOM_STATE,
            "note": "照回測逐年擴張規則的『測試年 2025』版，之後凍結不重訓"}
    F12._wj(MODEL_META, meta)
    print(f"模型訓練完成：{meta['n_train_rows']} 列（{meta['train_first']}～{meta['train_last']}，標籤最晚 {meta['label_end_max']}）")
    return m, meta


# ------------------------------------------------------------------ 價量（含成交量／成交值）
def build_bars(ids: list[str]) -> tuple[dict, list[str]]:
    """{代號: {日期: [o,h,l,c,ret,vol,money]}}，邏輯同 F12.build_bars，多存成交量（股）與成交值（元）。"""
    want = set(ids)
    cache = F12._rj(BARS, {"bars": {}, "calendar": []})
    bars: dict = cache["bars"]
    cal = set(cache["calendar"])
    if not cache["calendar"]:
        for src in ("twse", "tpex"):
            for f in sorted(glob.glob(str(F12.LOOKBACK / src / "*.json"))):
                j = json.loads(Path(f).read_text(encoding="utf-8"))
                if j.get("status") != "ok":
                    continue
                dt = j["date"]
                rows = j.get("rows") or {}
                if src == "twse" and len(rows) > 500:
                    cal.add(dt)
                for sid in want & rows.keys():
                    o, h, lo, c, v, t, chg = rows[sid]
                    if not c or c <= 0:
                        continue
                    ref = c - chg if chg is not None else None
                    ret = (c / ref - 1.0) if ref and ref > 0 else None
                    bars.setdefault(sid, {})[dt] = [o, h, lo, c, ret, v, t]
    ph: dict = {}
    for f in sorted(glob.glob(str(F12.DATA / "price_history" / "b*.json"))):
        try:
            ph.update(json.loads(Path(f).read_text(encoding="utf-8"))["prices"])
        except Exception as e:
            print(f"[warn] 讀不到 {f}：{e}")
    cnt: dict[str, int] = {}
    for sid, rows in ph.items():
        for r in rows:
            if (r.get("close") or 0) > 0:
                cnt[r["date"]] = cnt.get(r["date"], 0) + 1
    last = max(cal) if cal else ""
    new_days = sorted(d for d, n in cnt.items() if n >= F12.MIN_TRADED and d > last)
    nd = set(new_days)
    for sid in want & ph.keys():
        rows = sorted((r for r in ph[sid] if r.get("date")), key=lambda r: r["date"])
        prev = None
        for r in rows:
            ok = (r.get("close") or 0) > 0 and (r.get("adj_close") or 0) > 0
            if ok and r["date"] in nd:
                ret = (r["adj_close"] / prev["adj_close"] - 1.0) if prev else None
                bars.setdefault(sid, {})[r["date"]] = [r["open"], r["high"], r["low"], r["close"], ret,
                                                       r.get("volume"), r.get("turnover")]
            if ok:
                prev = r
    cal |= nd
    calendar = sorted(cal)
    F12._wj(BARS, {"note": "F14 紙上：原始 OHLC＋還原日報酬＋成交量（股）＋成交值（元）", "calendar": calendar, "bars": bars})
    return bars, calendar


def features_and_ind(bars: dict, mkt: dict) -> tuple[dict, dict]:
    """回傳 (特徵 {代號: {日期: [10 個]}}, 指標 {代號: {日期: (adj, ma150)}})。"""
    import pandas as pd
    import paper_8_ml_tracker as P8
    feats, ind = {}, {}
    for sid, b in bars.items():
        ds, lv = F12.adj_levels({d: v[:5] for d, v in b.items()})
        px = pd.DataFrame({"date": ds, "adj_close": lv,
                           "Trading_Volume": [float(b[d][5]) if b[d][5] is not None else float("nan") for d in ds],
                           "Trading_money": [float(b[d][6]) if b[d][6] is not None else float("nan") for d in ds]})
        d = P8.price_features(px, mkt)
        ma = d["adj_close"].rolling(MA_N, min_periods=MA_N).mean()
        feats[sid] = {dt: [None if v != v else float(v) for v in row] for dt, row in zip(d["date"], d[FEATURES].to_numpy().tolist())}
        ind[sid] = {dt: (a, None if m != m else float(m)) for dt, a, m in zip(d["date"], d["adj_close"], ma)}
    return feats, ind


def predict(model, feats: dict, day: str, ids: set) -> tuple[dict, dict]:
    import numpy as np
    rows, sids = [], []
    for sid in sorted(ids):
        v = feats.get(sid, {}).get(day)
        if v is None:
            continue
        sids.append(sid)
        rows.append([np.nan if x is None else x for x in v])
    if not rows:
        return {}, {}
    import pandas as pd
    X = np.array(rows, float)
    sc = model.predict(pd.DataFrame(X, columns=FEATURES))
    cov = {f: round(float(np.mean(~np.isnan(X[:, i]))), 4) for i, f in enumerate(FEATURES)}
    return dict(zip(sids, map(float, sc))), cov


# ------------------------------------------------------------------ 一日
def step(day: str, s: dict, bars: dict, ind: dict, feats: dict, model) -> dict:
    e = s["engine"]
    log = {"fills": [], "scheduled": []}

    def row(sid):
        return bars.get(sid, {}).get(day)

    def prev_close(sid):
        b = bars.get(sid, {})
        ps = [d for d in b if d < day]
        return b[max(ps)][3] if ps else None

    still = []
    for p in e["pending"]:
        sid = p["sid"]
        r = row(sid)
        adj = ind.get(sid, {}).get(day, (None,))[0] if r else None
        if r is None or adj is None or adj <= 0:
            still.append(p)
            continue
        lk = F12._locked(r[:5], prev_close(sid))
        if (p["side"] == "buy" and lk.limit_up) or (p["side"] == "sell" and lk.limit_down):
            still.append(p)
            continue
        if p["side"] == "buy":
            sh = int((e["last_equity"] / TOP_N) // (adj * (1 + BUY_RATE)))
            if sh <= 0 or sid in e["pos"]:
                continue
            notional = sh * adj
            cost = notional * (costmod.COMMISSION_RATE + SLIP)
            if notional + cost > e["cash"]:
                continue
            e["cash"] -= notional + cost
            e["pos"][sid] = {"shares": sh, "entry_price": adj, "entry_date": day}
            log["fills"].append({"sid": sid, "side": "buy", "px_adj": round(adj, 4), "raw_close": r[3], "reason": p["reason"]})
        else:
            pos = e["pos"].pop(sid, None)
            if pos is None:
                continue
            notional = pos["shares"] * adj
            cost = notional * (costmod.tax_rate("normal") + costmod.COMMISSION_RATE + SLIP)
            e["cash"] += notional - cost
            log["fills"].append({"sid": sid, "side": "sell", "px_adj": round(adj, 4), "raw_close": r[3], "reason": p["reason"],
                                 "ret": round(adj / pos["entry_price"] - 1, 4)})
    e["pending"] = still

    def schedule(sid, side, reason):
        if any(p["sid"] == sid and p["side"] == side for p in e["pending"]):
            return
        e["pending"].append({"sid": sid, "side": side, "reason": reason, "scheduled": day})
        log["scheduled"].append({"sid": sid, "side": side, "reason": reason})

    # ② 第一層 MA150、第三層停損 15%（同引擎順序）
    for sid in list(e["pos"]):
        v = ind.get(sid, {}).get(day) if row(sid) else None
        if not v or v[0] is None or v[0] <= 0:
            continue
        e["last_valid"][sid] = v[0]
        if v[1] is not None and v[0] < v[1]:
            schedule(sid, "sell", "tier1_ma_exit")
        if v[0] <= e["pos"][sid]["entry_price"] * (1 - PSTOP):
            schedule(sid, "sell", "tier3_hard_stop")

    # ③ 換股日
    if e["day_i"] % REBAL == 0:
        live = {sid for sid in s["universe_set"] if row(sid)}
        sc, cov = predict(model, feats, day, live)
        ranked = sorted(sc.items(), key=lambda kv: kv[1], reverse=True)
        for sid in list(e["pos"]):
            if sid not in sc:
                schedule(sid, "sell", "rebalance_dropped")
        slots = TOP_N - len(e["pos"]) - sum(1 for p in e["pending"] if p["side"] == "buy")
        for sid, _ in ranked:
            if slots <= 0:
                break
            if sid in e["pos"] or any(p["sid"] == sid and p["side"] == "buy" for p in e["pending"]):
                continue
            schedule(sid, "buy", "rebalance_entry")
            slots -= 1
        log["rebalance"] = {"scored": len(sc), "feature_coverage": cov, "top": [k for k, _ in ranked[:TOP_N]]}

    # ④ mark to market
    mtm = e["cash"]
    for sid, pos in e["pos"].items():
        v = ind.get(sid, {}).get(day)
        px = v[0] if v and v[0] and row(sid) else e["last_valid"].get(sid, pos["entry_price"])
        mtm += pos["shares"] * px
    r1 = mtm / e["last_equity"] - 1.0
    e["last_equity"] = mtm
    e["day_i"] += 1
    return {"date": day, "ret": round(r1, 8), "ret_1x": round(r1, 8), "equity_1x": round(mtm, 2), "exposure": 1.0,
            "n_holdings": len(e["pos"]), "cash_frac": round(e["cash"] / mtm, 4) if mtm else None, **log}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    ids = F12.universe()
    model, meta = load_model()
    bars, calendar = build_bars(ids)
    f12_bars, f12_cal = F12.build_bars(ids)
    cl = F12.taiex_series(f12_bars, f12_cal)
    mkt = {d: v[0] for d, v in cl.items()}
    feats, ind = features_and_ind(bars, mkt)
    if a.probe:
        day = calendar[-1]
        live = {sid for sid in ids if bars.get(sid, {}).get(day)}
        sc, cov = predict(model, feats, day, live)
        top = sorted(sc.items(), key=lambda kv: -kv[1])[:TOP_N]
        print(f"模型 sha256 {meta.get('sha256', '')[:12]}…；訓練 {meta.get('n_train_rows')} 列")
        print(f"最新交易日 {day}；宇宙 {len(ids)} 檔、當天有價 {len(live)} 檔、給分 {len(sc)} 檔；交易日曆 {calendar[0]}～{calendar[-1]} 共 {len(calendar)} 天")
        print("特徵覆蓋率：", cov)
        print("假設今天換股，前 30：", [f"{k}:{v:.3f}" for k, v in top])
        return 0
    s = F12._rj(STATE, None) or {"start": START, "engine": {"cash": INIT, "pos": {}, "pending": [], "day_i": 0,
                                                             "last_equity": INIT, "last_valid": {}},
                                  "last_date": None, "universe_n": len(ids), "model_sha256": meta.get("sha256")}
    if a.start != START:
        s["start"] = a.start
    s["universe_set"] = set(ids)
    done = 0
    for day in calendar:
        if day < s["start"] or (s["last_date"] and day <= s["last_date"]):
            continue
        rec = step(day, s, bars, ind, feats, model)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        s["last_date"] = day
        done += 1
        print(f"{day} 1× {rec['ret_1x']:+.2%}　持股 {rec['n_holdings']}")
    s.pop("universe_set", None)
    F12._wj(STATE, s)
    print(f"本次寫入 {done} 個交易日（起跑 {s['start']}，最後 {s['last_date']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_f14 失敗：{e}")
        sys.exit(0)
