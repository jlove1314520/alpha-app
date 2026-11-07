"""先.一五五-3 第二批 第 7 批：事件類→事件後固定持有（DevQueue 20261108-060101，紙上優化軌，零請求）。

四族（第 4 節清單「事件→事件後固定持有」裡本機有資料者）：
- E-rev  月營收意外（monthly_revenue_event_study／event_driven_sue_revenue）：f_revenue_surprise 新一期公布那天，
         新值在當日全樣本橫斷面百分位 ≥ q 才算事件。
- E-eps  財報 EPS 意外（event_driven_sue_earnings／pead）：f_eps_surprise，同上。
- E-52w  52 週新高突破（f_52w_high_prox 事件版）：收盤創 W 日新高、且前 20 日沒有創過。q 換成 W∈{126,252}。
- E-disp 處置股解除後反彈（HQ#47／paper_10）：TWSE＋TPEx 公布處置清單（本機 research/data/disposal_history_*.json，
         只到 2024），處置迄日後第一個交易日＝事件日。q 換成「全部／只取再次處置（累計≥2）」。這族只算 2015～2024。

共通規則（不偷看未來）：
- 事件觀察日 d（財報／月營收＝PIT 公布日；52w＝d 收盤；處置＝解除日）→ **d 的下一個交易日收盤進場**，持有 H 個交易日後收盤出場。
- 進場日漲幅 ≥9.5%（近似鎖漲停）→ 買不到、跳過；出場日跌幅 ≤−9.5% → 延後一天再賣（最多延 5 天）。
- 槽位 Nmax：每筆事件用「當下淨值÷Nmax」進場，槽滿就略過新事件（同日多筆依訊號強度排序）；閒置資金收台灣無風險利率。
- 成本：買 0.1925%、賣 0.4925%（同第 6 批）。缺價日報酬記 0（2025 起缺價 45 檔，同第 6 批，非下市清算模型）。
- 槓桿／組合止損沿用 batch2 overlay（只呼叫）。參數用全期挑（含 2025 起），2025 起分段不是樣本外。
- 因子值一律用 reaudit_ext2025_fin_factors.attach() 重算（不混 pkl），公式照 factors.py；核心檔只呼叫不改。
"""
from __future__ import annotations

import mem_guard  # noqa: F401

import itertools
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import reaudit_ext2025_engine as E  # noqa: E402
import reaudit_optimized_batch2_sector as S  # noqa: E402
from reaudit_ext2025_fin_factors import attach as attach_fin  # noqa: E402
from validation.costs import COMMISSION_RATE, DEFAULT_SLIPPAGE_BPS, SECURITIES_TX_TAX_NORMAL  # noqa: E402

D = HERE / "data"
OUT_JSON = D / "reaudit_batch3_batch7.json"
CAND = D / "paper_opt_candidates.json"
MD = HERE / "REAUDIT_OPTIMIZED.md"
START = "2015-01-02"
BUY_C = COMMISSION_RATE + DEFAULT_SLIPPAGE_BPS / 1e4
SELL_C = BUY_C + SECURITIES_TX_TAX_NORMAL
LIMIT = 0.095


def load():
    ext, mk, miss, jumps, end = E.load_extended()
    px = pd.DataFrame({sid: pd.Series(d["adj_close"].astype(float).to_numpy(), index=pd.to_datetime(d["date"].astype(str).str[:10]))
                       for sid, d in ext.items()}).sort_index()
    px = px[px.index >= pd.Timestamp("2014-01-01")]
    from strategies.weinstein_stage2 import prepare_market_data
    m = prepare_market_data(mk)
    gate = pd.Series(m["gate"].astype(bool).to_numpy(), index=pd.to_datetime(m["date"])).reindex(px.index).ffill().fillna(False)
    rfm = json.loads((HERE.parent / "data" / "rf_monthly.json").read_text(encoding="utf-8"))["monthly"]
    rs = pd.Series({pd.Period(r["date"][:7], "M"): float(r["rf_rate_pct"]) for r in rfm}).sort_index()
    per = px.index.to_period("M")
    rf = pd.Series(per.map(lambda p: rs[rs.index <= p].iloc[-1] if (rs.index <= p).any() else rs.iloc[0]),
                   index=px.index).astype(float) / 100 / 252
    return ext, px, gate, rf, miss


def fin_events(ext, px, fac):
    """回傳 DataFrame(date, sid, strength)：新一期值出現那天（值與前一日不同），strength＝當日橫斷面百分位。"""
    vals = {}
    for sid, d in ext.items():
        v = pd.Series(attach_fin(d, sid, fac), index=pd.to_datetime(d["date"].astype(str).str[:10]))
        vals[sid] = v[~v.index.duplicated()]
    panel = pd.DataFrame(vals).sort_index()
    panel = panel[~panel.index.duplicated()].reindex(px.index).ffill()  # as-of 值往後帶，個股零星缺日不誤判成新公布
    pct = panel.rank(axis=1, pct=True)
    prev = panel.shift(1)
    new = panel.notna() & prev.notna() & panel.ne(prev)  # 歷史起點第一次出現的值不算事件
    s = pct.where(new).stack().dropna()
    return s.rename("strength").reset_index().rename(columns={"level_0": "date", "level_1": "sid"})


def high_events(px, W):
    # 逐檔在自己的有價日上滾（日期是全樣本聯集，個股零星缺日會讓 min_periods 數不滿而整段 NaN）
    hi = px.apply(lambda s: s.dropna().rolling(W, min_periods=W).max().reindex(s.index))
    at = (px >= hi - 1e-12) & hi.notna()
    prior = at.shift(1).rolling(20, min_periods=1).max().fillna(0).astype(bool)
    ev = at & ~prior
    strength = px.apply(lambda s: (s.dropna() / s.dropna().shift(W) - 1).reindex(s.index))  # 同日多筆：W 日漲幅大者優先
    s = strength.where(ev & strength.notna()).stack().dropna()
    return s.rename("strength").reset_index().rename(columns={"level_0": "date", "level_1": "sid"})


def _roc(s):
    y, m, d = s.split("/")
    return pd.Timestamp(int(y) + 1911, int(m), int(d))


def disp_events(px, repeat_only):
    rows = []
    for src in ("twse", "tpex"):
        j = json.loads((D / f"disposal_history_{src}.json").read_text(encoding="utf-8"))
        for yr, blk in j["years"].items():
            f = blk.get("fields", [])
            if not blk.get("data"):
                continue
            ic, ip = f.index("證券代號"), next(i for i, x in enumerate(f) if x.startswith("處置起"))
            icum = f.index("累計")
            for r in blk["data"]:
                sid = re.sub(r"\(.*", "", str(r[ic])).strip()
                if sid not in px.columns:
                    continue
                m = re.findall(r"(\d{2,3}/\d{2}/\d{2})", str(r[ip]))
                if len(m) < 2:
                    continue
                try:
                    cum = int(r[icum])
                except (TypeError, ValueError):
                    cum = 1
                if repeat_only and cum < 2:
                    continue
                endd = _roc(m[1])
                k = int(np.searchsorted(px.index, endd, side="right"))  # 解除後第一個交易日
                if k < len(px.index):
                    rows.append({"date": px.index[k], "sid": sid, "strength": float(cum)})
    ev = pd.DataFrame(rows).drop_duplicates(["date", "sid"])
    return ev


def buyback_events(px):
    """MOPS 庫藏股（本機 data/raw_mops_buyback/*.parquet，民國 104H1～114H1）：董事會決議日＝觀察日，strength＝預定買回總金額。"""
    import glob
    rows = []
    for f in glob.glob(str(D / "raw_mops_buyback" / "*.parquet")):
        x = pd.read_parquet(f)
        for _, r in x.iterrows():
            sid = str(r["stock_id"]).strip()
            if sid not in px.columns:
                continue
            try:
                dt = _roc(str(r["board_resolution_date"]).strip())
                amt = float(str(r["max_total_amount"]).replace(",", "") or 0)
            except (ValueError, TypeError):
                continue
            rows.append({"date": dt, "sid": sid, "strength": amt})
    ev = pd.DataFrame(rows).drop_duplicates(["date", "sid"])
    # 觀察日非交易日 → 歸到之後第一個交易日（sim 會在其下一個交易日收盤進場）
    k = np.searchsorted(px.index, ev["date"].to_numpy(), side="left")
    ev = ev[k < len(px.index)].copy()
    ev["date"] = px.index[k[k < len(px.index)]]
    return ev


def reduction_events(px, kind):
    """FinMind 減資恢復買賣參考價（本機快取，2003／2010 起～latest）：恢復買賣日事先公告，觀察日＝恢復日前一個交易日，
    sim 於恢復日收盤進場。kind：cash＝現金退還、loss＝彌補虧損。"""
    import glob
    fs = glob.glob(str(D / "raw" / "TaiwanStockCapitalReductionReferencePrice__*.parquet"))
    x = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    if x.empty:
        return pd.DataFrame(columns=["date", "sid", "strength"])
    x = x.drop_duplicates(["date", "stock_id"])
    want = "Cash" if kind == "cash" else "losses"
    x = x[x["ReasonforCapitalReduction"].astype(str).str.contains(want) & x["stock_id"].isin(px.columns)]
    rows = []
    for _, r in x.iterrows():
        k = int(np.searchsorted(px.index, pd.Timestamp(r["date"]), side="left"))
        if 1 <= k < len(px.index):
            rows.append({"date": px.index[k - 1], "sid": r["stock_id"], "strength": 1.0})
    return pd.DataFrame(rows)


def sim(px, ret, gate, rf, ev, H, nmax, use_gate, end=None):
    idx = px.index
    i0 = int(np.searchsorted(idx, pd.Timestamp(START)))
    i1 = len(idx) if end is None else int(np.searchsorted(idx, pd.Timestamp(end), side="right"))
    cols = {s: j for j, s in enumerate(px.columns)}
    R = ret.to_numpy()
    P = px.to_numpy()
    by_day = {}
    for d, g in ev.sort_values("strength", ascending=False).groupby("date", sort=False):
        by_day[d] = list(g["sid"])
    pos = []  # [col, value, exit_k]
    cash, eq, trades, wins = 1.0, np.ones(i1 - i0), 0, 0
    entry_val = {}
    for k, i in enumerate(range(i0, i1)):
        if k > 0:
            cash *= 1 + float(rf.iloc[i])
            for p in pos:
                r = R[i, p[0]]
                p[1] *= 1 + (0.0 if np.isnan(r) else r)
        # 出場（收盤）
        keep = []
        for p in pos:
            if i >= p[2]:
                r = R[i, p[0]]
                if (not np.isnan(r)) and r <= -LIMIT and i < p[2] + 5:
                    keep.append(p)
                    continue
                v = p[1] * (1 - SELL_C)
                cash += v
                trades += 1
                wins += v > entry_val.pop(id(p), v)
            else:
                keep.append(p)
        pos = keep
        V = cash + sum(p[1] for p in pos)
        # 進場（收盤）：事件日 d 的下一個交易日＝今天 i，故查 idx[i-1] 的事件
        if i - 1 >= 0 and ((not use_gate) or bool(gate.iloc[i])):
            for sid in by_day.get(idx[i - 1], []):
                if len(pos) >= nmax:
                    break
                c = cols.get(sid)
                if c is None or np.isnan(P[i, c]) or any(p[0] == c for p in pos):
                    continue
                r = R[i, c]
                if not np.isnan(r) and r >= LIMIT:
                    continue
                amt = min(V / nmax, cash)
                if amt <= 1e-9:
                    break
                cash -= amt
                p = [c, amt * (1 - BUY_C), i + H]
                entry_val[id(p)] = amt
                pos.append(p)
        eq[k] = cash + sum(p[1] for p in pos)
    return idx[i0:i1], eq, trades, wins / max(trades, 1)


def st(dates, c):
    yrs = (dates[-1] - dates[0]).days / 365.25
    r = np.diff(c) / c[:-1]
    sd = r.std()
    return {"cagr": float(c[-1] ** (1 / yrs) - 1) if c[-1] > 0 else -1.0,
            "mdd": float((c / np.maximum.accumulate(c) - 1).min()),
            "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0}


def seg(dates, c, a, b):
    m = (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))
    if m.sum() < 30:
        return None
    x = c[m] / c[m][0]
    return st(dates[m], x)


FAMS = [("E-rev", "月營收意外事件（monthly_revenue_event_study）"), ("E-eps", "EPS 意外事件（event_driven_sue／pead）"),
        ("E-52w", "52 週新高突破事件（f_52w_high_prox 事件版）"), ("E-disp", "處置股解除後（HQ#47／paper_10，只到 2024）"),
        ("E-buyback", "庫藏股決議（buyback_car／HQ#40，只到 2025-06）"), ("E-reduct", "減資恢復買賣（capital_reduction_car／#71）")]
HS = (5, 10, 21, 63)
NS = (10, 20)


def main(only=None):
    t0 = time.time()
    ext, px, gate, rf, miss = load()
    ret = px.apply(lambda s: s.dropna().pct_change().reindex(s.index))  # 逐檔有價日報酬，缺日不丟跨缺口報酬
    print(f"樣本 {px.shape[1]} 檔、{px.index[0].date()}～{px.index[-1].date()}（{time.time()-t0:.0f}s）", flush=True)
    out = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {"families": []}
    out["meta"] = {"cycle": "20261108-060101", "start": START, "end": str(px.index[-1].date()), "n_stocks": int(px.shape[1]),
                   "missing_2025": len(miss), "cost": {"buy": BUY_C, "sell": SELL_C}}
    done = {f["family"] for f in out["families"]}
    for fid, title in FAMS:
        if (only and fid not in only) or fid in done:
            continue
        if fid == "E-rev":
            base = fin_events(ext, px, "f_revenue_surprise")
            variants = {q: base[base["strength"] >= q] for q in (0.8, 0.9)}
        elif fid == "E-eps":
            base = fin_events(ext, px, "f_eps_surprise")
            variants = {q: base[base["strength"] >= q] for q in (0.8, 0.9)}
        elif fid == "E-52w":
            variants = {W: high_events(px, W) for W in (126, 252)}
        elif fid == "E-buyback":
            variants = {"all": buyback_events(px)}
        elif fid == "E-reduct":
            variants = {q: reduction_events(px, q) for q in ("cash", "loss")}
        else:
            variants = {"all": disp_events(px, False), "repeat": disp_events(px, True)}
        end = {"E-disp": "2024-12-31", "E-buyback": "2025-06-30"}.get(fid)
        rows = []
        for (q, ev), H, n, g in itertools.product(variants.items(), HS, NS, (False, True)):
            dates, eq, tr, wr = sim(px, ret, gate, rf, ev, H, n, g, end)
            rfa = rf.reindex(dates).to_numpy()
            for L, stop in itertools.product((1.0, 1.5, 2.0, 3.0), (None, 0.10, 0.15, 0.20)):
                c, n_stop = S.overlay(eq, rfa, L, stop)
                s = st(dates, c)
                rows.append({"q": q, "H": H, "N": n, "gate": g, "L": L, "stop": stop, **s, "trades": tr, "win_rate": wr,
                             "n_events": int(len(ev)), "n_stop": n_stop,
                             "seg_2015_2024": seg(dates, c, "2015-01-01", "2024-12-31"),
                             "seg_2025": seg(dates, c, "2025-01-01", "2026-12-31"),
                             "calmar": s["cagr"] / abs(s["mdd"]) if s["mdd"] < 0 else 0.0})
            print(f"{fid} q={q} H={H} N={n} gate={g} 交易 {tr}（累計 {time.time()-t0:.0f}s）", flush=True)
        ok = [r for r in rows if r["mdd"] > -0.5]
        best = max(ok or rows, key=lambda r: r["calmar"])
        best_l2 = max([r for r in ok if r["L"] <= 2.0] or rows, key=lambda r: r["calmar"])
        base1 = max([r for r in rows if r["L"] == 1.0 and r["stop"] is None and not r["gate"]], key=lambda r: r["calmar"])
        out["families"].append({"family": fid, "title": title, "n_cells": len(rows), "period_end": end or out["meta"]["end"],
                                "best": best, "best_L2": best_l2, "best_1x_plain": base1,
                                "violates_survival_cells": sum(r["mdd"] <= -0.5 for r in rows)})
        OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    render(out)
    print(f"完成 {time.time()-t0:.0f}s")


def _p(x):
    return "—" if x is None else f"{x*100:+.1f}%"


def render(out):
    m = out["meta"]
    lines = ["<!-- BATCH3-B7-BEGIN -->", "", "## 11. 第二批 第 7 批：事件類→事件後固定持有（DevQueue 20261108-060101）", "",
             f"樣本＝#133 抽樣 {m['n_stocks']} 檔（延長價格到 {m['end']}；2025 起缺價 {m['missing_2025']} 檔報酬記 0），期間 {m['start']}～{m['end']}"
             "（處置族只到 2024-12-31，本機處置清單只到 2024），參數用全期挑（含 2025 起，2025 起分段不是樣本外）。"
             "事件觀察日的**下一個交易日收盤進場**、持有 H 日收盤出場；進場日漲 ≥9.5% 視為買不到跳過、出場日跌 ≤−9.5% 延後賣；"
             f"槽位 N 檔、每筆＝淨值÷N，槽滿略過；閒置資金收無風險利率。成本：買 {m['cost']['buy']*100:.4f}%、賣 {m['cost']['sell']*100:.4f}%。",
             "q：E-rev／E-eps＝新值在當日橫斷面百分位門檻；E-52w＝新高窗口（日）；E-disp＝全部／只取再次處置。", "",
             "| 族 | 最佳組（Calmar，MDD 在 50% 內） | 年化 | MDD | Sharpe | 勝率 | 交易數 | 2015～2024 | 2025 起 | ≤2× 最佳 | 1× 無止損不擇時最佳 | 越線格數 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in out["families"]:
        b, b2, b1 = f["best"], f["best_L2"], f["best_1x_plain"]
        pr = f"q={b['q']}、持有 {b['H']} 日、N={b['N']}、{'大盤閘門' if b['gate'] else '不擇時'}、{b['L']}×、止損 {b['stop'] or '無'}"
        s1, s2 = b["seg_2015_2024"] or {}, b["seg_2025"] or {}
        lines.append(f"| {f['title']} | {pr} | {_p(b['cagr'])} | {_p(b['mdd'])} | {b['sharpe']:.2f} | {b['win_rate']*100:.0f}% | {b['trades']} | "
                     f"{_p(s1.get('cagr'))}／{_p(s1.get('mdd'))} | {_p(s2.get('cagr'))}／{_p(s2.get('mdd'))} | "
                     f"{b2['L']}× {_p(b2['cagr'])}／{_p(b2['mdd'])} | {_p(b1['cagr'])}／{_p(b1['mdd'])} | "
                     f"{f['violates_survival_cells']}／{f['n_cells']} |")
    lines += ["", "明細 `research/data/reaudit_batch3_batch7.json`。3× 超過融資上限只當參考。勝率＝出場淨值＞進場金額的比例（含成本）。",
              "**讀法提醒**：E-rev 2025 起 +100% 以上主要來自少數記憶體／PCB 股（2337、3037、6182、6446、8021 單筆 63 日 +117%～+275%），"
              "2025 起 q=0.9 事件 267 筆 63 日報酬中位數只有 +5.0%、平均 +16.3%，獲利高度集中，紙上要預期落差；"
              "庫藏股（164 筆）與減資（11 筆）在 236 檔抽樣裡事件太少、大多空手，Calmar 虛高、年化只有 1% 上下，不進候選（交易數 <100）；要做得改用全市場宇宙。"
              "月營收沒有公布時間的列 PIT＝次月 10 日（2025 起 159/267 筆落在 10 日）。E-eps 最佳組年化低（+6.6%）但回撤極小。",
              "**本批開發時抓到並修掉的錯（照實記錄）**：①pandas 3 的 `stack()` 保留 NaN，第一版把非事件列也當事件（73 萬筆）；"
              "②價格表日期是全樣本聯集，個股零星缺日讓 `rolling(min_periods=W)` 整段 NaN、`pct_change()` 丟掉跨缺口報酬，改成逐檔在自己有價日上算。"
              "②也影響第 6 批（`reaudit_batch6_portfolio.py` 用 `px.pct_change()`），本輪已修並重跑，第 10 節為修正後數字。",
              "", "<!-- BATCH3-B7-END -->"]
    block = "\n".join(lines)
    txt = MD.read_text(encoding="utf-8")
    if "<!-- BATCH3-B7-BEGIN -->" in txt:
        a = txt.index("<!-- BATCH3-B7-BEGIN -->")
        z = txt.index("<!-- BATCH3-B7-END -->") + len("<!-- BATCH3-B7-END -->")
        txt = txt[:a] + block + txt[z:]
    else:
        txt = txt.rstrip() + "\n\n" + block + "\n"
    MD.write_text(txt, encoding="utf-8")


def write_candidates():
    """Calmar ≥0.6（同第 6 批門檻）的族寫進候選欄，id 前綴 B7E-，rank_in_table 暫記 8；重跑只換自己的條目。"""
    from datetime import datetime
    out = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    d = json.loads(CAND.read_text(encoding="utf-8")) if CAND.exists() else {"candidates": []}
    keep = [c for c in d.get("candidates", []) if not str(c.get("id", "")).startswith("B7E-")]
    new = []
    for f in out["families"]:
        b = f["best"]
        if b["calmar"] < 0.6 or b["trades"] < 100:  # 〔自行裁量〕事件稀少、大多空手的族 Calmar 會虛高（減資 7 筆），交易數 <100 不進候選
            continue
        note = ["樣本內最優化（偏樂觀，參數用全期含 2025 起挑）", "#133 抽樣 236 檔事件後固定持有"]
        if b["L"] > 2:
            note.append(f"{b['L']:g}× 超過台股融資上限，紙上要改槓桿 ETF／期貨或降到 2× 以下")
        if f["family"] == "E-disp":
            note.append("處置清單只到 2024，紙上前要先接每日處置公告")
        new.append({"id": f"B7E-{f['family']}", "factor": f["family"], "source": "先.一五五-3 第二批第 7 批（事件類）",
                    "status": "候選（待 先.一五四 系列建每日訊號產生器才上紙上）", "rank_in_table": 8,
                    "params": {k: b[k] for k in ("q", "H", "N", "gate", "L", "stop")},
                    "backtest_period": f"{out['meta']['start']}～{f['period_end']}",
                    "backtest_2015_2024": {k: round(v, 4) for k, v in (b["seg_2015_2024"] or {}).items()},
                    "from_2025_same_params": {k: round(v, 4) for k, v in (b["seg_2025"] or {}).items()} or None,
                    "full_period_same_params": {"cagr": round(b["cagr"], 4), "mdd": round(b["mdd"], 4), "sharpe": round(b["sharpe"], 2),
                                                "win_rate": round(b["win_rate"], 3), "trades": b["trades"]},
                    "violates_survival_extended": False, "notes": "；".join(note)})
    d["candidates"] = sorted(keep + new, key=lambda c: c["rank_in_table"])
    d["generated_at"] = datetime.now().isoformat(timespec="seconds")
    CAND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"候選欄新增 {len(new)} 支：" + "、".join(c["factor"] for c in new) + f"；總數 {len(d['candidates'])}")


if __name__ == "__main__":
    if sys.argv[1:] == ["candidates"]:
        write_candidates()
    else:
        main(set(sys.argv[1:]) or None)
