# -*- coding: utf-8 -*-
"""先.九十四-5b：權證隱含波動反推（Black-Scholes，二分法）。供 B2 前置，只描述、不回測、不登記試驗。

模型假設（照實寫）：
- 歐式 Black-Scholes、不含股利（標的預期股利尚未接入；美式認購在不配息時與歐式同價，美式認售會略低估）。
- 權證價格 ＝ 行使比例 × 每股選擇權價格。
- 無風險利率固定 1.5%／年（RISK_FREE），[自行裁量]：央行牌告利率尚未接入；1.5% 約為 2026 年台灣一年期定存
  水準的整數近似，對短天期權證的 IV 影響很小（利率差 0.5% 在 90 天權證上 IV 差遠小於 0.1 個百分點）。
- 到期日以日曆天計：T ＝（履約截止日 − 價格日）÷ 365。
- 重設型、上下限型不能套 Black-Scholes，一律排除（只算「一般型」）。

用法：
  python research/warrant_iv.py --sample 2026-10-14   # 用該日快照算全市場 IV 分佈 → research/data/warrant_iv_sample.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from datetime import date as _date
from pathlib import Path

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RISK_FREE = 0.015
VOL_LO, VOL_HI = 1e-4, 5.0  # 搜尋區間：0.01%～500%
TOL = 1e-8
SNAP_ROOT = HERE / "data" / "warrant_snapshots"
OUT = HERE / "data" / "warrant_iv_sample.json"


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S: float, K: float, T: float, sigma: float, cp: str, r: float = RISK_FREE, ratio: float = 1.0) -> float:
    """權證理論價（cp＝'C' 認購／'P' 認售）。T≤0 或 sigma≤0 時回內含價值（折現後），不拋錯。"""
    if S <= 0 or K <= 0:
        raise ValueError("S、K 必須 > 0")
    if T <= 0 or sigma <= 0:
        df = math.exp(-r * max(T, 0.0))
        iv = max(S - K * df, 0.0) if cp == "C" else max(K * df - S, 0.0)
        return ratio * iv
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / sq
    d2 = d1 - sq
    if cp == "C":
        p = S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    else:
        p = K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)
    return ratio * max(p, 0.0)


def implied_vol(price: float, S: float, K: float, T: float, cp: str, r: float = RISK_FREE,
                ratio: float = 1.0) -> tuple[float | None, str]:
    """二分法反推 IV。回 (iv, 原因)；反推不了回 (None, 原因)，原因只有固定幾種，方便統計。"""
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (price, S, K, T, ratio)):
        return None, "缺值"
    if price <= 0 or S <= 0 or K <= 0 or ratio <= 0:
        return None, "非正值"
    if T <= 0:
        return None, "已到期"
    lo_p = bs_price(S, K, T, VOL_LO, cp, r, ratio)
    hi_p = bs_price(S, K, T, VOL_HI, cp, r, ratio)
    if price < lo_p - TOL:
        return None, "低於內含價值"
    if price > hi_p + TOL:
        return None, "高於上限"
    lo, hi = VOL_LO, VOL_HI
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if bs_price(S, K, T, mid, cp, r, ratio) < price:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return 0.5 * (lo + hi), "ok"


def _load(d: Path, name: str):
    return json.loads(gzip.decompress((d / f"{name}.json.gz").read_bytes()).decode("utf-8"))


def _price(q: dict) -> tuple[float | None, str]:
    """有成交用收盤；沒成交用最後揭示買賣中價（兩邊都 >0 才算）。"""
    if q.get("close"):
        return q["close"], "收盤"
    b, a = q.get("bid"), q.get("ask")
    if b and a and b > 0 and a > 0:
        return 0.5 * (b + a), "買賣中價"
    return None, "無價"


def _pct(xs: list, p: float):
    if not xs:
        return None
    xs = sorted(xs)
    i = (len(xs) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (i - lo), 4)


def sample(day: str) -> dict:
    d = SNAP_ROOT / day
    t0 = _date.fromisoformat(day)
    rows = []  # (市場, cp, 價源, S, K, T, ratio, price)
    reasons: dict[str, int] = {}

    def bump(k):
        reasons[k] = reasons.get(k, 0) + 1

    basic_tw = {b["code"]: b for b in _load(d, "basic_twse")}
    for q in _load(d, "quotes_twse_call") + _load(d, "quotes_twse_put"):
        b = basic_tw.get(q["code"])
        if not b:
            bump("上市：基本資料查無")
            continue
        rows.append(("上市", b, q, q.get("und_close")))
    basic_tp = {b["code"]: b for b in _load(d, "basic_tpex")}
    issue = _load(d, "issue_tpex")
    und = _load(d, "underlying_tpex")
    for q in _load(d, "quotes_tpex"):
        b, iss = basic_tp.get(q["code"]), issue.get(q["code"])
        if not b or not iss:
            bump("上櫃：基本或發行資料查無")
            continue
        rows.append(("上櫃", b, q, und.get(iss.get("underlying_code") or "")))
    ivs: dict[str, list] = {}
    for mkt, b, q, S in rows:
        if b.get("kind") != "一般型":
            bump("排除：非一般型（重設／上下限）")
            continue
        cp = "C" if "購" in (b.get("cp") or "") else "P" if "售" in (b.get("cp") or "") else None
        if cp is None:
            bump("權證類型無法判斷")
            continue
        price, src = _price(q)
        if price is None:
            bump("無成交且無買賣價")
            continue
        if not S:
            bump("標的價查無")
            continue
        if not b.get("expiry"):
            bump("到期日缺")
            continue
        T = (_date.fromisoformat(b["expiry"]) - t0).days / 365.0
        iv, why = implied_vol(price, S, b.get("strike") or 0, T, cp, ratio=b.get("ratio") or 0)
        if iv is None:
            bump("反推失敗：" + why)
            continue
        ivs.setdefault(f"{mkt}{'認購' if cp == 'C' else '認售'}／{src}", []).append(iv)
    dist = {k: {"n": len(v), "p05": _pct(v, .05), "p25": _pct(v, .25), "p50": _pct(v, .5),
                "p75": _pct(v, .75), "p95": _pct(v, .95)} for k, v in sorted(ivs.items())}
    return {
        "date": day, "n_quotes": len(rows) + sum(v for k, v in reasons.items() if "查無" in k and "標的" not in k),
        "n_iv": sum(len(v) for v in ivs.values()), "distribution": dist, "skipped": dict(sorted(reasons.items())),
        "assumptions": {"model": "Black-Scholes 歐式、不含股利", "risk_free": RISK_FREE, "T": "日曆天/365",
                        "price": "有成交用收盤，否則最後揭示買賣中價", "kinds": "只算一般型"},
        "note": "先.九十四-5b 描述性樣本：只描述、不回測、不登記試驗、不計 N。非投資建議。",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, help="快照日期 YYYY-MM-DD")
    a = ap.parse_args()
    if not (SNAP_ROOT / a.sample / "meta.json").exists():
        print(f"沒有 {a.sample} 的快照，先跑 research/warrant_snapshot.py", flush=True)
        return 1
    res = sample(a.sample)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("date", "n_quotes", "n_iv")}, ensure_ascii=False), flush=True)
    for k, v in res["distribution"].items():
        print(f"  {k}: n={v['n']} 中位數 {v['p50']} （p25 {v['p25']}～p75 {v['p75']}）", flush=True)
    for k, v in res["skipped"].items():
        print(f"  略過 {k}: {v}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
