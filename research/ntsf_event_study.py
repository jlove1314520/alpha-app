# -*- coding: utf-8 -*-
"""先.一五六-2 國安基金進場事件：事件研究＋策略格點（紙上優化軌）。

零外部請求：只讀本機快取
- 加權指數日線：research/data/raw_yf/INDEX_TWII__1978-01-01__2024-12-31.parquet
  ＋ INDEX_TWII__2010-01-01__2026-08-27.parquet（2025～2026-08）
  ＋ research/data/paper_8_taiex_closes.json（2026-07 起官方 FMTQIK 收盤）
- 事件表：research/data/ntsf_events.csv（本機、不進公開 repo）

標的說明（照實）：
- 「0050」用加權**價格**指數代理（不含息，0050 2003 才上市；比 0050 含息報酬保守約 2～4%/年）。
- 「00631L」與 1.5×／3× 用指數**每日再平衡合成**：r_L = L·r − (L−1)·融資 2%/年 − 內扣 1%/年（1× 內扣 0.43%/年）。
  00631L 2014-10 才上市，之前的事件只能用合成；3× 台灣沒有對應 ETF，屬理論值（實際要用期貨，保證金另計）。
- PQ／F12 名單版本本批未做（見 NTSF_EVENT.md）。

PIT：
- 進場一律在「宣布後下一個交易日收盤」。宣布日查不到的事件，假設最壞情況＝首日進場日當天盤後才公告，
  所以進場日＝首日進場日的下一個交易日（比實際晚，保守）。
- 首日進場日來源衝突者，取較晚的日期（保守）。
- 「跌破宣布日低點再買」：參考低點＝宣布日（查不到用首日進場日）當天最低價；之後 20 個交易日內
  收盤跌破才在當天收盤買，沒跌破就不買。
成本：每邊手續費 0.1425%＋滑價 0.1%；賣出證交稅 0.1%（ETF）。
"""
from __future__ import annotations

import csv
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT_JSON = DATA / "ntsf_event_result.json"

FEE = 0.001425
SLIP = 0.001
TAX = 0.001
FIN = 0.02
HORIZONS = [5, 20, 60, 120, 250]


def load_taiex() -> pd.DataFrame:
    a = pd.read_parquet(DATA / "raw_yf/INDEX_TWII__1978-01-01__2024-12-31.parquet")
    b = pd.read_parquet(DATA / "raw_yf/INDEX_TWII__2010-01-01__2026-08-27.parquet")
    b = b[b["date"] > a["date"].max()]
    df = pd.concat([a, b])[["date", "open", "high", "low", "close"]]
    df["date"] = pd.to_datetime(df["date"])
    p8 = json.load(open(DATA / "paper_8_taiex_closes.json", encoding="utf-8"))["closes"]
    ext = pd.DataFrame([(pd.Timestamp(k), v) for k, v in p8.items()], columns=["date", "close"])
    ext = ext[ext["date"] > df["date"].max()]
    # 官方收盤只有收盤價：高低以收盤代替（只影響 2026-08-26 之後、即第 10 次的參考低點）
    ext["open"] = ext["high"] = ext["low"] = ext["close"]
    df = pd.concat([df, ext]).sort_values("date").drop_duplicates("date", keep="last")
    df = df[df["close"] > 0].reset_index(drop=True)
    return df


def load_events() -> list[dict]:
    ev = []
    with open(DATA / "ntsf_events.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ev.append(r)
    # [自行裁量] 衝突取較晚日期：2008→09-19、2011→12-21、2020→03-20
    late = {"4": "2008-09-19", "5": "2011-12-21", "7": "2020-03-20"}
    for r in ev:
        if r["no"] in late:
            r["first_entry_date"] = late[r["no"]]
    return ev


def idx_on_or_after(dates: np.ndarray, d: pd.Timestamp) -> int:
    return int(np.searchsorted(dates, np.datetime64(d), side="left"))


def event_anchor(r: dict, dates: np.ndarray) -> tuple[int, int]:
    """回傳（參考日 index, 進場日 index＝參考日下一個交易日）。"""
    if r["announce_date"]:
        ref = idx_on_or_after(dates, pd.Timestamp(r["announce_date"]))
    else:
        ref = idx_on_or_after(dates, pd.Timestamp(r["first_entry_date"]))
    return ref, ref + 1


def lev_returns(r: np.ndarray, L: float) -> np.ndarray:
    fee = 0.0043 if L == 1 else 0.01
    return L * r - (L - 1) * FIN / 252 - fee / 252


def run_trade(close: np.ndarray, ma: dict, ent: int, L: float, exit_rule: tuple) -> dict | None:
    n = len(close)
    if ent >= n:
        return None
    r = np.diff(close) / close[:-1]  # r[i] = close[i+1]/close[i]-1
    kind, p = exit_rule
    nav = 1.0 - FEE - SLIP
    peak = nav
    mdd = 0.0
    held = 0
    i = ent
    max_hold = p if kind == "fixed" else 250
    exited = False
    while i + 1 < n and held < max_hold:
        nav *= 1 + lev_returns(np.array([r[i]]), L)[0]
        i += 1
        held += 1
        peak = max(peak, nav)
        mdd = min(mdd, nav / peak - 1)
        if kind == "trail" and nav / peak - 1 <= -p:
            exited = True
            break
        if kind == "ma" and held >= 5 and close[i] < ma[p][i]:
            exited = True
            break
    if kind == "fixed" and held >= max_hold:
        exited = True
    if held >= max_hold:
        exited = True
    if exited:
        nav *= 1 - FEE - SLIP - TAX
    return {"ret": nav - 1, "mdd": mdd, "days": held, "closed": exited, "exit_idx": i}


PICKS = [("NTSF-A", "next_close", 2.0, "trail_0.15", "國安基金護盤後 2×（≈00631L）移動停利 15%"),
         ("NTSF-B", "next_close", 3.0, "trail_0.1", "國安基金護盤後 3×（理論，台指期實作）移動停利 10%")]


def upsert_candidates(grid: list) -> int:
    """寫進 research/data/paper_opt_candidates.json（只換 NTSF- 開頭的條目，別批的不動）。"""
    cand = DATA / "paper_opt_candidates.json"
    d = json.loads(cand.read_text(encoding="utf-8"))
    keep = [c for c in d["candidates"] if not str(c.get("id", "")).startswith("NTSF-")]
    for pid, e, L, x, name in PICKS:
        g = next(g for g in grid if g["entry"] == e and g["lev"] == L and g["exit"] == x)
        keep.append({"id": pid, "factor": "ntsf_event", "source": "先.一五六-2 國安基金進場事件",
                     "status": "紙上追蹤中（research/paper_opt_ntsf.py，起點 2026-11-09）", "name": name,
                     "params": {"entry": e, "L": L, "exit": x, "max_hold": 250},
                     "backtest_events": {"n": g["n_trades"], "compound": g["compound"], "win": g["win"],
                                         "worst_trade": g["worst_trade"], "worst_dd": g["worst_dd"],
                                         "days_in_market": g["days_in_market"]},
                     "notes": "9 次事件、樣本極小；報酬集中在 2020／2025 兩次 V 型反彈；1×＝加權價格指數代理（不含息）；"
                              "槓桿為每日再平衡合成；3× 台灣無對應 ETF"})
    d["candidates"] = keep
    cand.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    return len(keep)


def main() -> int:
    df = load_taiex()
    dates = df["date"].values
    close = df["close"].values.astype(float)
    low = df["low"].values.astype(float)
    ma = {w: pd.Series(close).rolling(w).mean().values for w in (20, 60)}
    ev = load_events()

    # ── ② 事件研究（1×、宣布後下一交易日收盤起算）
    study = []
    for r in ev:
        ref, ent = event_anchor(r, dates)
        row = {"no": int(r["no"]), "trigger": r["trigger"],
               "ref_date": str(pd.Timestamp(dates[ref]).date()) if ref < len(dates) else None,
               "entry_date": str(pd.Timestamp(dates[ent]).date()) if ent < len(dates) else None}
        for h in HORIZONS:
            if ent + h < len(close):
                seg = close[ent:ent + h + 1]
                row[f"ret_{h}"] = round(seg[-1] / seg[0] - 1, 4)
                row[f"mdd_{h}"] = round(float((seg / np.maximum.accumulate(seg) - 1).min()), 4)
            else:
                row[f"ret_{h}"] = None
                row[f"mdd_{h}"] = None
        # 宣布前 20 日跌幅（背景）
        if ref >= 20:
            row["pre20"] = round(close[ref] / close[ref - 20] - 1, 4)
        study.append(row)
    summ = {}
    for h in HORIZONS:
        v = [s[f"ret_{h}"] for s in study if s[f"ret_{h}"] is not None]
        m = [s[f"mdd_{h}"] for s in study if s[f"mdd_{h}"] is not None]
        if v:
            summ[h] = {"n": len(v), "mean": round(float(np.mean(v)), 4), "median": round(float(np.median(v)), 4),
                       "win": round(float(np.mean([x > 0 for x in v])), 3), "worst": round(min(v), 4),
                       "worst_mdd": round(min(m), 4)}

    # ── ③ 策略格點（事件 1～9 回測；第 10 次只做前向）
    entries = ["next_close", "break_low20"]
    levs = [1.0, 1.5, 2.0, 3.0]
    exits = [("fixed", h) for h in (20, 60, 120, 250)] + [("trail", t) for t in (0.10, 0.15, 0.20)] + [("ma", 20), ("ma", 60)]
    grid = []
    hist = [r for r in ev if r["no"] != "10"]
    for e, L, x in product(entries, levs, exits):
        trades = []
        for r in hist:
            ref, ent = event_anchor(r, dates)
            if e == "break_low20":
                lv = low[ref]
                hit = [j for j in range(ent, min(ent + 20, len(close))) if close[j] < lv]
                if not hit:
                    trades.append({"no": int(r["no"]), "skipped": True})
                    continue
                ent = hit[0]
            t = run_trade(close, ma, ent, L, x)
            if t:
                t["no"] = int(r["no"])
                t["entry_date"] = str(pd.Timestamp(dates[ent]).date())
                trades.append(t)
        done = [t for t in trades if not t.get("skipped")]
        rets = [t["ret"] for t in done]
        comp = float(np.prod([1 + x_ for x_ in rets]) - 1) if rets else 0.0
        worst_dd = min([t["mdd"] for t in done], default=0.0)
        days = sum(t["days"] for t in done)
        grid.append({
            "entry": e, "lev": L, "exit": f"{x[0]}_{x[1]}", "n_trades": len(done), "n_skipped": len(trades) - len(done),
            "compound": round(comp, 4), "mean": round(float(np.mean(rets)), 4) if rets else None,
            "win": round(float(np.mean([x_ > 0 for x_ in rets])), 3) if rets else None,
            "worst_trade": round(min(rets), 4) if rets else None, "worst_dd": round(worst_dd, 4),
            "days_in_market": days,
            "ret_per_100d": round(((1 + comp) ** (100 / days) - 1), 4) if days else None,
            "violates_survival": worst_dd < -0.5,
            "trades": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in t.items() if k != "exit_idx"} for t in trades],
        })
    ok = [g for g in grid if not g["violates_survival"] and g["n_trades"] >= 6]
    # 綜合排名：複利報酬、最差單筆回撤、勝率三項名次平均
    for key, rev in (("compound", True), ("worst_dd", True), ("win", True)):
        for rank, g in enumerate(sorted(ok, key=lambda g: g[key] or -9, reverse=rev)):
            g.setdefault("_rk", []).append(rank)
    for g in ok:
        g["rank_score"] = round(float(np.mean(g["_rk"])), 2)
    best_ret = sorted(ok, key=lambda g: -g["compound"])[:10]
    best_bal = sorted(ok, key=lambda g: g["rank_score"])[:10]
    for g in grid:
        g.pop("_rk", None)

    out = {"note": "先.一五六-2；零外部請求；1×＝加權價格指數代理（不含息）；槓桿為每日再平衡合成",
           "data_end": str(pd.Timestamp(dates[-1]).date()), "event_study": study, "event_summary": summ,
           "grid_size": len(grid), "n_ok": len(ok), "violates": sum(g["violates_survival"] for g in grid),
           "top_by_compound": best_ret, "top_by_rank": best_bal,
           "grid": [{k: v for k, v in g.items() if k != "trades"} for g in grid]}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    try:
        print("candidates 共", upsert_candidates(grid))
    except Exception as e:  # 十二節：只降級成警告
        print(f"[警告] 候選表寫入失敗：{e!r}")
    print("data_end", out["data_end"], "grid", len(grid), "ok", len(ok), "violates", out["violates"])
    for s in study:
        print(s)
    print(json.dumps(summ, ensure_ascii=False))
    print("— 依複利報酬")
    for g in best_ret[:6]:
        print({k: g[k] for k in ("entry", "lev", "exit", "n_trades", "compound", "win", "worst_trade", "worst_dd", "days_in_market", "rank_score")})
    print("— 依綜合名次")
    for g in best_bal[:6]:
        print({k: g[k] for k in ("entry", "lev", "exit", "n_trades", "compound", "win", "worst_trade", "worst_dd", "days_in_market", "rank_score")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
