# -*- coding: utf-8 -*-
"""先.一五六-2b 國安基金第 10 次護盤：NTSF-C（F12 第二階段名單 2× 移動停利 15%）紙上每日產生器。零外部請求。

規則（同 research/ntsf_list_variant.py 回測，這裡不調參）：
- 名單：宣布日 2026-11-06 收盤後可得資料，4 碼普通股（上市＋上櫃）中「還原收盤 > MA150 且 MA150 > 10 日前 MA150」
  （MA150 至少 140 筆有價），依 60 日報酬取前 20 檔。名單第一次算出就凍結進帳本。
- 進場：[自行裁量] 不倒填——本程式 2026-11-11 才寫好，進場日＝2026-11-11 收盤（比回測規則的 11/09 晚 2 天）。
  進場日鎖漲停（最高＝最低且收盤漲 ≥9.4%）那檔買不到、留現金。
- 持有：等權、權重自然漂移；2× 融資，超過 1× 部分付 6.5%/年；組合槓桿後淨值自高點回撤 15% 出場，最多 250 個交易日。
- 成本：買 手續費 0.1425%＋滑價 0.05%；賣 手續費＋證交稅 0.3%＋滑價 0.05%（持股部分 × 槓桿）。
資料（本機）：
- research/data/paper_9_lookback/{twse,tpex}/YYYYMMDD.json（2025-10-28～2026-10-30 官方全市場日檔；
  還原日報酬＝收盤÷(收盤−漲跌)−1）
- 之後：data/price_history（每日排程，adj_close 比值）。停牌日報酬記 0。
輸出：research/data/paper_opt/ledger_NTSF-C.json（本機帳本，不進公開 repo）。失敗只印警告、exit 0（十二節）。
非投資建議。
"""
from __future__ import annotations

import glob
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LOOKBACK = HERE / "data" / "paper_9_lookback"
OUT = HERE / "data" / "paper_opt" / "ledger_NTSF-C.json"
REF_DATE = "2026-11-06"
ENTRY_DATE = "2026-11-11"
N, L, TRAIL, MAX_HOLD, FIN = 20, 2.0, 0.15, 250, 0.065
FEE, TAX, SLIP = 0.001425, 0.003, 0.0005
BUY_C, SELL_C = FEE + SLIP, FEE + TAX + SLIP
STOCK_RE = re.compile(r"^[1-9]\d{3}$")
MIN_TRADED = 1000


def load_bars() -> tuple[dict, list[str]]:
    """{代號: {日期: (close, ret, high, low)}}、交易日曆。"""
    bars: dict = {}
    cal = set()
    for src in ("twse", "tpex"):
        for f in sorted(glob.glob(str(LOOKBACK / src / "*.json"))):
            try:
                j = json.loads(Path(f).read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[warn] 讀不到 {f}：{e}")
                continue
            if j.get("status") != "ok":
                continue
            dt = j["date"]
            rows = j.get("rows") or {}
            if src == "twse" and len(rows) > 500:
                cal.add(dt)
            for sid, row in rows.items():
                if not STOCK_RE.match(sid) or len(row) < 7:
                    continue
                o, h, lo, c, _v, _t, chg = row[:7]
                if not c or c <= 0:
                    continue
                ref = c - chg if chg is not None else None
                ret = (c / ref - 1.0) if ref and ref > 0 else None
                bars.setdefault(sid, {})[dt] = (c, ret, h, lo)
    last = max(cal)
    ph: dict = {}
    for f in sorted(glob.glob(str(REPO / "data" / "price_history" / "b*.json"))):
        try:
            ph.update(json.loads(Path(f).read_text(encoding="utf-8"))["prices"])
        except Exception as e:
            print(f"[warn] 讀不到 {f}：{e}")
    cnt: dict = {}
    for sid, rows in ph.items():
        for r in rows:
            if (r.get("close") or 0) > 0:
                cnt[r["date"]] = cnt.get(r["date"], 0) + 1
    new_days = {d for d, n in cnt.items() if n >= MIN_TRADED and d > last}
    for sid, rows in ph.items():
        if not STOCK_RE.match(sid):
            continue
        prev = None
        for r in sorted((r for r in rows if r.get("date")), key=lambda r: r["date"]):
            ok = (r.get("close") or 0) > 0 and (r.get("adj_close") or 0) > 0
            if ok and r["date"] in new_days:
                ret = (r["adj_close"] / prev["adj_close"] - 1.0) if prev else None
                bars.setdefault(sid, {})[r["date"]] = (r["close"], ret, r.get("high"), r.get("low"))
            if ok:
                prev = r
    return bars, sorted(cal | new_days)


def f12_list(bars: dict, cal: list[str], day: str) -> list[dict]:
    t = cal.index(day)
    if t < 170:
        raise RuntimeError(f"歷史只有 {t} 天，MA150 算不出")
    win = cal[t - 160:t + 1]
    out = []
    for sid, b in bars.items():
        if day not in b:
            continue
        lv, adj = 1.0, []
        for d in win:
            if d in b:
                r = b[d][1]
                lv *= 1.0 + (r if r is not None else 0.0)
                adj.append(lv)
            else:
                adj.append(None)
        now = adj[-1]
        seg_now = [x for x in adj[-150:] if x is not None]
        seg_prev = [x for x in adj[-160:-10] if x is not None]
        if len(seg_now) < 140 or len(seg_prev) < 10 or adj[-61] is None:
            continue
        ma_now, ma_prev = sum(seg_now) / len(seg_now), sum(seg_prev) / len(seg_prev)
        if now > ma_now and ma_now > ma_prev:
            out.append({"id": sid, "ret60": round(now / adj[-61] - 1, 4)})
    out.sort(key=lambda x: -x["ret60"])
    return out[:N]


def run() -> dict:
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    bars, cal = load_bars()
    names = prev.get("names") or f12_list(bars, cal, REF_DATE)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "id": "NTSF-C",
           "rule": "F12 第二階段名單前 20 檔、2× 融資、移動停利 15%、最多 250 日",
           "ref_date": REF_DATE, "entry_date": ENTRY_DATE, "names": names, "status": "等待進場日收盤", "curve": []}
    days = [d for d in cal if d >= ENTRY_DATE]
    if not days or days[0] != ENTRY_DATE:
        return out
    ids = [x["id"] for x in names]
    e = ENTRY_DATE
    pd_ = cal[cal.index(e) - 1]
    buy = []
    for s in ids:
        b = bars.get(s, {})
        if e not in b:
            continue
        c, r, h, lo = b[e]
        locked = h is not None and lo is not None and h == lo and (r or 0) >= 0.094
        if not locked:
            buy.append(s)
    w = {s: (1.0 - BUY_C) / N for s in buy}
    cash = 1.0 - len(buy) / N
    inv = len(buy) / N
    nav = peak = 1.0
    curve = [[e, 1.0]]
    status, exit_date = "持有中", None
    for i in range(1, len(days)):
        d = days[i]
        before = sum(w.values()) + cash
        for s in w:
            r = bars.get(s, {}).get(d, (None, None))[1]
            w[s] *= 1.0 + (r if r is not None else 0.0)
        r1 = (sum(w.values()) + cash) / before - 1
        nav *= 1 + L * r1 - (L - 1) * FIN / 252 * inv
        peak = max(peak, nav)
        if nav / peak - 1 <= -TRAIL or i >= MAX_HOLD:
            frac = sum(w.values()) / (sum(w.values()) + cash)
            nav *= 1 - SELL_C * frac * L
            status, exit_date = ("移動停利出場" if i < MAX_HOLD else "滿 250 日出場"), d
            curve.append([d, round(nav, 5)])
            break
        curve.append([d, round(nav, 5)])
    out.update({"status": status, "exit_date": exit_date, "bought": buy, "nav": round(nav, 5),
                "peak": round(peak, 5), "days_held": len(curve) - 1, "curve": curve, "prev_day": pd_})
    return out


def main() -> int:
    try:
        out = run()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("NTSF-C", out["status"], "名單", [x["id"] for x in out["names"]], "nav", out.get("nav"))
    except Exception as e:  # 十二節：只降級成警告
        print(f"[警告] NTSF-C 紙上失敗：{e!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
