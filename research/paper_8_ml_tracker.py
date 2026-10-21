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
  python research/paper_8_ml_tracker.py                                排程用（market.yml）：每月預測＋帳本＋App 摘要

[自行裁量]（PREREG 沒寫到、照實記錄，總司令可推翻）：
1. 訓練宇宙＝research/universe.py universe()（含已下市）裡的普通股（4 碼、非 0 開頭、排除 91 開頭），
   當月執行日有收盤價、特徵日近 20 日平均成交值 ≥3,000 萬（與前向宇宙同一門檻）。
2. 已下市股：持有期內下市者，標籤用持有期終點以前最後一個收盤價（下市以最後成交價出場，同草稿第 3 節）。
3. 三大法人類（f_foreign_streak／f_inst_flow／f_inst_streak_days）在 prepare_factors 裡把缺資料補 0，
   會讓「沒資料」看起來像「有值」；本程式在該日沒有任何法人原始列時改回 NaN，覆蓋率才算得對。
4. 訓練特徵一律離線計算：只讀本機快取，任何網路連線都被擋下（快取缺的資料集視為缺值，不打 FinMind）。
5. 例外：TaiwanStockSplitPrice 缺快取視為「無分割事件」（本機快取抽樣 99% 是空表），其餘資料集缺快取該檔失敗、照實記錄。
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


def step() -> dict:
    today = datetime.now(TW).strftime("%Y-%m-%d")
    if today < START_NOT_BEFORE:
        write_summary({"why_not_started": "12/01 起第一個有收盤資料的執行日初次建倉、之後每月再平衡，不倒填"})
        return {"state": "NOT_STARTED", "today": today}
    # 前向每月預測（特徵由 repo 既有資料照同一定義計算）尚未實作：先.一二七-B2 續做，2026-11-30 前完成
    write_summary({"why_not_started": "前向預測程式尚未完成（先.一二七-B2 續做中），不建倉"})
    return {"state": "NOT_IMPLEMENTED", "today": today}


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["build-panel"]:
            until = argv[argv.index("--until") + 1] if "--until" in argv else None
            print(json.dumps(build_panel(until), ensure_ascii=False))
        elif argv[:1] == ["train"]:
            print(json.dumps(train(), ensure_ascii=False))
        else:
            print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] 模擬 H 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
