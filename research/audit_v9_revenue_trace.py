"""驗.九一 析.三：營收因子(f_revenue_surprise)百分位 #8 的 99.0 → #404 的 87.0，逐變數追查。

診斷、非試驗：不登記TRIALS_LEDGER（凍結.二）、不改任何既有判定、不碰holdout（統計只用
date<=VAL_END）。**全程只讀本機快取，絕不打網路**（FinMind額度保留給驗.九二；yfinance也
不打）：requests.* 一律丟錯、finmind_client._fetch 快取未命中直接丟錯並記入缺口、
yf_price_client.fetch_yf_adjusted 只讀既有parquet（不存在則回空表、且不寫檔）。
缺快取的檔一律記為「缺口」、不補抓。

方法（輕量路徑，與 factor_ic.load_sample_with_factors 的營收因子完全等價，只是不算其他
因子）：價格由「還原價建構器」產生 → _asof_join(_revenue_surprise_sue) → 用「現行」
fic.evaluate_factor/build_snapshots 評分（Bonferroni n=6，須>=98.33）。
三個建構器（同一份快取、不同時期的 adjust.py）：
  orig   = git 899c96644:research/adjust.py（#8當時；FinMind原始價×股利，無yfinance）
  frozen = git 7a8fd5cda:research/adjust.py（#404 (i)組；yfinance優先，尚無上市日截斷）
  cur    = 現行 research/adjust.py（#404 (ii)組；含上市日截斷等）
  cur_notrunc = 現行但把_truncate_pre_listing換成恆等（單獨隔離「興櫃/上市日截斷」）
四個樣本（seed 20260822 全同）：
  old100/old300 = 用 899c96644 的 universe()（併檔bug修前的順序）抽
  cur100/cur300 = 用現行 universe()（ab7e9a40c修後順序）抽
輸出 data/diag_v9_revenue_trace.json。用法：python audit_v9_revenue_trace.py [--full-orig]
（--full-orig：另把 899c96644 的 research 整棵解到暫存目錄，用原始程式碼原封跑一次）。
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import ast
import collections
import importlib.util
import json
import random
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "data" / "diag_v9_revenue_trace.json"
ORIG_SHA = "899c96644"      # #8（2026-08-23）當時的 commit
FROZEN_SHA = "7a8fd5cda"    # #404 (i) 組使用的凍結舊 adjust（v7腳本 FROZEN_ADJUST）

# ---------------------------------------------------------------- 只讀快取的防護
MISSING: "collections.OrderedDict[str, int]" = collections.OrderedDict()


def _no_network(*a, **k):
    raise RuntimeError("NO_NETWORK (驗.九一 cache-only)")


for _n in ("get", "post", "request", "head"):
    setattr(requests, _n, _no_network)
requests.Session.request = _no_network  # type: ignore[assignment]

import finmind_client as fm  # noqa: E402

_orig_fetch = fm._fetch


def _cache_only_fetch(dataset, data_id="", start_date="2000-01-01", end_date=None,
                      force_refresh=False, **kw):
    p = fm._cache_path(dataset, data_id, start_date, end_date)
    if not p.exists():
        MISSING[p.name] = MISSING.get(p.name, 0) + 1
        raise RuntimeError(f"CACHE_MISS {p.name}")
    return _orig_fetch(dataset, data_id, start_date, end_date, False, **kw)


fm._fetch = _cache_only_fetch

import yf_price_client as yfc  # noqa: E402

_orig_yf = yfc.fetch_yf_adjusted


def _cache_only_yf(stock_id, start_date="2010-01-01", end_date=None, force_refresh=False):
    from validation.holdout import VAL_END as _VE
    eff = end_date if (end_date and end_date <= _VE) else _VE
    path = yfc._cache_path(stock_id, start_date, eff)
    if not path.exists():
        MISSING["yf:" + path.name] = MISSING.get("yf:" + path.name, 0) + 1
        return pd.DataFrame()  # 不呼叫原函式（原函式會打網路並把空結果寫成快取檔）
    return _orig_yf(stock_id, start_date, end_date, False)


yfc.fetch_yf_adjusted = _cache_only_yf

import adjust as adj_cur  # noqa: E402
import factor_ic as fic  # noqa: E402
import factors as fac  # noqa: E402
from strategies.weinstein_stage2 import prepare_market_data  # noqa: E402
from validation import holdout  # noqa: E402

START = fic.START_DATE
SEED = fic.SAMPLE_SEED
VAL_END = holdout.VAL_END
TRAIN_END = holdout.TRAIN_END
COL = "f_revenue_surprise"
BONF_N = 6


def _quiet_adjust(mod) -> None:
    """不改任何追蹤檔（異常/交叉比對log）；模組沒有該函式就略過。"""
    for name in ("_append_anomaly_log", "_append_crosscheck_log"):
        if hasattr(mod, name):
            setattr(mod, name, lambda *a, **k: None)
    if hasattr(mod, "crosscheck_yf_vs_finmind"):
        mod.crosscheck_yf_vs_finmind = lambda *a, **k: []


_quiet_adjust(adj_cur)

TMP = Path(tempfile.mkdtemp(prefix="v9trace_"))


def git_show(sha: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{sha}:{path}"], cwd=REPO, check=True,
                          capture_output=True).stdout.decode("utf-8")


def load_module_from_git(name: str, sha: str, path: str):
    f = TMP / f"{name}.py"
    f.write_bytes(git_show(sha, path).encode("utf-8"))
    spec = importlib.util.spec_from_file_location(name, f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


adj_orig = load_module_from_git("adjust_orig", ORIG_SHA, "research/adjust.py")
adj_frozen = load_module_from_git("adjust_frozen", FROZEN_SHA, "research/adjust.py")
_quiet_adjust(adj_orig)
_quiet_adjust(adj_frozen)
uni_old = load_module_from_git("universe_old", ORIG_SHA, "research/universe.py")

BUILDERS = {
    "orig": adj_orig.adjusted_price_series,
    "frozen": adj_frozen.adjusted_price_series,
    "cur": adj_cur.adjusted_price_series,
}


def _cur_notrunc(sid: str, start: str):
    real = adj_cur._truncate_pre_listing
    adj_cur._truncate_pre_listing = lambda df, stock_id: df
    try:
        return adj_cur.adjusted_price_series(sid, start)
    finally:
        adj_cur._truncate_pre_listing = real


BUILDERS["cur_notrunc"] = _cur_notrunc

# ---------------------------------------------------------------- 資料層
_market = prepare_market_data(fm.load_dev("TaiwanStockPrice", "TAIEX", START))
CALENDAR = sorted(_market["date"].tolist())
SNAPS = fic.build_snapshots(CALENDAR, fic.SNAPSHOT_START, VAL_END)
AS_OF = [a for a, _ in SNAPS]
FWD = [b for _, b in SNAPS]
IS_TRAIN = np.array([a <= TRAIN_END for a in AS_OF])
IS_VAL = np.array([(a > TRAIN_END) and (a <= VAL_END) for a in AS_OF])

_rev_cache: dict[str, tuple[str, pd.DataFrame | None]] = {}
_frame_cache: dict[tuple[str, str], tuple[str, pd.DataFrame | None]] = {}
_mat_cache: dict[tuple[str, str], tuple[str, np.ndarray | None, np.ndarray | None]] = {}


def rev_table(sid: str):
    """('ok'|'rev_miss', 表)。等價於 prepare_factors 的營收區塊（同一支 _revenue_surprise_sue）。"""
    if sid not in _rev_cache:
        try:
            _rev_cache[sid] = ("ok", fac._revenue_surprise_sue(sid, START))
        except Exception:  # noqa: BLE001
            _rev_cache[sid] = ("rev_miss", None)
    return _rev_cache[sid]


def frame(builder: str, sid: str):
    """('ok'|'price_err'|'price_short'|'rev_miss', df[date,adj_close,f_revenue_surprise]|None)。
    usable 判準 = 原 load_sample_with_factors：價格建得出來、>=260列、營收表算得出來。"""
    key = (builder, sid)
    if key in _frame_cache:
        return _frame_cache[key]
    try:
        px = BUILDERS[builder](sid, START)
    except Exception:  # noqa: BLE001
        _frame_cache[key] = ("price_err", None)
        return _frame_cache[key]
    if px.empty:
        _frame_cache[key] = ("price_err", None)
        return _frame_cache[key]
    if len(px) < 260:
        _frame_cache[key] = ("price_short", None)
        return _frame_cache[key]
    st, sue = rev_table(sid)
    if st != "ok":
        _frame_cache[key] = ("rev_miss", None)
        return _frame_cache[key]
    d = px.sort_values("date").reset_index(drop=True).copy()
    d = fac._asof_join(d, sue, "revenue_sue", COL)
    _frame_cache[key] = ("ok", d[["date", "adj_close", COL]].copy())
    return _frame_cache[key]


def snap_matrix(builder: str, sid: str):
    """每檔在每個快照的 (因子值F, 前瞻報酬R)；與 factor_ic._cross_section 同義（缺任一值或p0<=0→NaN）。"""
    key = (builder, sid)
    if key in _mat_cache:
        return _mat_cache[key]
    had = key in _frame_cache
    st, d = frame(builder, sid)
    if not had:
        _frame_cache.pop(key, None)  # 池掃描只留小矩陣，不留整張價格表（本機記憶體吃緊，mem_guard 門檻3GB）
    if st != "ok":
        _mat_cache[key] = (st, None, None)
        return _mat_cache[key]
    u = d.drop_duplicates("date")  # _cross_section 取 idx[0]
    ix = pd.Index(u["date"])
    i0, i1 = ix.get_indexer(AS_OF), ix.get_indexer(FWD)
    ok = (i0 >= 0) & (i1 >= 0)
    fv = np.full(len(SNAPS), np.nan)
    p0 = np.full(len(SNAPS), np.nan)
    p1 = np.full(len(SNAPS), np.nan)
    fv[ok] = u[COL].to_numpy(float)[i0[ok]]
    p0[ok] = u["adj_close"].to_numpy(float)[i0[ok]]
    p1[ok] = u["adj_close"].to_numpy(float)[i1[ok]]
    bad = ~np.isfinite(fv) | ~np.isfinite(p0) | ~np.isfinite(p1) | (p0 <= 0)
    R = p1 / p0 - 1
    fv[bad] = np.nan
    R[bad] = np.nan
    _mat_cache[key] = ("ok", fv, R)
    return _mat_cache[key]


# ---------------------------------------------------------------- 評分
def evaluate_real(builder: str, ids: list[str], label: str) -> dict:
    """現行 fic.evaluate_factor（權威）。"""
    data, status = {}, collections.Counter()
    for sid in ids:
        st, d = frame(builder, sid)
        status[st] += 1
        if st == "ok":
            data[sid] = d
    t0 = time.time()
    r = fic.evaluate_factor(COL, data, SNAPS, bonferroni_n=BONF_N)
    return {
        "label": label, "builder": builder, "n_sample": len(ids), "n_usable": len(data),
        "status": dict(status), "train_ic": r.train_mean_ic, "train_ir": r.train_ic_ir,
        "val_ic": r.val_mean_ic, "val_ir": r.val_ic_ir, "val_hit": r.val_hit_rate,
        "n_train": r.n_dates_train, "n_val": r.n_dates_val,
        "percentile": r.null_percentile, "required": r.required_percentile,
        "same_sign": bool(r.same_sign), "passes": bool(r.passes),
        "sec": round(time.time() - t0, 1),
    }


def fast_eval(builder: str, ids: list[str], n_shuf: int = 1000, seed: int = 20260822,
              mats: dict | None = None) -> dict:
    """向量化等價實作（換成numpy的排列虛無分佈，RNG不同故非逐位元相同，只用於重抽樣與交叉驗證）。"""
    rows_f, rows_r = [], []
    for sid in ids:
        st, f, r = (mats[sid] if mats is not None else snap_matrix(builder, sid))
        if st == "ok":
            rows_f.append(f)
            rows_r.append(r)
    if not rows_f:
        return {"n_usable": 0}
    F, R = np.vstack(rows_f), np.vstack(rows_r)
    valid = np.isfinite(F) & np.isfinite(R)
    tr, va = [], []
    sections = []
    for k in range(len(SNAPS)):
        m = valid[:, k]
        if m.sum() < 10:
            continue
        rf, rr = rankdata(F[m, k]), rankdata(R[m, k])
        rfc, rrc = rf - rf.mean(), rr - rr.mean()
        den = np.sqrt((rfc ** 2).sum() * (rrc ** 2).sum())
        if den == 0:
            continue
        ic = float((rfc * rrc).sum() / den)
        if IS_TRAIN[k]:
            tr.append(ic)
        elif IS_VAL[k]:
            va.append(ic)
            sections.append((rf, rrc, den))
    val_mean = float(np.mean(va)) if va else float("nan")
    train_mean = float(np.mean(tr)) if tr else float("nan")
    rng = np.random.default_rng(seed)
    acc = np.zeros(n_shuf)
    for rf, rrc, den in sections:
        perm = rng.permuted(np.tile(rf, (n_shuf, 1)), axis=1)
        acc += (perm @ rrc) / den
    null = acc / len(sections)
    pct = float(100.0 * np.mean(abs(val_mean) > np.abs(null)))
    return {
        "n_usable": len(rows_f), "train_ic": train_mean, "val_ic": val_mean,
        "val_ir": float(np.mean(va) / np.std(va)) if len(va) > 1 and np.std(va) > 0 else float("nan"),
        "n_train": len(tr), "n_val": len(va), "percentile": pct,
    }


# ---------------------------------------------------------------- 宇宙與樣本
def universe_ids_old() -> list[str]:
    return list(uni_old.universe()["stock_id"])


def universe_ids_cur() -> list[str]:
    from universe import universe as cu
    return list(cu()["stock_id"])


def sample_from(ids: list[str], n: int) -> list[str]:
    return random.Random(SEED).sample(ids, n)


def cache_flags(sid: str) -> dict:
    def ex(ds):
        return fm._cache_path(ds, sid, START, VAL_END).exists()
    return {"price": ex("TaiwanStockPrice"), "div": ex("TaiwanStockDividend"),
            "rev": ex("TaiwanStockMonthRevenue"),
            "yf": yfc._cache_path(sid, START, VAL_END).exists()}


# ---------------------------------------------------------------- 靜態檢查：程式碼是否相同
def ast_compare() -> dict:
    """比較 899c96644 與現行 HEAD 的關鍵函式AST（去除docstring）是否逐節點相同。"""
    def funcs(src: str) -> dict:
        tree = ast.parse(src)
        out = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                        and isinstance(n.body[0].value.value, str):
                    n.body = n.body[1:] or [ast.Pass()]
                out[n.name] = ast.dump(n)
        return out
    res = {}
    for path, names in (("research/pit.py", ["month_revenue_pit"]),
                        ("research/factors.py", ["_asof_join", "_revenue_surprise_sue"])):
        a = funcs(git_show(ORIG_SHA, path))
        b = funcs((REPO / path).read_text(encoding="utf-8"))
        for nm in names:
            res[f"{path}::{nm}"] = bool(nm in a and nm in b and a[nm] == b[nm])
    for path in ("research/pit.py", "research/factors.py"):
        a = funcs(git_show(ORIG_SHA, path))
        b = funcs((REPO / path).read_text(encoding="utf-8"))
        res[f"{path}::changed_functions"] = sorted(k for k in a if k in b and a[k] != b[k])
        res[f"{path}::added_functions"] = sorted(k for k in b if k not in a)
    # factor_ic 常數
    a_src, b_src = git_show(ORIG_SHA, "research/factor_ic.py"), (HERE / "factor_ic.py").read_text(encoding="utf-8")
    consts = {}
    for c in ("SAMPLE_SEED", "SAMPLE_SIZE", "START_DATE", "SNAPSHOT_START", "N_SHUFFLES", "SHUFFLE_SEED", "BASE_ALPHA"):
        def g(src):
            for ln in src.splitlines():
                if ln.startswith(c + " ="):
                    return ln.split("=", 1)[1].split("#")[0].strip()
            return None
        consts[c] = {"orig": g(a_src), "cur": g(b_src)}
    res["factor_ic_constants"] = consts
    return res


# ---------------------------------------------------------------- 主流程
def fmt(r: dict) -> str:
    return (f"{r['label']:<52} usable={r['n_usable']:>3}/{r['n_sample']:<3} val_ic={r['val_ic']:+.4f} "
            f"IR={r['val_ir']:+.3f} n_val={r['n_val']} pct={r['percentile']:.1f} "
            f"({'PASS' if r['passes'] else 'FAIL'})")


def run_full_orig(ids: list[str]) -> dict:
    """把 899c96644 的 research 整棵解到暫存目錄，用原始程式碼原封跑（cache-only，資料目錄指向主快取）。"""
    tree = TMP / "orig_tree"
    tree.mkdir()
    tar = subprocess.run(["git", "archive", ORIG_SHA, "research"], cwd=REPO, check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(tree)], input=tar, check=True)
    ids_file = TMP / "ids.json"
    ids_file.write_text(json.dumps(ids), encoding="utf-8")
    code = r'''
import sys, json, collections
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, sys.argv[1])
import requests
def _no(*a, **k): raise RuntimeError("NO_NETWORK")
requests.get = _no
from pathlib import Path
import finmind_client as fm
fm.DATA_DIR = Path(sys.argv[2])
MISS = collections.OrderedDict()
_o = fm._fetch
def _f(dataset, data_id="", start_date="2000-01-01", end_date=None, force_refresh=False, **kw):
    p = fm._cache_path(dataset, data_id, start_date, end_date)
    if not p.exists(): MISS[p.name] = 1
    return _o(dataset, data_id, start_date, end_date, False, **kw)
fm._fetch = _f
import factor_ic as fic
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout
ids = json.load(open(sys.argv[3]))
mdf = prepare_market_data(fm.load_dev("TaiwanStockPrice", "TAIEX", fic.START_DATE))
data = fic.load_sample_with_factors(ids, mdf)
snaps = fic.build_snapshots(sorted(mdf["date"].tolist()), fic.SNAPSHOT_START, holdout.VAL_END)
r = fic.evaluate_factor("f_revenue_surprise", data, snaps, bonferroni_n=6)
print("RESULT_JSON " + json.dumps({"usable": len(data), "n_snaps": len(snaps), "train_ic": r.train_mean_ic,
      "val_ic": r.val_mean_ic, "val_ir": r.val_ic_ir, "val_hit": r.val_hit_rate, "n_val": r.n_dates_val,
      "percentile": r.null_percentile, "required": r.required_percentile, "same_sign": bool(r.same_sign),
      "passes": bool(r.passes), "n_cache_miss": len(MISS)}))
'''
    (TMP / "run_orig.py").write_text(code, encoding="utf-8")
    p = subprocess.run([sys.executable, str(TMP / "run_orig.py"), str(tree / "research"),
                        str(fm.DATA_DIR), str(ids_file)], capture_output=True, cwd=str(tree / "research"))
    txt = p.stdout.decode("utf-8", "replace")
    for ln in txt.splitlines():
        if ln.startswith("RESULT_JSON "):
            return json.loads(ln[len("RESULT_JSON "):])
    return {"error": (txt + p.stderr.decode("utf-8", "replace"))[-800:]}


def main() -> None:
    t_start = time.time()
    full_orig = "--full-orig" in sys.argv
    out: dict = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                 "note": "診斷、非試驗；只讀快取（零網路）；統計限date<=VAL_END；不改任何既有判定；缺快取只記缺口不補抓。",
                 "shas": {"orig": ORIG_SHA, "frozen": FROZEN_SHA,
                          "head": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                                                 capture_output=True).stdout.decode().strip()},
                 "n_snapshots": len(SNAPS), "n_train_snaps": int(IS_TRAIN.sum()), "n_val_snaps": int(IS_VAL.sum())}

    # ---- 0. 程式碼相同性（靜態）
    out["static_code_check"] = ast_compare()
    print("靜態檢查：", json.dumps({k: v for k, v in out["static_code_check"].items()
                                     if "month_revenue_pit" in k or "_asof_join" in k or "_revenue_surprise" in k},
                                    ensure_ascii=False))

    # ---- 1. 宇宙與樣本
    uo, uc = universe_ids_old(), universe_ids_cur()
    samples = {"old100": sample_from(uo, 100), "old300": sample_from(uo, 300),
               "cur100": sample_from(uc, 100), "cur300": sample_from(uc, 300)}
    ov = lambda a, b: len(set(samples[a]) & set(samples[b]))  # noqa: E731
    out["universe"] = {
        "n_old": len(uo), "n_cur": len(uc), "same_population": sorted(uo) == sorted(uc),
        "same_order": uo == uc,
        "n_positions_differ": int(sum(1 for a, b in zip(uo, uc) if a != b)),
        "first100_old_eq_first100_of_old300": samples["old100"] == samples["old300"][:100],
        "first100_cur_eq_first100_of_cur300": samples["cur100"] == samples["cur300"][:100],
    }
    out["sample_overlap"] = {f"{a}~{b}": ov(a, b) for a, b in
                             [("old100", "cur100"), ("old100", "cur300"), ("old300", "cur300"),
                              ("old100", "old300"), ("cur100", "cur300")]}
    flags = {k: [cache_flags(s) for s in v] for k, v in samples.items()}
    out["sample_cache_coverage"] = {k: {c: int(sum(f[c] for f in v)) for c in ("price", "div", "rev", "yf")}
                                    for k, v in flags.items()}
    print("樣本重疊：", out["sample_overlap"])
    print("樣本快取覆蓋：", out["sample_cache_coverage"])

    # ---- 2. 驗證：重現 #8 = 99.0（orig建構器 + old100）
    grid: dict[str, dict] = {}
    rows: list[dict] = []

    def run(builder: str, sname: str, tag: str | None = None) -> dict:
        r = evaluate_real(builder, samples[sname], f"{sname} × {builder}")
        r["sample"] = sname
        grid[f"{sname}|{builder}"] = r
        print(fmt(r))
        return r

    print("\n== 驗證：輕量路徑須重現 #8（99.0/80檔/121截面）與 #404 (i)87.2、(ii)87.0 ==")
    r0 = run("orig", "old100")
    out["validation_reproduce_8"] = {
        "expected": {"percentile": 99.0, "n_usable": 80, "n_val": 47, "val_ic": 0.049577},
        "got": {k: r0[k] for k in ("percentile", "n_usable", "n_val", "val_ic", "train_ic", "val_ir")},
        "match": bool(abs(r0["percentile"] - 99.0) < 1e-9 and r0["n_usable"] == 80 and r0["n_val"] == 47
                      and abs(r0["val_ic"] - 0.049577) < 5e-7)}
    r404i = run("frozen", "cur300")
    r404ii = run("cur", "cur300")
    out["validation_reproduce_404"] = {
        "expected": {"i_percentile": 87.2, "i_val_ic": 0.0174, "ii_percentile": 87.0, "ii_val_ic": 0.0173, "n_val": 47},
        "got_i": {k: r404i[k] for k in ("percentile", "val_ic", "n_val", "n_usable")},
        "got_ii": {k: r404ii[k] for k in ("percentile", "val_ic", "n_val", "n_usable")},
        "match_i": bool(abs(r404i["percentile"] - 87.2) < 0.15 and abs(r404i["val_ic"] - 0.0174) < 5e-5),
        "match_ii": bool(abs(r404ii["percentile"] - 87.0) < 0.15 and abs(r404ii["val_ic"] - 0.0173) < 5e-5)}
    print("重現#8：", out["validation_reproduce_8"]["match"], " 重現#404 i/ii：",
          out["validation_reproduce_404"]["match_i"], out["validation_reproduce_404"]["match_ii"])

    if full_orig:
        fo = run_full_orig(samples["old100"])
        out["full_original_code_repro"] = fo
        print("原始程式碼原封重跑：", fo)

    # ---- 3. 完整網格 4樣本×4建構器
    print("\n== 網格 ==")
    for sname in ("old100", "old300", "cur100", "cur300"):
        for b in ("orig", "frozen", "cur_notrunc", "cur"):
            if f"{sname}|{b}" not in grid:
                run(b, sname)
    out["grid"] = grid

    # ---- 4. 鏈與單變數控制
    def g(s, b):
        return grid[f"{s}|{b}"]

    def step(name, frm, to, var):
        a, b = g(*frm), g(*to)
        return {"step": name, "variable": var, "from": f"{frm[0]}×{frm[1]}", "to": f"{to[0]}×{to[1]}",
                "pct_from": a["percentile"], "pct_to": b["percentile"], "d_pct": b["percentile"] - a["percentile"],
                "val_ic_from": a["val_ic"], "val_ic_to": b["val_ic"], "n_val_to": b["n_val"],
                "n_usable_to": b["n_usable"], "passes_to": b["passes"]}

    chainA = [  # 先換樣本、再換價格建構器
        step("A0→A1", ("old100", "orig"), ("old300", "orig"), "(a1)樣本檔數100→300（舊順序，前100檔不變）"),
        step("A1→A2", ("old300", "orig"), ("cur300", "orig"), "(a2)宇宙順序修正→同seed抽到不同的300檔"),
        step("A2→A3", ("cur300", "orig"), ("cur300", "frozen"), "(f0)價格建構器：FinMind原始價→yfinance優先（#404 (i)）"),
        step("A3→A4", ("cur300", "frozen"), ("cur300", "cur_notrunc"), "(f)現行adjust其餘修正（split/減資/面額/FinMind路徑）"),
        step("A4→A5", ("cur300", "cur_notrunc"), ("cur300", "cur"), "(e)上市日截斷（興櫃期間價格移除）（#404 (ii)）"),
    ]
    chainB = [  # 先換價格建構器、最後才換樣本
        step("B0→B1", ("old100", "orig"), ("old100", "frozen"), "(f0)價格建構器→yfinance優先"),
        step("B1→B2", ("old100", "frozen"), ("old100", "cur_notrunc"), "(f)現行adjust其餘修正"),
        step("B2→B3", ("old100", "cur_notrunc"), ("old100", "cur"), "(e)上市日截斷"),
        step("B3→B4", ("old100", "cur"), ("cur100", "cur"), "(a2)宇宙順序修正→抽到不同的100檔"),
        step("B4→B5", ("cur100", "cur"), ("cur300", "cur"), "(a1)檔數100→300"),
    ]
    single = [step(f"S{i}", ("old100", "orig"), t, v) for i, (t, v) in enumerate([
        (("old100", "frozen"), "只換價格建構器→yfinance優先"),
        (("old100", "cur_notrunc"), "只換價格建構器→現行(無截斷)"),
        (("old100", "cur"), "只換價格建構器→現行(含截斷)"),
        (("old300", "orig"), "只把檔數改300（舊順序）"),
        (("cur100", "orig"), "只把宇宙順序改現行（100檔）"),
        (("cur300", "orig"), "檔數300＋現行順序（其餘全同原始）"),
    ])]
    out["chain_A_sample_first"] = chainA
    out["chain_B_builder_first"] = chainB
    out["single_swap_from_original"] = single
    print("\n== 鏈A ==")
    for s in chainA:
        print(f"  {s['step']} {s['variable']}: {s['pct_from']:.1f}→{s['pct_to']:.1f} ({s['d_pct']:+.1f}) val_ic {s['val_ic_from']:+.4f}→{s['val_ic_to']:+.4f}")
    print("== 鏈B ==")
    for s in chainB:
        print(f"  {s['step']} {s['variable']}: {s['pct_from']:.1f}→{s['pct_to']:.1f} ({s['d_pct']:+.1f}) val_ic {s['val_ic_from']:+.4f}→{s['val_ic_to']:+.4f}")
    print("== 單變數控制（從原始出發只換一項）==")
    for s in single:
        print(f"  {s['variable']}: {s['pct_from']:.1f}→{s['pct_to']:.1f} ({s['d_pct']:+.1f}) val_ic→{s['val_ic_to']:+.4f}")

    # ---- 5. 共同支持集：控制「哪些檔用得出來」的組成差異
    common = {}
    for sname in samples:
        ok = [s for s in samples[sname] if all(frame(b, s)[0] == "ok" for b in ("orig", "frozen", "cur_notrunc", "cur"))]
        common[sname] = {"n_common": len(ok), "rows": {}}
        for b in ("orig", "frozen", "cur_notrunc", "cur"):
            r = evaluate_real(b, ok, f"{sname}∩共同 × {b}")
            common[sname]["rows"][b] = {k: r[k] for k in ("n_usable", "val_ic", "val_ir", "n_val", "percentile", "passes")}
            print(fmt(r))
    out["common_support"] = common

    # ---- 6. 池內重抽樣：估「同一設定下、換一批股票」的百分位噪音，並成對比較建構器
    print("\n== 池內重抽樣 ==")
    all_ids = sorted(set(uo))
    pool_builders = ("orig", "frozen", "cur_notrunc", "cur")
    pool = []
    t0 = time.time()
    for i, sid in enumerate(all_ids):
        if not cache_flags(sid)["rev"]:
            continue
        if all(snap_matrix(b, sid)[0] == "ok" for b in pool_builders):
            pool.append(sid)
        if (i + 1) % 400 == 0:
            print(f"  掃描 {i + 1}/{len(all_ids)} 池={len(pool)} ({time.time() - t0:.0f}s)")
    print(f"共同池：{len(pool)} 檔（宇宙 {len(all_ids)}；四個建構器皆可用且有營收快取）")
    mats = {b: {s: snap_matrix(b, s) for s in pool} for b in pool_builders}
    # fast_eval 與權威實作交叉驗證
    xv = {}
    for sname, b in (("old100", "orig"), ("cur300", "cur"), ("cur300", "frozen")):
        ids = [s for s in samples[sname] if frame(b, s)[0] == "ok"]
        fe = fast_eval(b, ids)
        xv[f"{sname}×{b}"] = {"fast_pct": fe["percentile"], "real_pct": grid[f"{sname}|{b}"]["percentile"],
                               "fast_val_ic": fe["val_ic"], "real_val_ic": grid[f"{sname}|{b}"]["val_ic"]}
    out["fast_eval_crosscheck"] = xv
    print("fast_eval vs 權威：", xv)

    M = 400
    resample = {"pool_size": len(pool), "n_draws": M, "n_shuffles_each": 500, "sizes": {}}
    for size in (80, 240):
        rng = random.Random(910001 + size)
        per_b = {b: [] for b in pool_builders}
        for _ in range(M):
            ids = rng.sample(pool, size)
            for b in pool_builders:
                per_b[b].append(fast_eval(b, ids, n_shuf=500, mats=mats[b]))
        stats = {}
        for b in pool_builders:
            p = np.array([x["percentile"] for x in per_b[b]])
            v = np.array([x["val_ic"] for x in per_b[b]])
            stats[b] = {"pct_mean": float(p.mean()), "pct_sd": float(p.std()),
                        "pct_q05": float(np.quantile(p, .05)), "pct_q25": float(np.quantile(p, .25)),
                        "pct_q50": float(np.quantile(p, .5)), "pct_q75": float(np.quantile(p, .75)),
                        "pct_q95": float(np.quantile(p, .95)),
                        "share_ge_98.33": float((p >= 98.33).mean()), "share_ge_99.0": float((p >= 99.0).mean()),
                        "share_le_87.0": float((p <= 87.0).mean()),
                        "val_ic_mean": float(v.mean()), "val_ic_sd": float(v.std())}
        paired = {}
        for b in pool_builders[1:]:
            dp = np.array([x["percentile"] for x in per_b[b]]) - np.array([x["percentile"] for x in per_b["orig"]])
            dv = np.array([x["val_ic"] for x in per_b[b]]) - np.array([x["val_ic"] for x in per_b["orig"]])
            paired[f"{b}-orig"] = {"d_pct_mean": float(dp.mean()), "d_pct_sd": float(dp.std()),
                                   "d_val_ic_mean": float(dv.mean()), "d_val_ic_sd": float(dv.std())}
        for a, b in (("frozen", "cur_notrunc"), ("cur_notrunc", "cur")):
            dp = np.array([x["percentile"] for x in per_b[b]]) - np.array([x["percentile"] for x in per_b[a]])
            dv = np.array([x["val_ic"] for x in per_b[b]]) - np.array([x["val_ic"] for x in per_b[a]])
            paired[f"{b}-{a}"] = {"d_pct_mean": float(dp.mean()), "d_pct_sd": float(dp.std()),
                                  "d_val_ic_mean": float(dv.mean()), "d_val_ic_sd": float(dv.std())}
        resample["sizes"][str(size)] = {"by_builder": stats, "paired_builder_effect": paired}
        print(f"  size={size}: " + " | ".join(
            f"{b}: 均{stats[b]['pct_mean']:.1f} sd{stats[b]['pct_sd']:.1f} ≥98.33占{stats[b]['share_ge_98.33']:.0%} ≤87占{stats[b]['share_le_87.0']:.0%}"
            for b in ("orig", "cur")))
        print("    成對建構器效應：", {k: (round(v['d_pct_mean'], 2), round(v['d_pct_sd'], 2)) for k, v in paired.items()})
    out["pool_resample"] = resample

    # ---- 7. 缺口
    out["gaps"] = {
        "n_missing_cache_entries": len(MISSING),
        "missing_sample": list(MISSING)[:40],
        "not_usable_by_status": {f"{s}|{b}": {k: v for k, v in grid[f"{s}|{b}"]["status"].items() if k != "ok"}
                                 for s in samples for b in ("orig", "cur")},
        "note": "缺快取者一律不補抓；usable=價格建得出來且>=260列且營收表可算（等價原load_sample_with_factors對營收因子的門檻）。",
    }
    out["elapsed_sec"] = round(time.time() - t_start, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n已寫入 {OUT}  (缺口 {len(MISSING)} 筆快取項；耗時 {out['elapsed_sec']}s)")


if __name__ == "__main__":
    main()
