# -*- coding: utf-8 -*-
"""先.一五八-1（收件匣 042 A，已定案（Cowork 收件匣 042））紙上優化軌 F3／F5／F2＋「F3＋F5 各半」每日產生器——零外部請求。

參數照 REAUDIT_OPTIMIZED.md §3「①原最優組不重調」，這裡不調參；算法逐條照 research/reaudit_optimized_batch1.py simulate()：
  F3 0050 趨勢槓桿：前一日 0050 含息價位 > 50 日均線 → 0050 曝險 1，否則 0.5；3×（3r−2rf−1%/年）、其餘領無風險；
     每天回到目標權重；帳戶自持倉高點回撤 10% → 0050 腿清空 21 個交易日。
  F5 已實現波動度 regime：前一日 60 日報酬標準差 > 自己 expanding 中位數（至少 252 筆）→ 曝險 0.25，否則 1；1×、無停損。
  F2 危機閘門 Bb-90：上個月底 0050 價位 > 近 6 個月底均值 → 股票 0.85（0050 與 VTI 各半），否則 0；其餘 IEF；1×；
     權重漂移、月初或目標改變才再平衡；帳戶回撤 10% → 股票腿轉現金 21 個交易日。美股腿照實換匯（data/fx 牌告）、匯兌 0.3%。
  F3F5：起跑日 F3、F5 各投一半，之後不再平衡（各自帳戶照上面跑）。
成本：台股腿 |Δw|×(滑價 0.1%＋手續費 0.1425%×6 折)，賣出另加 ETF 證交稅 0.1%；美股腿 |Δw|×0.3%。起跑第一天照實付建倉成本。
訊號日曆（忠於回測）：回測用「台股∪美股交易日」聯集日曆（美股單獨開市日 0050 報酬記 0），均線／波動視窗都在這個日曆上算。
  2026-10-05 以前讀種子 research/data/paper_opt/f5_vol_seed.json（paper_opt_regime_seed.py 用 batch1 同一份資料產生，
  三條回測 2025 起段與 REAUDIT §3 表逐位對上）；之後＝paper_opt_f12 的 0050 日線（data/price_history）∪ us_returns.json 的美股日期。
記帳日曆：只在台股交易日記帳。〔自行裁量〕回測在美股單獨開市日也扣槓桿成本、冷卻天數也按聯集日計；紙上只按台股交易日，差異照實揭露。
F2 的美股日報酬取「上一個台股交易日之後～當天」的美股交易日連乘，要等當天美股收盤（台北隔天清晨）才記，所以 F2 會晚一天入帳；
  缺 VTI／IEF 報酬（research/fetch_paper_opt_us_prices.py 尚未抓到）就停在那一天、下次再補，不拿 0 頂替。
輸出（append-only，只在本機）：research/data/paper_opt/ledger_{F3,F5,F2,F3F5}.jsonl、state_regime.json；起跑日 2026-11-11、不倒填。
用法：python research/paper_opt_regime.py [--probe]
非投資建議。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_opt_f12 as F12  # noqa: E402  （共用 0050 日線快取、無風險利率、讀寫工具）

OUT = F12.OUT
STATE = OUT / "state_regime.json"
SEED = OUT / "f5_vol_seed.json"
US = OUT / "us_returns.json"
START = "2026-11-11"
SLIP, BROKER, ETF_TAX, FX_COST, FEE_LEV, COOLDOWN = 0.001, 0.001425 * 0.6, 0.001, 0.003, 0.01, 21
RISKY = {"0050", "VTI"}
SPEC = {
    "F3": {"assets": ["0050", "CASH"], "L": 3.0, "stop": 0.10, "monthly": False},
    "F5": {"assets": ["0050", "CASH"], "L": 1.0, "stop": None, "monthly": False},
    "F2": {"assets": ["0050", "VTI", "IEF", "CASH"], "L": 1.0, "stop": 0.10, "monthly": True},
}


# ───────── 聯集日曆上的 0050 報酬（訊號用） ─────────
def union_series(b50: dict, us_dates: list[str]) -> tuple[list[str], list[float]]:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    ds, rs = list(seed["dates"]), list(seed["r_0050"])
    end = seed["end"]
    tw = {d: (b50[d][4] or 0.0) for d in b50 if d > end}
    for d in sorted(set(tw) | {d for d in us_dates if d > end}):
        ds.append(d)
        rs.append(tw.get(d, 0.0))
    return ds, rs


def levels(rs: list[float]) -> list[float]:
    out, x = [], 1.0
    for r in rs:
        x *= 1.0 + r
        out.append(x)
    return out


def sig_f3(px: list[float], i: int) -> float:
    """第 i 個聯集日收盤的訊號（下一日生效）：價位 > 50 日均線 → 1，否則 0.5；不足 50 筆視為 1（同 ma_signal）。"""
    if i + 1 < 50:
        return 1.0
    ma = sum(px[i - 49:i + 1]) / 50.0
    return 1.0 if px[i] > ma else 0.5


def vol_hist(rs: list[float]) -> list[float | None]:
    """60 日報酬標準差（ddof=1，同 pandas rolling().std()）。"""
    out: list[float | None] = []
    for i in range(len(rs)):
        if i + 1 < 60:
            out.append(None)
            continue
        w = rs[i - 59:i + 1]
        m = sum(w) / 60.0
        out.append((sum((x - m) ** 2 for x in w) / 59.0) ** 0.5)
    return out


def sig_f5(vols: list, i: int) -> float:
    """expanding 中位數（含當天、至少 252 筆）；中位數不存在 → 1（同 vol_signal）。"""
    hist = sorted(v for v in vols[:i + 1] if v is not None)
    if len(hist) < 252 or vols[i] is None:
        return 1.0
    n = len(hist)
    med = hist[n // 2] if n % 2 else (hist[n // 2 - 1] + hist[n // 2]) / 2.0
    return 0.25 if vols[i] > med else 1.0


def gate_f2(ds: list[str], px: list[float], before: str) -> float:
    """最近一個「已結束月份」月底（聯集日曆該月最後一天）價位 > 含當月在內近 6 個月底均值 → 1；不足 6 個月 → 1（同 month_ma_signal）。"""
    me: dict[str, float] = {}
    for d, p in zip(ds, px):
        if d[:7] < before[:7]:
            me[d[:7]] = p
    vals = [me[k] for k in sorted(me)]
    if len(vals) < 6:
        return 1.0
    return 1.0 if vals[-1] > sum(vals[-6:]) / 6.0 else 0.0


# ───────── 帳戶一日（逐條照 batch1 simulate() 迴圈本體） ─────────
def side_cost(a: str, dw: float) -> float:
    if a in ("VTI", "IEF"):
        return abs(dw) * FX_COST
    if a == "CASH":
        return 0.0
    c = abs(dw) * (SLIP + BROKER)
    if dw < 0:
        c += abs(dw) * ETF_TAX
    return c


def step(s: dict, sp: dict, target: dict, rets: dict, new_month: bool) -> tuple[float, float, str | None]:
    assets = sp["assets"]
    t = {a: float(target.get(a, 0.0)) for a in assets}
    raw = dict(t)
    if s["cool"] > 0:
        s["cool"] -= 1
        moved = sum(t[a] for a in assets if a in RISKY)
        for a in assets:
            if a in RISKY:
                t[a] = 0.0
        t["CASH"] += moved
    w = s["w"]
    changed = s.get("last_target") is None or sum(abs(raw[a] - s["last_target"].get(a, 0.0)) for a in assets) > 1e-12
    rebalance = (not sp["monthly"]) or new_month or changed or s["cool"] > 0 or not any(w.values())
    s["last_target"] = raw
    cost = 0.0
    if rebalance:
        cost = sum(side_cost(a, t[a] - w.get(a, 0.0)) for a in assets)
        w = dict(t)
    in_pos = any(w[a] > 0 for a in assets if a in RISKY)
    g = {a: w[a] * (1.0 + rets[a]) for a in assets}
    tot = sum(g.values()) if sum(w.values()) > 0 else 1.0
    r = (tot - 1.0) - cost
    if s["eq"] <= 0:
        r = 0.0
    s["eq"] = max(s["eq"] * (1.0 + r), 0.0)
    s["w"] = {a: (g[a] / tot if tot > 0 else 0.0) for a in assets}
    s["peak"] = max(s["peak"], s["eq"]) if in_pos else s["eq"]
    evt = None
    if sp["stop"] is not None and in_pos and s["eq"] < s["peak"] * (1.0 - sp["stop"]):
        s["cool"], s["peak"], evt = COOLDOWN, s["eq"], "account_stop"
    return r, cost, evt


def lev(r: float, L: float, rf: float) -> float:
    x = L * r - (L - 1.0) * rf
    return x - FEE_LEV / 252.0 if L > 1 else x


def fx_at(fx: dict, day: str):
    ks = [k for k in fx if k <= day]
    return fx[max(ks)] if ks else None


def us_ret(us: dict, tk: str, prev: str, day: str) -> float | None:
    """(prev, day] 之間美股交易日的 USD 報酬連乘；任一天缺該檔就回 None（不拿 0 頂替）。"""
    x = 1.0
    for d in sorted(k for k in us["returns"] if prev < k <= day):
        v = us["returns"][d].get(tk)
        if v is None:
            return None
        x *= 1.0 + float(v)
    return x - 1.0


def _append(fid: str, rec: dict) -> None:
    with (OUT / f"ledger_{fid}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def new_acct() -> dict:
    return {"eq": 1.0, "peak": 1.0, "cool": 0, "w": {}, "last_target": None, "last_date": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--start", default=START)  # 只給自測用（暫存目錄），正式帳不得改
    a = ap.parse_args()
    # 只讀 F12 的日線快取，不呼叫 F12.build_bars()：那支會把共用日曆往前推，只帶 0050 呼叫會讓 F12／F11 當天其他股票缺價。
    # 所以 run_paper_opt.py 要排在 f11／f12 之後跑（快取已更新）。
    cache = F12._rj(F12.BARS, {"bars": {}, "calendar": []})
    bars, calendar = cache["bars"], sorted(cache["calendar"])
    b50 = bars.get("0050", {})
    us = F12._rj(US, None) or {"returns": {}, "fx_usd_twd": {}}
    us_dates = sorted(us.get("returns", {}))
    ds, rs = union_series(b50, us_dates)
    px = levels(rs)
    vols = vol_hist(rs)
    idx = {d: i for i, d in enumerate(ds)}
    rf = F12.rf_daily()
    fx = us.get("fx_usd_twd", {})

    def signals(day: str) -> dict:
        prev_u = max((d for d in ds if d < day), default=None)
        i = idx[prev_u]
        return {"F3": sig_f3(px, i), "F5": sig_f5(vols, i), "F2": gate_f2(ds, px, day), "from": prev_u}

    if a.probe:
        day = calendar[-1]
        print(f"聯集日曆 {len(ds)} 天（至 {ds[-1]}），{day} 適用訊號：{signals(day)}；美股最新 {us_dates[-1] if us_dates else '—'}；"
              f"VTI/IEF 在美股檔裡：{bool(us_dates) and 'VTI' in us['returns'][us_dates[-1]]}/{bool(us_dates) and 'IEF' in us['returns'][us_dates[-1]]}")
        return 0
    s = F12._rj(STATE, None) or {"start": a.start, **{k: new_acct() for k in ("F3", "F5", "F2")}}
    if a.start != START:
        s["start"] = a.start
    done = {k: 0 for k in SPEC}
    for i, day in enumerate(calendar):
        if day < s["start"] or i == 0:
            continue
        prev = calendar[i - 1]
        if day not in b50:
            print(f"[warn] {day} 沒有 0050 價格，停在這天")
            break
        sg = signals(day)
        r50 = b50[day][4] or 0.0
        new_month = prev[:7] != day[:7]
        for fid in ("F3", "F5"):
            acc = s[fid]
            if acc["last_date"] and day <= acc["last_date"]:
                continue
            e = sg[fid]
            sp = SPEC[fid]
            r, cost, evt = step(acc, sp, {"0050": e, "CASH": 1.0 - e}, {"0050": lev(r50, sp["L"], rf), "CASH": rf}, new_month)
            _append(fid, {"date": day, "ret": round(r, 8), "account": round(acc["eq"], 8), "target_0050": e,
                          "signal_from": sg["from"], "r_0050": round(r50, 6), "cost": round(cost, 6),
                          "account_event": evt, "cooldown_left": acc["cool"]})
            acc["last_date"] = day
            done[fid] += 1
        # F3F5：兩邊都記到這天才合成（起跑各半、不再平衡＝兩個帳戶權益平均）
        if s["F3"]["last_date"] == day and s["F5"]["last_date"] == day and s.get("F3F5_last") != day:
            prev_c = s.get("F3F5_eq", 1.0)
            cur = 0.5 * s["F3"]["eq"] + 0.5 * s["F5"]["eq"]
            _append("F3F5", {"date": day, "ret": round(cur / prev_c - 1.0, 8), "account": round(cur, 8),
                             "F3_account": round(s["F3"]["eq"], 8), "F5_account": round(s["F5"]["eq"], 8)})
            s["F3F5_eq"], s["F3F5_last"] = cur, day
        # F2：要等當天美股收盤（VTI／IEF 報酬）才記
        acc = s["F2"]
        if not (acc["last_date"] and day <= acc["last_date"]) and acc.get("blocked") is None:
            rv, ri = us_ret(us, "VTI", prev, day), us_ret(us, "IEF", prev, day)
            covered = bool(us_dates) and us_dates[-1] >= day
            f1, f0 = fx_at(fx, day), fx_at(fx, prev)
            if not covered or rv is None or ri is None or not (f1 and f0):
                acc["blocked"] = day
                print(f"[info] F2 {day}：美股報酬或匯率還沒到（美股最新 {us_dates[-1] if us_dates else '—'}），下次再補")
            else:
                ratio = f1 / f0
                g = sg["F2"]
                tgt = {"0050": 0.425 * g, "VTI": 0.425 * g, "IEF": 1.0 - 0.85 * g, "CASH": 0.0}
                rets = {"0050": r50, "VTI": (1 + rv) * ratio - 1.0, "IEF": (1 + ri) * ratio - 1.0, "CASH": rf}
                r, cost, evt = step(acc, SPEC["F2"], tgt, rets, new_month)
                _append("F2", {"date": day, "ret": round(r, 8), "account": round(acc["eq"], 8), "gate": g,
                               "r_0050": round(r50, 6), "r_vti_usd": round(rv, 6), "r_ief_usd": round(ri, 6),
                               "fx_ratio": round(ratio, 6), "cost": round(cost, 6), "account_event": evt,
                               "cooldown_left": acc["cool"]})
                acc["last_date"] = day
                done["F2"] += 1
    s["F2"].pop("blocked", None)
    F12._wj(STATE, s)
    print(f"本次寫入 {done}；F3F5 至 {s.get('F3F5_last')}（起跑 {s['start']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 十二節：自身失敗只印警告、exit 0
        import traceback
        traceback.print_exc()
        print(f"[warn] paper_opt_regime 失敗：{e}")
        sys.exit(0)
