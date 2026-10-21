# -*- coding: utf-8 -*-
"""模擬 H：ML 個股前向紙上追蹤（先.一二七-B2，照 docs/PREREG_paper_h_ml_forward.md，事前登記 #459）。

規則照 PREREG（參數一次定死，不調參、不倒填、不改任何一條）：
- 模型：sklearn HistGradientBoostingRegressor 全部預設參數、random_state=20261021；只訓練一次、整個追蹤期凍結。
- 訓練樣本：2013-01～2024-11 每月一列／檔；標籤＝持有期報酬（當月第一個交易日收盤 → 次月第一個交易日收盤）
  的當月橫斷面百分位排名。標籤終點最晚 2024-12-02，**只讀 2024-12-31 以前的報酬**（load_dev 硬上限 VAL_END）。
- 特徵：草稿第 2 節 26 個既有因子（research/factors.py prepare_factors），取執行日前一個交易日的值；
  訓練期覆蓋率 <50% 的特徵機械式排除（訓練時一次算出、寫進 paper_8_model/features.json，之後不改）。
- 組合（前向）：預測分數前 30 名等權進場、已持有者跌出前 90 名（或失去宇宙資格）才出場、空位由最高分補滿；
  每月第一個有收盤資料的執行日再平衡；起算 2026-12-01，之前不建倉、不倒填。成本 engine.py buy/sell_leg_rate 1×。

子命令：
  python research/paper_8_ml_tracker.py build-panel [--until HH:MM]   分批算訓練特徵面板（可續跑，本機快取、不進 repo）
  python research/paper_8_ml_tracker.py train                          訓練一次＋存模型＋雜湊（模型已存在就拒絕重訓）
  python research/paper_8_ml_tracker.py dry-run                        只算最新交易日的前向宇宙與特徵覆蓋率（不預測、不寫帳本）
  python research/paper_8_ml_tracker.py                                排程用（market.yml）：每月預測＋帳本＋App 摘要

[自行裁量]（PREREG 沒寫到、照實記錄，總司令可推翻）：
1. 訓練宇宙＝research/universe.py universe()（含已下市）裡的普通股（4 碼、非 0 開頭、排除 91 開頭），
   當月執行日有收盤價、特徵日近 20 日平均成交值 ≥3,000 萬（與前向宇宙同一門檻）。
2. 已下市股：持有期內下市者，標籤用持有期終點以前最後一個收盤價（下市以最後成交價出場，同草稿第 3 節）。
3. 三大法人類（f_foreign_streak／f_inst_flow／f_inst_streak_days）在 prepare_factors 裡把缺資料補 0，
   會讓「沒資料」看起來像「有值」；本程式在該日沒有任何法人原始列時改回 NaN，覆蓋率才算得對。
4. 訓練特徵一律離線計算：只讀本機快取，任何網路連線都被擋下（快取缺的資料集視為缺值，不打 FinMind）。
5. 例外：TaiwanStockSplitPrice 缺快取視為「無分割事件」（本機快取抽樣 99% 是空表），其餘資料集缺快取該檔失敗、照實記錄。
   減資表（TaiwanStockCapitalReductionReferencePrice）不比照：已快取的 1,039 檔有 259 檔非空（25%），當空表會算錯還原價。
6. 前向大盤序列：market_tw.json 的官方近 60 日加權指數收盤，每班併進 research/data/paper_8_taiex_closes.json 累積（零額外請求）。
7. 前向特徵：價量 10 個照 factors.py 同一公式（price_features，scripts/selftest_paper_8_features.py 在歷史資料上核對一致）；
   月營收 2 個直接呼叫 factors 同一支函式、資料換成 data/fundamentals.json 官方累積月營收（pit＝次月 10 日）；
   其餘 14 個（籌碼、季報、殖利率）repo 沒有同定義的前向資料，一律 NaN，每次再平衡把各特徵覆蓋率寫進帳本。
   repo 價格檔只留約 90 個交易日，252 日類（f_52w_high_prox、f_residual_momentum）前向也是 NaN。
自身失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import hashlib
import json
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(RESEARCH))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TW = timezone(timedelta(hours=8))
MODEL_DIR = RESEARCH / "paper_8_model"
MODEL_PATH = MODEL_DIR / "model.joblib"
FEATURES_PATH = MODEL_DIR / "features.json"
PANEL_DIR = RESEARCH / "data" / "paper_8_train_panel"   # research/data/ 已 gitignore：FinMind 衍生資料不進公開 repo
LOG = RESEARCH / "data" / "paper_8_log.jsonl"
OUT = ROOT / "data" / "paper_8.json"

RANDOM_STATE = 20261021
TRAIN_FIRST_MONTH, TRAIN_LAST_MONTH = "2013-01", "2024-11"
LABEL_END_CAP = "2024-12-31"
FACTOR_START = "2010-01-01"
START_NOT_BEFORE = "2026-12-01"
TOP_N, EXIT_RANK = 30, 90
MIN_TURNOVER = 30_000_000.0
LIQ_DAYS = 20
MIN_COVERAGE = 0.50
INITIAL = 1_000_000.0
LABEL = "模擬 H ML 個股（樹模型）"
NOTE = ("每月再平衡：樹模型（26 個既有因子、預設參數、2013～2024-11 訓練一次凍結）預測分數前 30 名進場、"
        "跌出前 90 名出場、等權；近 20 日平均成交值 ≥3,000 萬；成本 1×")

# 草稿第 2 節的 26 個特徵（排除 f_value_pb／f_value_pe／f_listing_age_days／f_odd_lot_imbalance，理由見草稿）
FEATURES = [
    # 價量 10
    "f_low_vol", "f_idio_vol", "f_bab", "f_short_reversal_1m", "f_short_term_reversal_1w",
    "f_amihud_illiq", "f_52w_high_prox", "f_residual_momentum", "f_rel_strength", "f_ma_breakout",
    # 籌碼 6
    "f_foreign_streak", "f_inst_flow", "f_inst_streak_days",
    "f_margin_utilization", "f_short_sale_utilization", "f_short_margin_ratio",
    # 基本面 10
    "f_rev_accel", "f_revenue_surprise", "f_eps_growth", "f_eps_surprise", "f_quality_roe_stability",
    "f_gross_margin_stability", "f_gross_profitability", "f_asset_growth", "f_accruals", "f_dividend_yield_ttm",
]
INST_FEATURES = ("f_foreign_streak", "f_inst_flow", "f_inst_streak_days")
assert len(FEATURES) == 26


def is_common(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and code[0] != "0" and not code.startswith("91")


def _offline_guard() -> None:
    """訓練特徵只准讀本機快取：擋下所有對外連線（快取缺 → 該資料集視為缺值）。"""
    def _blocked(*_a, **_k):
        raise OSError("paper_8 離線模式：禁止網路連線（只讀本機快取）")
    socket.socket.connect = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    import finmind_client as fc
    orig = fc._fetch

    def _cache_only(dataset, data_id="", start_date="2000-01-01", end_date=None, **kw):
        if not fc._cache_path(dataset, data_id, start_date, end_date).exists():
            if dataset == "TaiwanStockSplitPrice":
                # [自行裁量]5：分割表本機已快取 726 檔、抽樣 400 檔只有 4 檔非空；缺快取視為無分割事件，
                # 否則約 728 檔整檔失敗（2026-10-21 第 1 批實測），訓練樣本會少四成。
                import pandas as pd
                return pd.DataFrame()
            raise RuntimeError(f"paper_8 離線模式：本機無快取 {dataset}/{data_id}/{start_date}/{end_date}")
        return orig(dataset, data_id, start_date, end_date, **kw)
    fc._fetch = _cache_only


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ───────────────────────────── 訓練面板 ─────────────────────────────

def _month_exec_days(calendar: list[str]) -> list[str]:
    """每月第一個交易日（TAIEX 交易日曆）。"""
    out, seen = [], set()
    for d in calendar:
        if d[:7] not in seen:
            seen.add(d[:7])
            out.append(d)
    return out


def _stock_rows(sid: str, market_df, exec_days: list[str], prev_day: dict) -> list[dict]:
    import numpy as np
    import pandas as pd
    import factors
    from adjust import adjusted_price_series

    px = adjusted_price_series(sid, FACTOR_START)
    if px is None or px.empty or len(px) < 260:
        return []
    d = factors.prepare_factors(sid, px, market_df, FACTOR_START)
    d = d.sort_values("date").reset_index(drop=True)
    # [自行裁量]3：法人原始列不存在的日子改回 NaN
    try:
        inst = factors._institutional_daily_net(sid, FACTOR_START)
        has_inst = set(pd.to_datetime(inst["date"]).dt.strftime("%Y-%m-%d")) if not inst.empty else set()
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {sid} 法人原始列讀取失敗，法人特徵當缺值：{e}")
        has_inst = set()
    dates = pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d").tolist()
    d["_d"] = dates
    no_inst = ~d["_d"].isin(has_inst)
    for c in INST_FEATURES:
        if c in d.columns:
            d.loc[no_inst, c] = np.nan
    for c in FEATURES:
        if c not in d.columns:
            d[c] = np.nan
    tm = pd.to_numeric(d.get("Trading_money"), errors="coerce")
    d["_liq"] = tm.rolling(LIQ_DAYS, min_periods=LIQ_DAYS).mean()
    by_date = {dt: i for i, dt in enumerate(dates)}
    adj = d["adj_close"].to_numpy(dtype=float)
    rows = []
    months = [x for x in exec_days if TRAIN_FIRST_MONTH <= x[:7] <= TRAIN_LAST_MONTH]
    for ex in months:
        nxt_i = exec_days.index(ex) + 1
        if nxt_i >= len(exec_days):
            continue
        nxt = exec_days[nxt_i]
        if nxt > LABEL_END_CAP:
            continue
        fdate = prev_day.get(ex)
        if fdate not in by_date or ex not in by_date:
            continue
        fi, ei = by_date[fdate], by_date[ex]
        liq = d.at[fi, "_liq"]
        p0 = adj[ei]
        if not (liq == liq) or liq < MIN_TURNOVER or not (p0 > 0):
            continue
        # 持有期終點：nxt 當天收盤；若已下市則用 nxt 以前最後一個收盤（[自行裁量]2）
        j = ei
        for k in range(ei + 1, len(dates)):
            if dates[k] > nxt:
                break
            j = k
        p1 = adj[j]
        if j == ei or not (p1 > 0):
            continue
        r = {"stock_id": sid, "exec_date": ex, "feature_date": fdate, "label_end": dates[j],
             "ret": float(p1 / p0 - 1.0), "turnover_20d": float(liq)}
        for c in FEATURES:
            v = d.at[fi, c]
            r[c] = float(v) if v == v and v is not None and np.isfinite(v) else None
        rows.append(r)
    return rows


def build_panel(until_hhmm: str | None) -> dict:
    import pandas as pd
    import mem_guard  # noqa: F401  與 factor_ic.py 相同的記憶體安全閥
    from finmind_client import load_dev
    from strategies.weinstein_stage2 import prepare_market_data
    from universe import universe as build_universe
    from validation import holdout

    _offline_guard()
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", FACTOR_START)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in paper_8_ml_tracker")
    market_df = prepare_market_data(market_raw)
    calendar = sorted(pd.to_datetime(market_df["date"]).dt.strftime("%Y-%m-%d").tolist())
    prev_day = {calendar[i]: calendar[i - 1] for i in range(1, len(calendar))}
    exec_days = _month_exec_days(calendar)
    ids = sorted({s for s in build_universe()["stock_id"].astype(str) if is_common(s)})
    done = {p.stem for p in PANEL_DIR.glob("*.json")}
    todo = [s for s in ids if s not in done]
    print(f"宇宙普通股 {len(ids)} 檔；已完成 {len(done)}；本次待做 {len(todo)}")
    n_new = 0
    for i, sid in enumerate(todo):
        if until_hhmm and datetime.now(TW).strftime("%H:%M") >= until_hhmm:
            print(f"到 {until_hhmm} 停止；下一批從 {sid} 開始")
            break
        try:
            rows = _stock_rows(sid, market_df, exec_days, prev_day)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i+1}/{len(todo)}] {sid}: 失敗 {type(e).__name__}: {str(e)[:120]}（記為空、可刪檔重算）")
            rows, err = [], f"{type(e).__name__}: {str(e)[:200]}"
        else:
            err = None
        (PANEL_DIR / f"{sid}.json").write_text(json.dumps({"rows": rows, "error": err}, ensure_ascii=False), encoding="utf-8")
        n_new += 1
        if (i + 1) % 50 == 0:
            print(f"  進度 {i+1}/{len(todo)}（{datetime.now(TW).strftime('%H:%M:%S')}）")
    done = {p.stem for p in PANEL_DIR.glob("*.json")}
    return {"universe_n": len(ids), "done_n": len(done), "new_n": n_new, "remaining_n": len([s for s in ids if s not in done])}


# ───────────────────────────── 訓練（只一次） ─────────────────────────────

def train() -> dict:
    import joblib
    import numpy as np
    import pandas as pd
    import sklearn
    from sklearn.ensemble import HistGradientBoostingRegressor

    if MODEL_PATH.exists():
        raise RuntimeError(f"模型已存在（{MODEL_PATH.name}），PREREG 規定只訓練一次、不得重訓；拒絕執行")
    rows = []
    errs = 0
    for p in sorted(PANEL_DIR.glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        errs += bool(doc.get("error"))
        rows.extend(doc.get("rows") or [])
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("訓練面板是空的，先跑 build-panel")
    assert df["label_end"].max() <= LABEL_END_CAP, "標籤讀到 2024-12-31 以後的報酬"
    df["label"] = df.groupby("exec_date")["ret"].rank(pct=True)
    cov = {c: float(df[c].notna().mean()) for c in FEATURES}
    used = [c for c in FEATURES if cov[c] >= MIN_COVERAGE]
    dropped = [c for c in FEATURES if cov[c] < MIN_COVERAGE]
    X = df[used].astype(float).to_numpy()
    y = df["label"].to_numpy(dtype=float)
    model = HistGradientBoostingRegressor(random_state=RANDOM_STATE)
    model.fit(X, y)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    meta = {
        "prereg": "docs/PREREG_paper_h_ml_forward.md", "trial_id": 459,
        "trained_at": datetime.now(TW).isoformat(timespec="seconds"),
        "model": "sklearn.ensemble.HistGradientBoostingRegressor（全部預設參數）", "random_state": RANDOM_STATE,
        "sklearn_version": sklearn.__version__, "model_file": MODEL_PATH.name, "model_sha256": _sha256(MODEL_PATH),
        "train_months": [TRAIN_FIRST_MONTH, TRAIN_LAST_MONTH], "label_end_max": str(df["label_end"].max()),
        "n_rows": int(len(df)), "n_stocks": int(df["stock_id"].nunique()), "n_months": int(df["exec_date"].nunique()),
        "n_panel_errors": int(errs), "min_coverage": MIN_COVERAGE,
        "coverage": {c: round(cov[c], 4) for c in FEATURES},
        "features_used": used, "features_dropped_low_coverage": dropped,
        "n_iter": int(getattr(model, "n_iter_", 0)),
        "frozen_note": "2026-11-30 前 commit；之後不得重訓或更換（PREREG）",
    }
    FEATURES_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {k: meta[k] for k in ("model_sha256", "n_rows", "n_stocks", "n_months", "features_used", "features_dropped_low_coverage")}


# ───────────────────────────── 前向特徵（repo 既有資料） ─────────────────────────────

PRICE_FEATURES = ("f_low_vol", "f_idio_vol", "f_bab", "f_short_reversal_1m", "f_short_term_reversal_1w",
                  "f_amihud_illiq", "f_52w_high_prox", "f_residual_momentum", "f_rel_strength", "f_ma_breakout")


def price_features(px, mkt_close: dict):
    """前向價量 10 個特徵，照 research/factors.py prepare_factors 同一公式與同一組窗口常數。

    px：DataFrame（date 遞增，欄位 adj_close／Trading_Volume／Trading_money）；mkt_close：{date: 加權指數收盤}。
    回傳加上 10 個特徵欄的 DataFrame。窗口不足的列為 NaN（repo 價格檔只留約 90 個交易日，
    252 日類 f_52w_high_prox／f_residual_momentum 前向一律 NaN，照 PREREG「算不出來留 NaN」）。
    與 prepare_factors 的一致性由 scripts/selftest_paper_8_features.py 在歷史資料上核對。
    """
    import numpy as np
    import pandas as pd
    import factors as F

    d = px.sort_values("date").reset_index(drop=True).copy()
    d["mkt_close"] = d["date"].map(mkt_close)
    ret60 = d["adj_close"] / d["adj_close"].shift(F.REL_STRENGTH_WINDOW) - 1
    mkt_ret60 = d["mkt_close"] / d["mkt_close"].shift(F.REL_STRENGTH_WINDOW) - 1
    d["f_rel_strength"] = ret60 - mkt_ret60
    ma60 = d["adj_close"].rolling(F.MA_WINDOW, min_periods=F.MA_WINDOW).mean()
    vol20 = d["Trading_Volume"].rolling(F.VOL_SHORT_WINDOW, min_periods=F.VOL_SHORT_WINDOW).mean()
    vol60 = d["Trading_Volume"].rolling(F.VOL_LONG_WINDOW, min_periods=F.VOL_LONG_WINDOW).mean()
    d["f_ma_breakout"] = (d["adj_close"] / ma60 - 1) * (vol20 / vol60)
    daily_ret = d["adj_close"].pct_change()
    d["f_low_vol"] = -daily_ret.rolling(F.LOW_VOL_WINDOW, min_periods=F.LOW_VOL_WINDOW).std()
    d["f_short_reversal_1m"] = -(d["adj_close"] / d["adj_close"].shift(F.SHORT_REVERSAL_WINDOW) - 1)
    illiq = np.where(d["Trading_money"] > 0, daily_ret.abs() / d["Trading_money"], np.nan)
    d["f_amihud_illiq"] = pd.Series(illiq, index=d.index).rolling(F.AMIHUD_WINDOW, min_periods=F.AMIHUD_WINDOW).mean()
    mkt_ret = d["mkt_close"].pct_change()
    w = F.LOW_VOL_WINDOW
    var_s = daily_ret.rolling(w, min_periods=w).var()
    var_m = mkt_ret.rolling(w, min_periods=w).var()
    beta_60 = daily_ret.rolling(w, min_periods=w).cov(mkt_ret) / var_m
    d["f_idio_vol"] = -np.sqrt((var_s - beta_60 ** 2 * var_m).clip(lower=0.0))
    d["f_bab"] = -beta_60
    w2 = F.RESIDUAL_MOMENTUM_WINDOW
    ret_252 = d["adj_close"] / d["adj_close"].shift(w2) - 1
    mkt_ret_252 = d["mkt_close"] / d["mkt_close"].shift(w2) - 1
    beta_252 = daily_ret.rolling(w2, min_periods=w2).cov(mkt_ret) / mkt_ret.rolling(w2, min_periods=w2).var()
    d["f_residual_momentum"] = ret_252 - beta_252 * mkt_ret_252
    d["f_52w_high_prox"] = d["adj_close"] / d["adj_close"].rolling(F.HIGH_52W_WINDOW, min_periods=F.HIGH_52W_WINDOW).max()
    d["f_short_term_reversal_1w"] = -(d["adj_close"] / d["adj_close"].shift(F.SHORT_TERM_REVERSAL_1W_WINDOW) - 1)
    return d


TAIEX_STORE = RESEARCH / "data" / "paper_8_taiex_closes.json"
REVENUE_FEATURES = ("f_rev_accel", "f_revenue_surprise")


def update_taiex_store() -> dict:
    """[自行裁量]6：前向的大盤序列。repo 沒有持續更新的加權指數日收盤檔（price_history_index_legacy 停在 09-24），
    market_tw.json 每班有官方 FMTQIK 近 60 日收盤（零額外請求），但 60 日窗口要 61 點；
    所以每班把它併進本檔累積（同日以新值覆蓋），一天後就夠長。"""
    store = {}
    try:
        store = json.loads(TAIEX_STORE.read_text(encoding="utf-8")).get("closes") or {}
    except (OSError, ValueError):
        pass
    try:
        t = json.loads((ROOT / "data" / "market_tw.json").read_text(encoding="utf-8")).get("taiex") or {}
        for dt, v in zip(t.get("sparkline_60d_dates") or [], t.get("sparkline_60d") or []):
            if dt and v:
                store[str(dt)] = float(v)
    except (OSError, ValueError) as e:
        print(f"[warn] 模擬 H：market_tw.json 讀不到加權指數，沿用既有累積：{e}")
    TAIEX_STORE.parent.mkdir(parents=True, exist_ok=True)
    TAIEX_STORE.write_text(json.dumps({"source": "data/market_tw.json taiex.sparkline_60d（TWSE FMTQIK）逐班累積",
                                       "closes": dict(sorted(store.items()))}, ensure_ascii=False), encoding="utf-8")
    return store


def _revenue_frame(entry: dict):
    """data/fundamentals.json 月營收 → 與 pit.month_revenue_pit 同欄位的表（pit_date＝次月 10 日，官方檔沒有 create_time）。"""
    import pandas as pd
    from pit import _next_month_10th
    rows = {}
    for key in ("revenue_history_scoring", "month_revenue"):  # 後者較新、同年月覆蓋（同模擬 G）
        for r in entry.get(key) or []:
            if r.get("revenue") is not None and r.get("year") and r.get("month"):
                rows[(int(r["year"]), int(r["month"]))] = float(r["revenue"])
    return pd.DataFrame([{"revenue_year": y, "revenue_month": m, "revenue": v, "pit_date": _next_month_10th(y, m)}
                         for (y, m), v in sorted(rows.items())])


def revenue_features(entry: dict, fdate: str) -> dict:
    """f_rev_accel／f_revenue_surprise：直接呼叫 factors 的同一支函式（把資料來源換成 repo 官方累積月營收）。"""
    import pandas as pd
    import factors as F
    rev = _revenue_frame(entry)
    if rev.empty:
        return {c: None for c in REVENUE_FEATURES}
    orig = F.month_revenue_pit
    F.month_revenue_pit = lambda *_a, **_k: rev.copy()
    try:
        acc = F._revenue_yoy_acceleration("", "")
        sue = F._revenue_surprise_sue("", "")
    finally:
        F.month_revenue_pit = orig
    base = pd.DataFrame({"date": [fdate]})
    out = {}
    for c, pit_df, col in (("f_rev_accel", acc, "yoy_accel"), ("f_revenue_surprise", sue, "revenue_sue")):
        v = F._asof_join(base.copy(), pit_df, col, c)[c].iloc[0]
        out[c] = float(v) if v == v and v is not None else None
    return out


def forward_features(day: str, prices: dict, funds: dict, active: set, mkt: dict) -> tuple[list, dict]:
    """執行日 day 的宇宙與特徵（用 day 前一個交易日收盤以前的資料）。回傳 (rows, coverage)。"""
    import numpy as np
    import pandas as pd
    out = []
    for code in sorted(active):
        rs = prices.get(code) or []
        if not is_common(code) or not rs:
            continue
        on_day = [r for r in rs if r["date"] == day and (r.get("adj_close") or r.get("close"))]
        hist = [r for r in rs if r["date"] < day]
        if not on_day or len(hist) < LIQ_DAYS:
            continue
        fdate = hist[-1]["date"]
        tv = [r.get("turnover") for r in hist[-LIQ_DAYS:]]
        if any(v is None for v in tv) or sum(tv) / LIQ_DAYS < MIN_TURNOVER:
            continue
        px = pd.DataFrame({"date": [r["date"] for r in hist],
                           "adj_close": [r.get("adj_close") if r.get("adj_close") is not None else r.get("close") for r in hist],
                           "Trading_Volume": [r.get("volume") for r in hist],
                           "Trading_money": [r.get("turnover") for r in hist]})
        for c in ("adj_close", "Trading_Volume", "Trading_money"):
            px[c] = pd.to_numeric(px[c], errors="coerce")
        last = price_features(px, mkt).iloc[-1]
        row = {"code": code, "feature_date": fdate, "turnover_20d": round(sum(tv) / LIQ_DAYS)}
        for c in FEATURES:
            v = last.get(c) if c in PRICE_FEATURES else None
            row[c] = float(v) if v is not None and v == v and np.isfinite(v) else None
        row.update(revenue_features(funds.get(code) or {}, fdate))
        out.append(row)
    cov = {c: round(sum(r[c] is not None for r in out) / len(out), 4) if out else 0.0 for c in FEATURES}
    return out, cov


def predict_ranking(rows: list, meta: dict) -> list:
    import joblib
    import numpy as np
    if _sha256(MODEL_PATH) != meta.get("model_sha256"):
        raise RuntimeError("模型檔雜湊與 features.json 不符（模型被換過），拒絕預測")
    model = joblib.load(MODEL_PATH)
    used = meta["features_used"]
    X = np.array([[np.nan if r.get(c) is None else r[c] for c in used] for r in rows], dtype=float)
    pred = model.predict(X)
    rk = [{"code": r["code"], "score": round(float(p), 6), "turnover_20d": r["turnover_20d"]} for r, p in zip(rows, pred)]
    rk.sort(key=lambda r: (-r["score"], r["code"]))
    for i, r in enumerate(rk, 1):
        r["rank"] = i
    return rk


def rebalance_from_ranking(rk: list, px, day: str, prev: dict | None) -> dict:
    """等權再平衡（沿用模擬 G 已驗證的解法：先賣後買、扣成本後解等權目標；成本 engine.py 1×）。"""
    import paper_7_revsurprise_tracker as G
    by = {r["code"]: r for r in rk}
    held = G.current_values(px, prev, day) if prev else {}
    nav_pre = sum(held.values()) if prev else INITIAL
    keep = [c for c in held if c in by and by[c]["rank"] <= EXIT_RANK]
    exits = [c for c in held if c not in keep]
    new = keep[:]
    for r in rk:
        if len(new) >= TOP_N:
            break
        if r["code"] not in new:
            new.append(r["code"])
    if not new:
        raise RuntimeError(f"{day} 合格宇宙是空的，不建倉")
    sells = {c: max(0.0, held.get(c, 0.0) - (0.0 if c not in new else nav_pre / len(new))) for c in held}
    cash = nav_pre - sum(held.values()) + sum(v * (1 - G.SELL) for v in sells.values())
    remain = {c: held.get(c, 0.0) - sells.get(c, 0.0) for c in new}
    lo, hi = 0.0, (sum(remain.values()) + cash) / len(new)
    for _ in range(60):
        t = (lo + hi) / 2
        need = sum(max(0.0, t - remain[c]) * (1 + G.BUY) for c in new) - sum(max(0.0, remain[c] - t) for c in new)
        lo, hi = (t, hi) if need <= cash else (lo, t)
    t = lo
    values_post = {c: round(t, 2) for c in new}
    bought = sum(max(0.0, t - remain[c]) for c in new)
    return {"date": day, "event": "inception" if not prev else "rebalance", "values_post": values_post,
            "nav_pre": round(nav_pre, 2), "nav": round(sum(values_post.values()), 2),
            "rebalance_cost": round(sum(sells.values()) * G.SELL + bought * G.BUY, 2),
            "turnover_pct": round((sum(sells.values()) + bought) / nav_pre * 100, 2) if nav_pre else None,
            "entered": [c for c in new if c not in held], "exited": exits, "kept": keep,
            "picks": [by[c] for c in new], "universe_n": len(rk), "costs": {"buy": G.BUY, "sell": G.SELL}}


# ───────────────────────────── 前向（排程） ─────────────────────────────

def read_log() -> list:
    try:
        return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def write_summary(extra: dict | None = None) -> None:
    meta = {}
    try:
        meta = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    log = read_log()
    doc = {"label": LABEL, "note": NOTE, "start_not_before": START_NOT_BEFORE, "started": bool(log),
           "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "model_frozen": bool(meta.get("model_sha256")), "model_sha256": meta.get("model_sha256"),
           "features_used_n": len(meta.get("features_used") or []) or None,
           "judge": "滿 24 個月（24 次再平衡）判一次：扣 1× 成本年化 > 同期 0050 含息（第 8 關）、期間回撤 ≤50%（天條一）",
           "known_limit": "訓練期 2013～2024 的特徵都被既有因子試驗看過；只有 24 次再平衡，檢定力弱",
           "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。", **(extra or {})}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _append(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _forward_inputs():
    import paper_7_revsurprise_tracker as G
    import price_history_store as PHS
    prices = PHS.load(ROOT / "data" / "price_history.json").get("prices") or {}
    funds = (G._load(ROOT / "data" / "fundamentals.json", {}) or {}).get("fundamentals") or {}
    active = set((G._load(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    return G.Px(prices), prices, funds, active


def dry_run() -> dict:
    """只算最新交易日的宇宙與特徵覆蓋率（不預測、不寫帳本），供上線前核對。"""
    px, prices, funds, active = _forward_inputs()
    mkt = update_taiex_store()
    import paper_7_revsurprise_tracker as G
    day = G.latest_date(px)
    rows, cov = forward_features(day, prices, funds, active, mkt)
    return {"day": day, "universe_n": len(rows), "taiex_days": len(mkt), "coverage": cov}


def step() -> dict:
    import paper_7_revsurprise_tracker as G
    mkt = update_taiex_store()
    today = datetime.now(TW).strftime("%Y-%m-%d")
    log = read_log()
    if today < START_NOT_BEFORE:
        write_summary({"why_not_started": "12/01 起第一個有收盤資料的執行日初次建倉、之後每月再平衡，不倒填"})
        return {"state": "NOT_STARTED", "today": today, "taiex_days": len(mkt)}
    try:
        meta = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    if not meta.get("model_sha256") or not MODEL_PATH.exists():
        write_summary({"why_not_started": "凍結模型不存在（先.一二七-B2 尚未完成訓練），不建倉"})
        return {"state": "NO_MODEL", "today": today}
    px, prices, funds, active = _forward_inputs()
    day = G.latest_date(px)
    if not day or day < START_NOT_BEFORE or any(e["date"][:7] == day[:7] for e in log) or (log and day <= log[-1]["date"]):
        write_summary(_holdings_extra(px, log))
        return {"state": "HOLD", "day": day}
    rows, cov = forward_features(day, prices, funds, active, mkt)
    rk = predict_ranking(rows, meta)
    ev = rebalance_from_ranking(rk, px, day, log[-1] if log else None)
    ev["feature_coverage"] = cov
    ev["model_sha256"] = meta["model_sha256"]
    ev["picks"] = ev["picks"][:TOP_N]
    _append(ev)
    log = read_log()
    write_summary(_holdings_extra(px, log))
    return {"state": ev["event"].upper(), "day": day, "n": len(ev["values_post"]), "universe_n": ev["universe_n"]}


def _holdings_extra(px, log: list) -> dict:
    if not log:
        return {}
    import paper_7_revsurprise_tracker as G
    ev = log[-1]
    day = G.latest_date(px) or ev["date"]
    vals = G.current_values(px, ev, day)
    nav = sum(vals.values())
    picks = {p["code"]: p for p in ev.get("picks") or []}
    return {"as_of_date": day, "nav": round(nav, 2), "initial_virtual_capital": INITIAL,
            "total_return_pct": round((nav / INITIAL - 1) * 100, 2), "last_rebalance": ev["date"], "n_rebalances": len(log),
            "holdings": sorted([{"code": c, "weight_pct": round(v / nav * 100, 2) if nav else None,
                                 "rank_at_rebalance": (picks.get(c) or {}).get("rank")} for c, v in vals.items()],
                               key=lambda h: (h["rank_at_rebalance"] or 9999)),
            "last_entered": ev.get("entered") or [], "last_exited": ev.get("exited") or [],
            "last_feature_coverage": ev.get("feature_coverage")}


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["build-panel"]:
            until = argv[argv.index("--until") + 1] if "--until" in argv else None
            print(json.dumps(build_panel(until), ensure_ascii=False))
        elif argv[:1] == ["train"]:
            print(json.dumps(train(), ensure_ascii=False))
        elif argv[:1] == ["dry-run"]:
            print(json.dumps(dry_run(), ensure_ascii=False))
        else:
            print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] 模擬 H 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
