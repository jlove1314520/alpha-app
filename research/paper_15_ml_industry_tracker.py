# -*- coding: utf-8 -*-
"""模擬 O：ML 價量「產業輪動」前向紙上追蹤（先.一三六-B7，照 docs/PREREG_ML_INDUSTRY_ROTATION_FORWARD_FINAL.md）。

規則照 FINAL（§2 乙＋70／30，參數一次定死，不調參、不倒填）：
- 產業指數：自建上市產業指數——同產業成分股以「前一日市值」加權合成日報酬；成分股＝當日在市上市普通股；
  產業代碼＝data/company_info.json 的官方上市產業代碼（twse_t187ap03_L，名稱對照 research/data/official_industry_code_map.json），
  **非時點分類**（照 FINAL §5-1 揭露）；當日有報酬與市值的成分股 <5 檔 → 該產業當日不成立（NaN）。
- 特徵：8 個前向可得價量特徵，在產業指數序列上用模擬 H 的 price_features()（與 factors.py 同公式）重算：
  f_low_vol、f_short_reversal_1m、f_short_term_reversal_1w、f_amihud_illiq、f_ma_breakout、f_idio_vol、f_bab、f_rel_strength。
- 模型：HistGradientBoostingRegressor 全部預設參數、random_state=20261021；訓練一次（2013-01～2024-11、標籤終點 ≤2024-12-31），凍結。
- 標籤：下月產業報酬（當月第一個交易日收盤 → 次月第一個交易日收盤）的當月橫斷面百分位。

子命令：
  python research/paper_15_ml_industry_tracker.py build-panel [--until HH:MM]  逐檔日資料快取（可續跑；本機、不進 repo）
  python research/paper_15_ml_industry_tracker.py train                         合成產業指數＋特徵＋訓練一次（模型已存在就拒絕）
  python research/paper_15_ml_industry_tracker.py                               排程用（2027-01-04 前 NOT_STARTED）

[自行裁量]（FINAL 沒寫到、照實記錄，Cowork／總司令可推翻）：
1. 歷史「前一日市值」＝前一交易日原始收盤 × 發行股數；發行股數＝FinMind 快取 TaiwanStockBalanceSheet 的
   OrdinaryShare（普通股股本，缺則 CapitalStock）÷ 面額 10 元（2330 實核 2,593.27 億元 → 259.3 億股，與官方相符）。
   PIT：季報只在法定公告期限後才可用（Q1～Q3 季末 +45 天、年報 +90 天），之前沿用上一期。
   FinMind TaiwanStockMarketValue 是付費資料，不用；TaiwanStockShareholding 本機無快取（要 ~1,000 次請求），不抓。
   前向改用 data/foreign_holding.json 的 shares_issued（TWSE 外資持股表發行股數，每日管線既有、零額外請求），
   兩邊都是「發行股數」同一個量、來源不同，照實揭露。非 10 元面額公司（少數）股數會偏，影響只在產業內權重。
2. 訓練成分股只含「今天官方上市產業代碼裡有的代號」；已下市的上市股沒有官方代碼 → 不納入產業指數
   （訓練期產業報酬有存活者偏誤，只影響模型學到的關係；判定只看 2027-01 以後前向報酬，照實揭露）。
3. f_ma_breakout 公式裡的「成交量」用產業合計成交金額代替（不同股價的股數相加沒有意義）；f_amihud_illiq 照 FINAL 用合計成交金額。
4. 產業指數合成只用「當日與前一日都有還原收盤、且前一日市值可得」的成分股；整段離線，只讀本機快取。
5. 股數嚴格 PIT、不回填：FinMind 季報快取最早 2012Q4（2013-03-31 才可用），2013-03-31 以前產業指數不成立，
   訓練實際從特徵窗口湊滿的月份起算（約 2013 年中），照實寫進 features.json 的 n_months。
6. 「前 1/4 產業」＝產業數 × 0.25 四捨五入、至少 1（FINAL 寫「產業約 20～28 個 → 5～7 個」，與此一致）。
8. 約 250 檔沒有 2010 起的價格快取鍵（模擬 H 面板同樣缺）→ 還原價改用 2012 起的快取鍵（面板只用 2012-06 以後的日報酬）。
7. 前向組合用共用框架新增的 mode="weighted"（目標權重；不在目標的持股全數出場、續抱保留原進場日），
   既有 monthly／event 路徑不變（scripts/selftest_paper_13_18.py 照跑全過）。
自身失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import bisect
import glob
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
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
MODEL_DIR = RESEARCH / "paper_15_model"
MODEL_PATH = MODEL_DIR / "model.joblib"
META_PATH = MODEL_DIR / "features.json"
PANEL_DIR = RESEARCH / "data" / "paper_15_stock_daily"   # research/data/ 已 gitignore：FinMind 衍生資料不進公開 repo
LOG = RESEARCH / "data" / "paper_15_log.jsonl"
OUT = ROOT / "data" / "paper_15.json"
PREREG = "docs/PREREG_ML_INDUSTRY_ROTATION_FORWARD_FINAL.md"
TRIAL_NO = 486  # register_trial() #486（2026-10-27 互動視窗 先.一三七-1 登記）

RANDOM_STATE = 20261021
TRAIN_FIRST_MONTH, TRAIN_LAST_MONTH = "2013-01", "2024-11"
LABEL_END_CAP = "2024-12-31"
FACTOR_START = "2010-01-01"      # 與模擬 H 同一組快取鍵
PANEL_FROM = "2012-06-01"        # 2013-01 第一個特徵要回看 61 個交易日
MIN_MEMBERS = 5
TOP_FRAC = 0.25
INVEST_FRAC = 0.70
PAR_VALUE = 10.0
START = "2027-01-04"
JUDGE = "2029-01-02"
FEATURES = ("f_low_vol", "f_short_reversal_1m", "f_short_term_reversal_1w", "f_amihud_illiq",
            "f_ma_breakout", "f_idio_vol", "f_bab", "f_rel_strength")
assert len(FEATURES) == 8


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def listed_industry() -> dict:
    """{代號: 官方上市產業代碼}，只取 4 碼普通股。"""
    from paper_8_ml_tracker import is_common
    doc = json.loads((ROOT / "data" / "company_info.json").read_text(encoding="utf-8"))
    out = {}
    for sid, v in (doc.get("companies") or {}).items():
        if v.get("industry_source") == "twse_t187ap03_L" and v.get("industry_code") and is_common(sid):
            out[sid] = str(v["industry_code"])
    return out


# ───────────────────────────── 發行股數（PIT） ─────────────────────────────

def _avail_date(qend: str) -> str:
    d = date.fromisoformat(qend)
    lag = 90 if d.month == 12 else 45
    return (d + timedelta(days=lag)).isoformat()


def shares_schedule(sid: str) -> list[tuple[str, float]]:
    """[(可用日, 股數)] 依可用日遞增；只讀本機 FinMind 快取檔（多個起訖鍵合併），季末 ≤ 2024-12-31。"""
    import pandas as pd
    import finmind_client as fc
    files = glob.glob(str(fc.DATA_DIR / f"TaiwanStockBalanceSheet__{sid}__*.parquet"))
    if not files:
        return []
    df = pd.concat([pd.read_parquet(f, columns=["date", "type", "value"]) for f in files], ignore_index=True)
    df["date"] = df["date"].astype(str).str[:10]
    df = df[df["date"] <= LABEL_END_CAP]
    by = {}
    for t in ("CapitalStock", "OrdinaryShare"):   # OrdinaryShare 後寫，優先
        for dt, v in df[df["type"] == t][["date", "value"]].itertuples(index=False):
            if v and v > 0:
                by[dt] = float(v) / PAR_VALUE
    return sorted((_avail_date(q), s) for q, s in by.items())


def shares_asof(sched: list, d: str):
    i = bisect.bisect_right([a for a, _ in sched], d) - 1
    return sched[i][1] if i >= 0 else None


# ───────────────────────────── 訓練面板（逐檔，離線） ─────────────────────────────

def raw_closes(sid: str) -> dict:
    """原始（未還原）收盤 {date: close}，合併本機所有 TaiwanStockPrice 快取鍵（模擬 H 那組 2010 鍵不是每檔都有），只取 ≤2024-12-31。"""
    import pandas as pd
    import finmind_client as fc
    out = {}
    for f in sorted(glob.glob(str(fc.DATA_DIR / f"TaiwanStockPrice__{sid}__*.parquet"))):
        try:
            df = pd.read_parquet(f, columns=["date", "close"])
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {sid} 讀快取 {Path(f).name} 失敗：{e}")
            continue
        for d, c in zip(df["date"].astype(str).str[:10], df["close"].astype(float)):
            if d <= LABEL_END_CAP and c > 0:
                out[d] = c
    return out


def stock_daily(sid: str) -> dict:
    """{d, r, mc, tm}：日期、還原日報酬、前一日市值（原始收盤×股數）、成交金額；PANEL_FROM～2024-12-31。"""
    from adjust import adjusted_price_series
    try:
        px = adjusted_price_series(sid, FACTOR_START)
    except RuntimeError as e:
        # [自行裁量]8：約 250 檔沒有 2010 起的價格快取鍵（模擬 H 面板同樣缺），改用 2012 起的鍵；
        # 面板只取 2012-06 以後的日報酬，還原日報酬與序列起算日無關。
        if "本機無快取" not in str(e):
            raise
        px = adjusted_price_series(sid, "2012-01-01")
    rc = raw_closes(sid)
    if px is None or px.empty or not rc:
        return {"d": [], "r": [], "mc": [], "tm": []}
    sched = shares_schedule(sid)
    px = px.sort_values("date")
    ds = px["date"].astype(str).str[:10].tolist()
    adj = px["adj_close"].astype(float).tolist()
    tm = px["Trading_money"].astype(float).tolist()
    out = {"d": [], "r": [], "mc": [], "tm": []}
    for i in range(1, len(ds)):
        d, dp = ds[i], ds[i - 1]
        if d < PANEL_FROM or d > LABEL_END_CAP:
            continue
        r = adj[i] / adj[i - 1] - 1 if adj[i - 1] and adj[i - 1] > 0 and adj[i] == adj[i] else None
        sh = shares_asof(sched, dp)
        c0 = rc.get(dp)
        mc = c0 * sh if (sh and c0 and c0 > 0) else None
        out["d"].append(d)
        out["r"].append(round(r, 8) if r is not None else None)
        out["mc"].append(round(mc) if mc is not None else None)
        out["tm"].append(tm[i] if tm[i] == tm[i] else None)
    return out


def build_panel(until_hhmm: str | None) -> dict:
    import paper_8_ml_tracker as H
    H._offline_guard()
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    ids = sorted(listed_industry())
    done = {p.stem for p in PANEL_DIR.glob("*.json")}
    todo = [s for s in ids if s not in done]
    print(f"上市普通股（有官方產業代碼）{len(ids)} 檔；已完成 {len(done)}；本次待做 {len(todo)}")
    n_new = 0
    for i, sid in enumerate(todo):
        if until_hhmm and datetime.now(TW).strftime("%H:%M") >= until_hhmm:
            print(f"到 {until_hhmm} 停止；下一批從 {sid} 開始")
            break
        try:
            doc, err = stock_daily(sid), None
        except Exception as e:  # noqa: BLE001
            doc, err = {"d": [], "r": [], "mc": [], "tm": []}, f"{type(e).__name__}: {str(e)[:200]}"
            print(f"  {sid}: 失敗 {err[:120]}（記為空、可刪檔重算）")
        doc["error"] = err
        (PANEL_DIR / f"{sid}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        n_new += 1
        if (i + 1) % 50 == 0:
            print(f"  進度 {i+1}/{len(todo)}（{datetime.now(TW).strftime('%H:%M:%S')}）")
    done = {p.stem for p in PANEL_DIR.glob("*.json")}
    return {"universe_n": len(ids), "done_n": len(done), "new_n": n_new, "remaining_n": len([s for s in ids if s not in done])}


# ───────────────────────────── 產業指數與特徵（訓練、前向共用） ─────────────────────────────

def industry_index(members: dict) -> dict:
    """members：{產業: {代號: {date: (r, mc_prev, tm)}}} → {產業: {"d": [...], "lvl": [...], "tm": [...], "n": [...]}}。
    每日報酬＝Σ mc_prev·r / Σ mc_prev（只用 r 與 mc_prev 都有的成分股）；有效成分股 <MIN_MEMBERS → 當日報酬 None
    （指數水準在 None 那天中斷：之後重新從 1 起算，price_features 的窗口會自然跨不過缺口——見 to_frame）。"""
    out = {}
    for ind, stocks in members.items():
        days = sorted({d for s in stocks.values() for d in s})
        lvl, tms, ns, rets = [], [], [], []
        for d in days:
            num = den = tsum = 0.0
            n = 0
            for s in stocks.values():
                v = s.get(d)
                if not v:
                    continue
                r, mc, tm = v
                if tm is not None:
                    tsum += tm
                if r is None or mc is None or mc <= 0:
                    continue
                num += mc * r
                den += mc
                n += 1
            rets.append(num / den if n >= MIN_MEMBERS and den > 0 else None)
            tms.append(tsum)
            ns.append(n)
        out[ind] = {"d": days, "r": rets, "tm": tms, "n": ns}
    return out


def to_frame(series: dict):
    """產業序列 → price_features 吃的 DataFrame（adj_close＝累積水準；報酬 None 的日子水準設 NaN，窗口跨缺口即 NaN）。"""
    import numpy as np
    import pandas as pd
    lvl, cur = [], 1.0
    for r in series["r"]:
        if r is None:
            lvl.append(np.nan)
            cur = 1.0
        else:
            cur *= 1.0 + r
            lvl.append(cur)
    tm = [t if t and t > 0 else np.nan for t in series["tm"]]
    return pd.DataFrame({"date": series["d"], "adj_close": lvl, "Trading_Volume": tm, "Trading_money": tm})


def industry_features(series: dict, mkt_close: dict):
    import paper_8_ml_tracker as H
    return H.price_features(to_frame(series), mkt_close)


def _members_from_panel(ind_of: dict) -> tuple[dict, int]:
    members, errs = {}, 0
    for p in sorted(PANEL_DIR.glob("*.json")):
        sid = p.stem
        if sid not in ind_of:
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        errs += bool(doc.get("error"))
        m = {d: (r, mc, tm) for d, r, mc, tm in zip(doc["d"], doc["r"], doc["mc"], doc["tm"])}
        if m:
            members.setdefault(ind_of[sid], {})[sid] = m
    return members, errs


def training_rows(members: dict, mkt_close: dict, calendar: list) -> list:
    import numpy as np
    from paper_8_ml_tracker import _month_exec_days
    exec_days = _month_exec_days(calendar)
    prev_day = {calendar[i]: calendar[i - 1] for i in range(1, len(calendar))}
    idx = industry_index(members)
    rows = []
    for ind, s in idx.items():
        f = industry_features(s, mkt_close)
        by = {d: i for i, d in enumerate(f["date"])}
        lv = f["adj_close"].to_numpy(dtype=float)
        for k, ex in enumerate(exec_days):
            if not (TRAIN_FIRST_MONTH <= ex[:7] <= TRAIN_LAST_MONTH) or k + 1 >= len(exec_days):
                continue
            nxt = exec_days[k + 1]
            fd = prev_day.get(ex)
            if nxt > LABEL_END_CAP or fd not in by or ex not in by or nxt not in by:
                continue
            p0, p1 = lv[by[ex]], lv[by[nxt]]
            # 持有期內任一天不成立（水準 NaN 或重新起算）→ 不算標籤
            seg = lv[by[ex]:by[nxt] + 1]
            if not (np.isfinite(seg).all() and p0 > 0):
                continue
            r = {"industry": ind, "exec_date": ex, "feature_date": fd, "label_end": nxt, "ret": float(p1 / p0 - 1),
                 "members_n": int(s["n"][by[ex]])}
            for c in FEATURES:
                v = f.at[by[fd], c]
                r[c] = float(v) if v == v and np.isfinite(v) else None
            rows.append(r)
    return rows


def train() -> dict:
    import joblib
    import pandas as pd
    import sklearn
    from sklearn.ensemble import HistGradientBoostingRegressor
    import paper_8_ml_tracker as H
    from finmind_client import load_dev
    from validation import holdout

    if MODEL_PATH.exists():
        raise RuntimeError(f"模型已存在（{MODEL_PATH.name}），FINAL 規定只訓練一次、不得重訓；拒絕執行")
    H._offline_guard()
    ind_of = listed_industry()
    members, errs = _members_from_panel(ind_of)
    missing = len([s for s in ind_of if not (PANEL_DIR / f"{s}.json").exists()])
    if missing:
        raise RuntimeError(f"面板還缺 {missing} 檔，先跑完 build-panel 再訓練")
    mraw = load_dev("TaiwanStockPrice", "TAIEX", FACTOR_START)
    holdout.assert_no_holdout_leakage(mraw, context="TAIEX in paper_15_ml_industry_tracker")
    mkt = dict(zip(mraw["date"].astype(str).str[:10], mraw["close"].astype(float)))
    calendar = sorted(mkt)
    df = pd.DataFrame(training_rows(members, mkt, calendar))
    if df.empty:
        raise RuntimeError("訓練列是空的")
    assert df["label_end"].max() <= LABEL_END_CAP, "標籤讀到 2024-12-31 以後的報酬"
    df["label"] = df.groupby("exec_date")["ret"].rank(pct=True)
    X = df[list(FEATURES)].astype(float).to_numpy()
    model = HistGradientBoostingRegressor(random_state=RANDOM_STATE)
    model.fit(X, df["label"].to_numpy(dtype=float))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    meta = {
        "prereg": PREREG, "trial_id": TRIAL_NO, "trained_at": datetime.now(TW).isoformat(timespec="seconds"),
        "model": "sklearn.ensemble.HistGradientBoostingRegressor（全部預設參數）", "random_state": RANDOM_STATE,
        "sklearn_version": sklearn.__version__, "model_file": MODEL_PATH.name, "model_sha256": _sha256(MODEL_PATH),
        "train_months": [TRAIN_FIRST_MONTH, TRAIN_LAST_MONTH], "label_end_max": str(df["label_end"].max()),
        "n_rows": int(len(df)), "n_industries": int(df["industry"].nunique()), "n_months": int(df["exec_date"].nunique()),
        "n_stocks_in_panel": int(sum(len(v) for v in members.values())), "n_panel_errors": int(errs),
        "coverage": {c: round(float(df[c].notna().mean()), 4) for c in FEATURES},
        "features_used": list(FEATURES), "min_members": MIN_MEMBERS,
        "frozen_note": "2026-12-31 前 commit；之後不得重訓或更換（FINAL）",
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {k: meta[k] for k in ("model_sha256", "n_rows", "n_industries", "n_months", "coverage")}


# ───────────────────────────── 前向（2027-01-04 起） ─────────────────────────────

def forward_shares() -> dict:
    """[自行裁量]1：前向發行股數＝data/foreign_holding.json 的 shares_issued（當下快照）。"""
    try:
        doc = json.loads((ROOT / "data" / "foreign_holding.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[warn] 模擬 O：讀不到 foreign_holding.json（{e}），前向市值全部缺")
        return {}
    return {c: float(v["shares_issued"]) for c, v in (doc.get("stocks") or {}).items()
            if isinstance(v, dict) and v.get("shares_issued")}


def forward_members(px, day: str, ind_of: dict, shares: dict, active: set) -> dict:
    """{產業: {代號: {date: (r, mc_prev, tm)}}}，只用 day 以前（不含）的價格日；成分股＝今天在市（active）的上市普通股。"""
    members = {}
    for c, ind in ind_of.items():
        if c not in active or c not in px.idx or not shares.get(c):
            continue
        rows = px.rows[c]
        m = {}
        for i in range(1, len(rows)):
            d, prev = rows[i]["date"], rows[i - 1]
            if d >= day:
                break
            a0, a1 = C_v(prev), C_v(rows[i])
            r = a1 / a0 - 1 if (a0 and a1 and a0 > 0) else None
            rc = prev.get("close")
            mc = float(rc) * shares[c] if rc else None
            tm = rows[i].get("turnover")
            m[d] = (r, mc, float(tm) if tm is not None else None)
        if m:
            members.setdefault(ind, {})[c] = m
    return members


def C_v(r):
    v = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
    return float(v) if v is not None else None


def score_industries(members: dict, mkt: dict, fdate: str, meta: dict) -> list:
    """每個產業在特徵日 fdate 的 8 個特徵 → 凍結模型分數，由高到低。特徵日產業指數不成立（成分股 <5）者不打分。"""
    import joblib
    import numpy as np
    if _sha256(MODEL_PATH) != meta.get("model_sha256"):
        raise RuntimeError("模型檔雜湊與 features.json 不符，拒絕預測")
    model = joblib.load(MODEL_PATH)
    idx = industry_index(members)
    out = []
    for ind, s in idx.items():
        if fdate not in s["d"] or s["r"][s["d"].index(fdate)] is None:
            continue
        f = industry_features(s, mkt)
        row = f[f["date"] == fdate].iloc[0]
        x = [float(row[c]) if row[c] == row[c] else np.nan for c in meta["features_used"]]
        out.append({"industry": ind, "features": {c: (None if v != v else round(v, 6)) for c, v in zip(meta["features_used"], x)},
                    "members_n": int(s["n"][s["d"].index(fdate)])})
    if out:
        pred = model.predict(np.array([[np.nan if r["features"][c] is None else r["features"][c] for c in meta["features_used"]]
                                       for r in out], dtype=float))
        for r, p in zip(out, pred):
            r["score"] = float(p)
    return sorted(out, key=lambda r: (-r["score"], r["industry"]))


def target_weights(ranked: list, px, day: str, ind_of: dict, shares: dict, active: set) -> list:
    """前 1/4 產業（四捨五入、至少 1）等權；產業內依前一日市值（前一交易日原始收盤×股數）；合計 INVEST_FRAC。"""
    k = max(1, int(len(ranked) * TOP_FRAC + 0.5))
    pick = ranked[:k]
    prev = px.prev_trading_day(day)
    out = []
    for r in pick:
        mcs = {}
        for c, ind in ind_of.items():
            if ind != r["industry"] or c not in active or px.close_on(c, day) is None or not shares.get(c):
                continue
            rc = px.raw_close_on(c, prev) if prev else None
            if rc:
                mcs[c] = rc * shares[c]
        tot = sum(mcs.values())
        for c, mc in sorted(mcs.items()):
            out.append({"code": c, "weight": INVEST_FRAC / len(pick) * mc / tot, "industry": r["industry"],
                        "industry_score": round(r["score"], 6)})
    return out


def make_signal():
    def signal(ctx: dict, day: str, uni: dict):
        px = ctx["px"]
        try:
            meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        if not meta.get("model_sha256") or not MODEL_PATH.exists():
            ctx["skip_reason"] = "模擬 O 凍結模型不存在，本月不調倉"
            return None
        fdate = px.prev_trading_day(day)
        members = forward_members(px, day, ctx["ind_of"], ctx["shares"], ctx["active"])
        ranked = score_industries(members, ctx["mkt"], fdate, meta)
        if not ranked:
            ctx["skip_reason"] = "沒有任何產業指數在特徵日成立，本月不調倉"
            return None
        ctx.setdefault("summary_extra", {})["last_industry_ranking"] = [
            {"industry": r["industry"], "score": round(r["score"], 6), "members_n": r["members_n"]} for r in ranked]
        return target_weights(ranked, px, day, ctx["ind_of"], ctx["shares"], ctx["active"]) or None
    return signal


def spec():
    import paper_forward_common as C
    return C.Spec(key="paper_15", label="模擬 O ML 產業輪動",
                  note="每月第一個交易日：凍結模型對自建上市產業指數（前一日市值加權、成分股 ≥5）打分，前 1/4 產業等權、"
                       "產業內市值權重；持股 70%／現金 30%；成本 1×",
                  prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="weighted",
                  top_n=0, min_turnover=None, delist_value="last", signal=make_signal(), log_path=LOG, out_path=OUT,
                  judge_text=("2029-01-02 後判一次：已平倉 <100 筆→INCONCLUSIVE；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                              "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（seed 20270104）；隨機產業對照 > 第 95 百分位（seed 20270105）"),
                  known_limit="產業代碼非時點；訓練期不含已下市股；前向股數用當下快照；與模擬 H 同家族，要證明增額才算獨立發現",
                  extra_summary={"family": "ML 價量（模擬 H）＋產業輪動"})


def step() -> dict:
    """排程用。2027-01-04 前只寫 NOT_STARTED 摘要、不讀模型、不寫帳本、不算報酬。"""
    import paper_forward_common as C
    import paper_13_ml_low_beta_tracker as M
    px = C.load_px()
    active = set((C.load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    sp = spec()
    if (px.latest_date() or "") < START:
        return C.step(sp, {"px": px}, px=px, active=active)
    ctx = {"px": px, "mkt": M.taiex_closes(), "ind_of": listed_industry(), "shares": forward_shares(), "active": active}
    return C.step(sp, ctx, px=px, active=active)


def main(argv: list[str]) -> int:
    try:
        if argv and argv[0] == "build-panel":
            until = argv[argv.index("--until") + 1] if "--until" in argv else None
            print(json.dumps(build_panel(until), ensure_ascii=False))
        elif argv and argv[0] == "train":
            print(json.dumps(train(), ensure_ascii=False))
        else:
            print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001  十二節：自身失敗只印警告
        print(f"[warn] 模擬 O 失敗：{type(e).__name__}: {e}")
        if argv and argv[0] in ("build-panel", "train"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
