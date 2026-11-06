# -*- coding: utf-8 -*-
"""先.一五四-1a ③ 紙上優化軌 PQ（恐慌×PQ 最優組）每日訊號產生器——研究帽產物，零外部請求。

策略（照 research/PANIC_PQ_OPTIMIZED.md 2 節最優組，機制照 research/panic_pq_backtest.py，這裡不調參）：
  θ=20%（當天上市櫃 4 碼普通股「收盤鎖跌停」檔數 ÷ 有成交檔數）、20 個交易日內只算第一次觸發、
  持有中的觸發跳過；觸發日收盤後用 PQ strict 名單＋高峰濾網、依單季營益率年增排序取前 20 檔，
  隔 1 個交易日開盤買進（鎖漲跌停／停牌順延，超過出場日取消），持有 120 個交易日，
  收盤報酬 ≤ −15% 停損，1× 不槓桿；名單不足 20 檔的部分留現金。平時空手（日報酬 0）。
成本：沿用回測同一組常數（手續費 0.1425%、證交稅 0.3%、滑價 0.05%，1×），讓紙上與回測是同一個策略。

資料（全部本機、每日排程更新的檔）：
  - 恐慌指標：data/price_history/b*.json（每日）。本機沒有官方參考價欄，
    用 adj_close 日報酬近似「收盤÷參考價−1」（除權息日由還原價吸收）；回測版用 FinMind spread，口徑略不同，照實標註。
  - 季報：data/stock_detail.json financials.quarters（每日排程，TWSE/TPEx 官方）＋ data/financials_backfill.json；
    高峰濾網要近 20 季毛利率百分位（至少 8 季），2024 以前的季另讀本機 research/data/raw FinMind 快取（有才讀）。
  - 月營收：data/fundamentals.json month_revenue（每日排程）＋ data/revenue_backfill.json。
  - 可得日同回測：Q1→05-15、Q2→08-31、Q3→11-14、Q4→次年 04-30；月營收＝次月 10 日。

輸出（append-only，已寫過的日期不改）：
  research/data/paper_opt/ledger_PQ.jsonl  每個交易日一行（起跑日 2026-11-09 起）
  research/data/paper_opt/state_PQ.json    持有狀態／觸發計數（事件名單一旦定下就凍結）
用法：python research/paper_opt_pq.py            每日跑（只處理還沒寫過的交易日）
      python research/paper_opt_pq.py --probe    只印近期恐慌指標＋「假設今天觸發」的名單，不寫檔
非投資建議。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
OUT = HERE / "data" / "paper_opt"
LEDGER = OUT / "ledger_PQ.jsonl"
STATE = OUT / "state_PQ.json"
RAW = HERE / "data" / "raw"
GM_CACHE = OUT / "gm_hist_pre2025.json"

START = "2026-11-09"
THETA, MERGE_DAYS, N, H, SL = 0.20, 20, 20, 120, -0.15
LIMIT, TOL = 0.10, 0.006
FEE, TAX, SLIP = 0.001425, 0.003, 0.0005
BUY_C, SELL_C = FEE + SLIP, FEE + TAX + SLIP
STRICT = dict(gm=2, om=2, rev=0.25, eps=0.30, ttm=10)
Q_AVAIL = {1: "05-15", 2: "08-31", 3: "11-14", 4: "04-30"}
STOCK_RE = re.compile(r"^[1-9]\d{3}$")
MIN_TRADED = 1000  # 少於 1000 檔有成交的日子不算完整交易日（全市場約 1,950 檔）〔自行裁量〕
GONE_DAYS = 10  # 連續 10 個交易日沒有價格視為下市／長期停牌，以最後價值出場〔自行裁量〕


# ------------------------------------------------------------------ 價格
def load_prices() -> dict[str, dict[str, dict]]:
    """回傳 {代號: {日期: bar}}，只留 4 碼普通股。"""
    out: dict[str, dict[str, dict]] = {}
    for f in sorted(glob.glob(str(DATA / "price_history" / "b*.json"))):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))["prices"]
        except Exception as e:  # 單一分片壞掉只略過，記警告
            print(f"[warn] 讀不到 {f}：{e}")
            continue
        for sid, rows in d.items():
            if STOCK_RE.match(sid):
                out[sid] = {r["date"]: r for r in rows if r.get("date")}
    return out


def daily_panel(px: dict) -> tuple[list[str], dict[str, dict]]:
    """每日恐慌指標＋每檔每日 (ret, locked)。回傳 (交易日曆, {日期: 指標})。"""
    stats: dict[str, dict] = {}
    for sid, bars in px.items():
        prev = None
        for dt in sorted(bars):
            b = bars[dt]
            vol = b.get("volume") or 0
            if vol <= 0 or not b.get("close"):
                continue
            s = stats.setdefault(dt, {"n_traded": 0, "n_limit_down": 0, "n_limit_up": 0})
            s["n_traded"] += 1
            if prev is not None and prev.get("adj_close") and b.get("adj_close"):
                r = b["adj_close"] / prev["adj_close"] - 1
                if r <= -(LIMIT - TOL) and b["close"] <= (b.get("low") or 0) + 1e-9:
                    s["n_limit_down"] += 1
                if r >= (LIMIT - TOL) and b["close"] >= (b.get("high") or 0) - 1e-9:
                    s["n_limit_up"] += 1
            prev = b
    cal = sorted(stats)
    # 去掉還沒抓齊的日子（有成交檔數 < 近 20 日中位數 × 0.8），避免盤後半套資料被當成交易日
    full = []
    for i, dt in enumerate(cal):
        ref = sorted(stats[x]["n_traded"] for x in cal[max(0, i - 20):i]) or [0]
        med = ref[len(ref) // 2]
        if stats[dt]["n_traded"] >= max(MIN_TRADED, 0.8 * med):
            full.append(dt)
    for dt in full:
        s = stats[dt]
        s["frac_limit_down"] = s["n_limit_down"] / s["n_traded"]
    return full, stats


def bar_info(px: dict, sid: str, dt: str):
    """回傳 (有價, ratio 前一筆→今天 adj_close, open, close, locked)。"""
    bars = px.get(sid, {})
    b = bars.get(dt)
    if not b or not (b.get("volume") or 0) > 0 or not b.get("close"):
        return False, None, None, None, False
    prev_dates = [x for x in bars if x < dt]
    ratio = None
    if prev_dates:
        p = bars[max(prev_dates)]
        if p.get("adj_close") and b.get("adj_close"):
            ratio = b["adj_close"] / p["adj_close"]
    locked = (b.get("high") == b.get("low")) and ratio is not None and abs(ratio - 1) >= LIMIT - TOL
    return True, ratio, b.get("open"), b["close"], locked


# ------------------------------------------------------------------ PQ 名單
def _avail_q(y: int, q: int) -> str:
    return f"{y + 1 if q == 4 else y}-{Q_AVAIL[q]}"


def _raw_gm_history() -> dict[str, dict[tuple[int, int], float]]:
    """2024 以前的單季毛利率（%），只給高峰濾網的近 20 季百分位用；沒有本機快取就回空。"""
    out: dict[str, dict] = {}
    if GM_CACHE.exists():  # 2024 以前的季報不會再變，算一次就存（本機，不進 repo）
        try:
            c = json.loads(GM_CACHE.read_text(encoding="utf-8"))
            return {sid: {(int(k[:4]), int(k[5])): v for k, v in d.items()} for sid, d in c.items()}
        except Exception as e:
            print(f"[warn] 毛利率快取壞掉，重算：{e}")
    files = list(RAW.glob("TaiwanStockFinancialStatements__*.parquet"))
    if not files:
        return out
    bad = 0
    try:
        import pandas as pd
    except Exception as e:
        print(f"[warn] 沒有 pandas，高峰濾網只用近期季報：{e}")
        return out
    for p in files:
        sid = p.name.split("__")[1]
        if not STOCK_RE.match(sid):
            continue
        try:
            f = pd.read_parquet(p, columns=["date", "type", "value"])
        except Exception:  # 空檔（FinMind 回 0 列存成無欄位 parquet）只計數，最後印一行
            bad += 1
            continue
        f = f[f["type"].isin(["Revenue", "GrossProfit"]) & (f["date"] <= "2024-12-31")]
        w = f.pivot_table(index="date", columns="type", values="value", aggfunc="last")
        if not {"Revenue", "GrossProfit"} <= set(w.columns):
            continue
        for dt, r in w.iterrows():
            m = int(dt[5:7])
            if m in (3, 6, 9, 12) and r["Revenue"] and r["Revenue"] > 0:
                out.setdefault(sid, {})[(int(dt[:4]), m // 3)] = r["GrossProfit"] / r["Revenue"] * 100
    print(f"[info] 2024 以前季報快取 {len(files)} 檔、讀不到（多為空檔）{bad} 檔、有毛利率 {len(out)} 檔")
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        GM_CACHE.write_text(json.dumps({sid: {f"{y}Q{q}": round(v, 4) for (y, q), v in d.items()} for sid, d in out.items()}),
                            encoding="utf-8")
    except Exception as e:
        print(f"[warn] 毛利率快取寫不進去（不影響本次結果）：{e}")
    return out


def _quarters() -> dict[str, dict[tuple[int, int], dict]]:
    q: dict[str, dict] = {}
    for path, getter in ((DATA / "financials_backfill.json", lambda d: d.get("stocks", {})),
                         (DATA / "stock_detail.json", lambda d: {k: (v.get("financials") or {}).get("quarters") or []
                                                                 for k, v in d.get("stocks", {}).items()})):
        try:
            src = getter(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[warn] 讀不到 {path.name}：{e}")
            continue
        for sid, rows in src.items():  # 後讀的 stock_detail（每日官方）覆蓋回補
            for r in rows or []:
                if r.get("year") and r.get("quarter"):
                    q.setdefault(sid, {})[(int(r["year"]), int(r["quarter"]))] = r
    return q


def _revenues() -> dict[str, dict[int, float]]:
    rv: dict[str, dict] = {}
    for path, key in ((DATA / "revenue_backfill.json", "stocks"), (DATA / "fundamentals.json", "fundamentals")):
        try:
            src = json.loads(path.read_text(encoding="utf-8")).get(key, {})
        except Exception as e:
            print(f"[warn] 讀不到 {path.name}：{e}")
            continue
        for sid, v in src.items():
            rows = v if isinstance(v, list) else (v.get("month_revenue") or [])
            for r in rows:
                if r.get("year") and r.get("month") and r.get("revenue") is not None:
                    rv.setdefault(sid, {})[int(r["year"]) * 100 + int(r["month"])] = r["revenue"]
    return rv


def _rev_pub(ym: int) -> str:
    y, m = divmod(ym, 100)
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y2}-{m2:02d}-10"


def pq_list(dt: str, px: dict, gm_old=None) -> tuple[list[str], dict]:
    """事件日 dt 收盤後可得的 PQ strict＋peak 名單（依營益率年增排序，前 N 檔）。"""
    qs, rvs = _quarters(), _revenues()
    if gm_old is None:
        gm_old = _raw_gm_history()
    cut = (date.fromisoformat(dt) - timedelta(days=200)).isoformat()
    cands, diag = [], {"q_stocks": len(qs), "rev_stocks": len(rvs), "fresh": 0, "pass_rules": 0, "peak_removed": 0,
                       "gm_pct_missing": 0}
    for sid, qq in qs.items():
        if not STOCK_RE.match(sid):
            continue
        ok_q = [k for k in qq if _avail_q(*k) <= dt]
        if not ok_q:
            continue
        y, q = max(ok_q)
        if _avail_q(y, q) < cut:
            continue
        diag["fresh"] += 1
        cur, ly = qq[(y, q)], qq.get((y - 1, q))
        if not ly:
            continue
        try:
            gm_pp = cur["gross_margin_pct"] - ly["gross_margin_pct"]
            om_pp = cur["op_margin_pct"] - ly["op_margin_pct"]
            eps, eps_ly = cur["eps"], ly["eps"]
            ttm_keys = [(y, q)]
            yy, qn = y, q
            for _ in range(3):
                yy, qn = (yy - 1, 4) if qn == 1 else (yy, qn - 1)
                ttm_keys.append((yy, qn))
            if not all(k in qq and qq[k].get("eps") is not None for k in ttm_keys):
                continue
            eps_ttm = sum(qq[k]["eps"] for k in ttm_keys)
        except (TypeError, KeyError):
            continue
        if None in (gm_pp, om_pp, eps, eps_ly):
            continue
        eps_yoy = eps / eps_ly - 1 if eps_ly > 0 else None
        rv = rvs.get(sid, {})
        pub = sorted(k for k in rv if _rev_pub(k) <= dt)
        rev3 = None
        if len(pub) >= 3:
            last3 = pub[-3:]
            ly3 = [k - 100 for k in last3]
            if all(k in rv for k in ly3) and sum(rv[k] for k in ly3) > 0:
                rev3 = sum(rv[k] for k in last3) / sum(rv[k] for k in ly3) - 1
        if eps_yoy is None or rev3 is None:
            continue
        if not (gm_pp >= STRICT["gm"] and om_pp >= STRICT["om"] and rev3 >= STRICT["rev"]
                and eps_yoy >= STRICT["eps"] and eps_ttm >= STRICT["ttm"]):
            continue
        b = px.get(sid, {}).get(dt)
        if not b or not b.get("close"):
            continue  # 事件日沒有價格（同回測：不在價格宇宙不選）
        diag["pass_rules"] += 1
        # 高峰濾網：單季毛利率在自身近 20 季（含本季、至少 8 季）排名前 10%，且 TTM EPS÷收盤 > 20% → 排除
        hist = dict(gm_old.get(sid, {}))
        hist.update({k: v["gross_margin_pct"] for k, v in qq.items() if v.get("gross_margin_pct") is not None})
        keys = sorted(k for k in hist if k <= (y, q))[-20:]
        if len(keys) >= 8:
            prior = [hist[k] for k in keys[:-1]]
            pct = sum(1 for v in prior if v < hist[(y, q)]) / len(prior)
            if pct >= 0.9 and eps_ttm / b["close"] > 0.20:
                diag["peak_removed"] += 1
                continue
        else:
            diag["gm_pct_missing"] += 1  # 同回測：百分位算不出來就不排除
        cands.append((om_pp, sid))
    cands.sort(reverse=True)
    return [s for _, s in cands[:N]], diag


# ------------------------------------------------------------------ 狀態機
def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"days_since_trigger": 10**6, "holding": None, "last_date": None}


def step(dt: str, s: dict, panel: dict, px: dict) -> dict:
    p = panel[dt]
    rec = {"date": dt, "member": "PQ", "ret": 0.0, "invested": 0.0, "event": False,
           "frac_limit_down": round(p["frac_limit_down"], 4), "n_limit_down": p["n_limit_down"],
           "n_traded": p["n_traded"], "positions": 0, "note": ""}
    s["days_since_trigger"] += 1
    trig = p["frac_limit_down"] >= THETA and s["days_since_trigger"] > MERGE_DAYS
    if trig:  # 20 日合併照算，不論是否持有中（同回測：事件清單先算、持有中的事件才跳過）
        s["days_since_trigger"] = 0
    hold = s["holding"]
    if hold:
        hold["days"] += 1
        tot = 0.0
        for pos in hold["positions"]:
            if pos["done"]:
                tot += pos["cash"]
                continue
            has, ratio, op, cl, locked = bar_info(px, pos["sid"], dt)
            tradable = has and not locked and (op or 0) > 0
            pos["missing"] = 0 if has else pos.get("missing", 0) + 1
            if pos["sh"] > 0 and has and ratio is not None:
                pos["sh"] *= ratio
            if pos["pending"] and hold["days"] <= H and tradable:
                pos["cash"] -= 1.0
                pos["basis"] = 1.0
                pos["sh"] = (1 - BUY_C) * cl / op
                pos["pending"] = False
                pos["entry_date"] = dt
            if hold["days"] >= H:
                pos["pending"] = False
            hit = pos["sh"] > 0 and not pos["pending"] and pos["sh"] / pos["basis"] - 1 <= SL
            gone = pos["missing"] >= GONE_DAYS
            if pos["sh"] > 0 and (((hold["days"] >= H or hit) and tradable) or gone):
                pos["cash"] += pos["sh"] * (1 - SELL_C)
                pos["sh"] = 0.0
                pos["exit_date"], pos["exit_reason"] = dt, ("停損" if hit else "下市或停牌" if gone else "到期")
            if pos["sh"] == 0 and not pos["pending"]:
                pos["done"] = True
            tot += pos["cash"] + pos["sh"]
        tot = (tot + (N - len(hold["positions"]))) / N
        rec["ret"] = round(tot / hold["prev_tot"] - 1, 8)
        hold["prev_tot"] = tot
        live = [x for x in hold["positions"] if not x["done"]]
        rec["positions"] = len(live)
        rec["invested"] = round(len(live) / N, 4)
        if not live:
            rec["note"] = f"事件 {hold['event_date']} 部位全部出場"
            s.setdefault("closed", []).append(hold)
            s["holding"] = None
        if trig:
            rec["note"] = (rec["note"] + "；" if rec["note"] else "") + "恐慌觸發但持有中，跳過（同回測 busy_until）"
            rec["event"] = True
        return rec
    if trig:
        rec["event"] = True
        picks, diag = pq_list(dt, px)
        rec["note"] = f"恐慌觸發；PQ 名單 {len(picks)} 檔：{','.join(picks) or '（名單空，維持空手）'}"
        rec["list_diag"] = diag
        if picks:
            s["holding"] = {"event_date": dt, "days": 0, "prev_tot": 1.0, "picks": picks,
                            "positions": [{"sid": x, "cash": 1.0, "sh": 0.0, "basis": 0.0, "pending": True,
                                           "done": False, "missing": 0} for x in picks]}
    elif p["frac_limit_down"] >= THETA:
        rec["note"] = "鎖跌停比例達門檻，但距上次觸發未滿 20 個交易日（合併，不算新事件）"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    px = load_prices()
    cal, panel = daily_panel(px)
    print(f"價格 {len(px)} 檔、完整交易日 {len(cal)} 天（{cal[0] if cal else '-'}～{cal[-1] if cal else '-'}）")
    if a.probe:
        for dt in cal[-15:]:
            p = panel[dt]
            print(f"{dt} 有成交 {p['n_traded']} 鎖跌停 {p['n_limit_down']}（{p['frac_limit_down']:.2%}） 鎖漲停 {p['n_limit_up']}")
        top = sorted(cal, key=lambda d: -panel[d]["frac_limit_down"])[:5]
        print("期間鎖跌停比例最高 5 天：", [(d, f"{panel[d]['frac_limit_down']:.2%}") for d in top])
        picks, diag = pq_list(cal[-1], px)
        print(f"假設 {cal[-1]} 觸發：名單 {len(picks)} 檔 {picks}；診斷 {diag}")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    s = _load_state()
    todo = [d for d in cal if d >= START and (s["last_date"] is None or d > s["last_date"])]
    if not todo:
        print(f"沒有新的交易日要寫（起跑日 {START}，上次寫到 {s['last_date']}）")
        return 0
    with LEDGER.open("a", encoding="utf-8") as fh:
        for dt in todo:
            rec = step(dt, s, panel, px)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            s["last_date"] = dt
            print(f"{dt} 報酬 {rec['ret']:+.4%} 持股 {rec['positions']} 鎖跌停 {rec['frac_limit_down']:.2%} {rec['note']}")
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
