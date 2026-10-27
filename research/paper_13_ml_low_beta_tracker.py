# -*- coding: utf-8 -*-
"""模擬 M：模擬 H 模型排名＋低 beta 篩選 前向紙上追蹤（先.一三六-B7）。

規則照 `docs/PREREG_PAPER_M_ML_LOW_BETA_FINAL.md`（§2 甲；候選池 60、持股 30、beta 窗 60 日、續抱 90 名，一次定死）；
組合／帳本／成本在 research/paper_forward_common.py（monthly，每月第一個交易日再平衡），本檔只有訊號函式。
- 宇宙與特徵＝模擬 H `forward_features()`（同一天、同一份特徵）；排名＝模擬 H `predict_ranking()`（凍結模型，雜湊不符拒絕預測）。
- beta：個股對加權指數 60 個交易日日報酬 OLS 斜率，只用執行日前一個交易日收盤以前的資料（PIT）；不滿 60 個報酬 → NaN、不入選（記件數）。
- 目標集合＝模型前 60 名中 beta 最低 30 檔。已持有者：模型前 90 名且 beta ≤ 目標集合最大 beta → 續抱；其餘出場；
  空位由目標集合中未持有者依 beta 由低到高補滿；每次再平衡回到等權、100% 投入。
- 揭露（不判定）：每次再平衡的組合等權 60 日 beta。
資料：data/price_history、data/fundamentals.json、data/institutional_history.json、research/data/paper_8_taiex_closes.json
（模擬 H 每班累積的加權指數收盤，本檔只讀），零額外外部請求。
"""
from __future__ import annotations

import json

import paper_forward_common as C

ROOT = C.ROOT
POOL, TOP_N, BETA_DAYS, KEEP_RANK = 60, 30, 60, 90
MIN_TURNOVER = 30_000_000.0
START = "2027-01-04"
JUDGE = "2029-01-02"
PREREG = "docs/PREREG_PAPER_M_ML_LOW_BETA_FINAL.md"
TRIAL_NO = None  # 待互動視窗 register_trial()（先.一三六-B1 定稿時尚未登記，2026-10-27 查 TRIALS_REGISTRY 最後一筆 #483）
LOG = ROOT / "research" / "data" / "paper_13_log.jsonl"


def taiex_closes() -> dict:
    import paper_8_ml_tracker as H
    try:
        return json.loads(H.TAIEX_STORE.read_text(encoding="utf-8")).get("closes") or {}
    except (OSError, ValueError) as e:
        print(f"[warn] 模擬 M：讀不到加權指數累積檔（{e}），beta 全部 NaN")
        return {}


def beta_of(px: C.Px, code: str, mkt: dict, before: str):
    """前一交易日（含）以前最後 BETA_DAYS+1 個指數日的日報酬，對個股還原收盤日報酬做 OLS 斜率；缺任一天 → None。"""
    days = sorted(d for d in mkt if d < before)[-(BETA_DAYS + 1):]
    if len(days) < BETA_DAYS + 1:
        return None
    s = [px.close_on(code, d) for d in days]
    if any(v is None or v <= 0 for v in s):
        return None
    m = [float(mkt[d]) for d in days]
    rs = [s[i] / s[i - 1] - 1 for i in range(1, len(days))]
    rm = [m[i] / m[i - 1] - 1 for i in range(1, len(days))]
    mx, my = sum(rm) / len(rm), sum(rs) / len(rs)
    var = sum((x - mx) ** 2 for x in rm)
    if var <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(rm, rs)) / var


def select(rk: list, betas: dict, held: set) -> tuple[list, dict]:
    """rk：模型排名（已排序、含 rank）；betas：code→beta 或 None；held：目前持股。
    回傳 (給共用框架的清單, 統計)：清單＝目標集合（beta 由低到高）＋可續抱但不在目標集合的持股；框架 exit_rank 設很大，
    所以「在清單裡」＝可續抱、「不在清單裡」＝出場，補位只從清單前段（目標集合）依序補。"""
    pool = [r for r in rk if r["rank"] <= POOL]
    with_beta = [r for r in pool if betas.get(r["code"]) is not None]
    target = sorted(with_beta, key=lambda r: (betas[r["code"]], r["code"]))[:TOP_N]
    tset = {r["code"] for r in target}
    bmax = max((betas[r["code"]] for r in target), default=None)
    by = {r["code"]: r for r in rk}
    extra = [by[c] for c in sorted(held - tset) if c in by and by[c]["rank"] <= KEEP_RANK
             and betas.get(c) is not None and bmax is not None and betas[c] <= bmax]
    out = [dict(r, beta_60d=round(betas[r["code"]], 4), model_rank=r["rank"], role="target") for r in target]
    out += [dict(r, beta_60d=round(betas[r["code"]], 4), model_rank=r["rank"], role="keep") for r in extra]
    for r in out:
        r.pop("rank", None)
    stats = {"pool_n": len(pool), "pool_beta_nan": len(pool) - len(with_beta), "target_n": len(target),
             "target_max_beta": round(bmax, 4) if bmax is not None else None, "keep_extra_n": len(extra)}
    return out, stats


def make_signal(spec_ref: dict):
    def signal(ctx: dict, day: str, uni: dict):
        import paper_8_ml_tracker as H
        px: C.Px = ctx["px"]
        try:
            meta = json.loads(H.FEATURES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        if not meta.get("model_sha256") or not H.MODEL_PATH.exists():
            ctx["skip_reason"] = "模擬 H 凍結模型不存在，本月不調倉"
            return None
        mkt = ctx.get("mkt") or {}
        rows, cov = H.forward_features(day, px.rows, ctx.get("funds") or {}, ctx.get("active") or set(), mkt)
        if not rows:
            ctx["skip_reason"] = "合格宇宙是空的，本月不調倉"
            return None
        rk = H.predict_ranking(rows, meta)
        prev = px.prev_trading_day(day)
        betas = {r["code"]: beta_of(px, r["code"], mkt, day) for r in rk if r["rank"] <= max(POOL, KEEP_RANK)}
        log = C.read_log(spec_ref["spec"])
        held = set(((log[-1] if log else {}) or {}).get("positions") or {})
        out, stats = select(rk, betas, held)
        if not out:
            ctx["skip_reason"] = "前 60 名全部沒有 60 日 beta（加權指數累積不足？），本月不調倉"
            return None
        tb = [r["beta_60d"] for r in out if r["role"] == "target"]
        stats.update({"beta_asof": prev, "portfolio_target_beta_eq": round(sum(tb) / len(tb), 4) if tb else None,
                      "model_sha256": meta.get("model_sha256"), "feature_coverage": cov})
        ctx.setdefault("rebalance_stats", {})[day] = stats
        return out
    return signal


def spec() -> C.Spec:
    ref = {}
    sp = C.Spec(key="paper_13", label="模擬 M ML 排名＋低 beta",
                note="每月第一個交易日：模擬 H 凍結模型前 60 名中 60 日 beta 最低 30 檔等權、100% 投入；前 90 名且 beta 不高於目標集合者續抱；成本 1×",
                prereg=PREREG, trial_no=TRIAL_NO, start_not_before=START, judge_after=JUDGE, mode="monthly",
                top_n=TOP_N, exit_rank=10 ** 8, min_turnover=MIN_TURNOVER, delist_value="last", signal=None,
                log_path=LOG, out_path=ROOT / "data" / "paper_13.json",
                judge_text=("2029-01-02 後判一次：已平倉 ≥100 筆前提；天條一回撤 ≤50%；扣 1× 年化 > 0050 含息；"
                            "2×／3× 成本年化 >0；隨機時點對照 > 第 95 百分位（1,000 次、seed 20270104）；揭露與模擬 H 同期淨值差"),
                known_limit="前向 24 個月大概率沒有 2008 級空頭，天條一通過不代表 2008 也活得下來；與模擬 H 同家族，只算一個發現",
                extra_summary={"family": "模擬 H（paper_8）同一份凍結模型"})
    ref["spec"] = sp
    sp.signal = make_signal(ref)
    return sp


def step() -> dict:
    import paper_8_ml_tracker as H
    import paper_7_revsurprise_tracker as G
    px = C.load_px()
    active = set((C.load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    sp = spec()
    if (px.latest_date() or "") < START:  # 起跑前不讀模型、不算特徵（省記憶體），只寫 NOT_STARTED 摘要
        return C.step(sp, {"px": px}, px=px, active=active)
    funds = (G._load(ROOT / "data" / "fundamentals.json", {}) or {}).get("fundamentals") or {}
    ctx = {"px": px, "mkt": taiex_closes(), "funds": funds, "active": active}
    r = C.step(sp, ctx, px=px, active=active)
    if ctx.get("rebalance_stats"):
        r["rebalance_stats"] = {d: {k: v for k, v in s.items() if k != "feature_coverage"} for d, s in ctx["rebalance_stats"].items()}
    return r


if __name__ == "__main__":
    raise SystemExit(C.run_main(step, "模擬 M"))
