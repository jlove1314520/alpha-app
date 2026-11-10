# -*- coding: utf-8 -*-
"""先.一五八-3 紙上優化軌：補正官方日檔「除權息日漲跌記成 0」造成的日報酬 0——研究帽產物，零外部請求。

問題：research/fetch_paper_9_lookback.py 解析證交所 MI_INDEX 時，除權息日官方「漲跌(+/-)」欄是 X（不比價）、
  「漲跌價差」是 0.00，`_signed_change()` 先判 mag==0 就回 0.0（沒走到 X→None 那條），於是
  paper_opt_f12／f14／f18 的 build_bars() 用「收盤÷(收盤−漲跌)−1」算出 0。0050 在 2026-01-22（現金 1.0 元）、
  2026-07-21（現金 0.6 元）兩個除息日因此記成 0（實際約 +1.34%、+3.96%）。FinMind TaiwanStockPrice 的 spread
  同樣是 0，不能拿來對。

補正（只動 ret 欄，OHLC 不動；只看回看期官方日檔那段日期，price_history 那段本來就用 adj_close）：
  候選＝ret 恰為 0 的日子。依序找參考價：
    ① data/price_history 兩天都有 adj_close 且前一列就是 bars 的前一筆 → ret＝adj 比值
    ② data/ex_dividend_events.json 當天有已套用事件 → ret＝收盤÷(前收×factor_applied)−1
    ③ research/data/raw/TaiwanStockDividend__{代號}__*.parquet（本機 FinMind 快取）當天是現金或股票除權息交易日
       → 參考價＝(前收−現金)÷(1＋配股元÷10)
    ④ 都沒有、但收盤≠前收（漲跌 0 卻有價差，必是 X 列）→ 退回原始價格報酬 收盤÷前收−1（不含權息，照實標 raw_close）
  收盤＝前收且找不到事件 → 真的 0，不動。
除權息日與股利金額在除權息交易日前已公告，當天用參考價算報酬不是偷看未來；FinMind 列的 date 欄（公告整理日）
晚於除息日，只拿除息日與金額，不拿 date 欄當可得日。
非投資建議。
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
RAW = HERE / "data" / "raw"
VERSION = 1


def _price_history() -> dict:
    ph: dict = {}
    for f in sorted(glob.glob(str(DATA / "price_history" / "b*.json"))):
        try:
            ph.update(json.loads(Path(f).read_text(encoding="utf-8"))["prices"])
        except Exception as e:  # 單一分片壞掉只略過
            print(f"[warn] exright_fix 讀不到 {f}：{e}")
    return ph


def _ledger_events() -> dict:
    try:
        e = json.loads((DATA / "ex_dividend_events.json").read_text(encoding="utf-8"))
    except Exception as ex:
        print(f"[warn] exright_fix 讀不到 ex_dividend_events.json：{ex}")
        return {}
    out: dict = {}
    for sid, lst in (e.get("events") or {}).items():
        for ev in lst:
            if ev.get("applied") and ev.get("factor_applied") and ev.get("ex_date"):
                out[(sid, ev["ex_date"])] = float(ev["factor_applied"])
    return out


def _finmind_div(sid: str, cache: dict) -> dict:
    """{除權息交易日: (現金, 配股元)}，同代號多份快取合併。"""
    if sid in cache:
        return cache[sid]
    res: dict = {}
    files = glob.glob(str(RAW / f"TaiwanStockDividend__{sid}__*.parquet"))
    if files:
        try:
            import pandas as pd
            for f in files:
                d = pd.read_parquet(f)
                for _, r in d.iterrows():
                    cash = float(r.get("CashEarningsDistribution") or 0) + float(r.get("CashStatutorySurplus") or 0)
                    stk = float(r.get("StockEarningsDistribution") or 0) + float(r.get("StockStatutorySurplus") or 0)
                    cd, sd = str(r.get("CashExDividendTradingDate") or ""), str(r.get("StockExDividendTradingDate") or "")
                    if cd and cash > 0:
                        c0, s0 = res.get(cd, (0.0, 0.0))
                        res[cd] = (max(c0, cash), s0)
                    if sd and stk > 0:
                        c0, s0 = res.get(sd, (0.0, 0.0))
                        res[sd] = (c0, max(s0, stk))
        except Exception as e:
            print(f"[warn] exright_fix 讀不到 {sid} 股利快取：{e}")
    cache[sid] = res
    return res


def fix_zero_returns(bars: dict, last_date: str, ret_idx: int = 4, close_idx: int = 3) -> list[list]:
    """就地補正 bars（{代號: {日期: [o,h,l,c,ret,...]}}）日期 ≤ last_date 的 0 報酬；回傳 [[代號,日期,舊,新,來源],...]。"""
    ph = _price_history()
    phi = {sid: {r["date"]: r for r in rows if r.get("date")} for sid, rows in ph.items()}
    phd = {sid: sorted(d) for sid, d in phi.items()}
    lev = _ledger_events()
    fm: dict = {}
    fixes = []
    for sid, b in bars.items():
        ds = sorted(b)
        for i in range(1, len(ds)):
            d, pdt = ds[i], ds[i - 1]
            if d > last_date:
                break
            row = b[d]
            if row[ret_idx] != 0:
                continue
            c, pc = row[close_idx], b[pdt][close_idx]
            if not c or not pc or c <= 0 or pc <= 0:
                continue
            new, src = None, None
            rows = phi.get(sid) or {}
            if d in rows and pdt in rows and (rows[d].get("adj_close") or 0) > 0 and (rows[pdt].get("adj_close") or 0) > 0:
                lst = phd[sid]
                k = lst.index(d)
                if k > 0 and lst[k - 1] == pdt:
                    new, src = rows[d]["adj_close"] / rows[pdt]["adj_close"] - 1.0, "price_history_adj"
            if new is None and (sid, d) in lev:
                new, src = c / (pc * lev[(sid, d)]) - 1.0, "ex_dividend_events"
            if new is None:
                ev = _finmind_div(sid, fm).get(d)
                if ev:
                    cash, stk = ev
                    ref = (pc - cash) / (1.0 + stk / 10.0)
                    if ref > 0:
                        new, src = c / ref - 1.0, "finmind_dividend_cache"
            if new is None and abs(c - pc) > 1e-9:
                new, src = c / pc - 1.0, "raw_close"
            if new is None or abs(new) < 1e-12:
                continue
            row[ret_idx] = new
            fixes.append([sid, d, 0.0, round(new, 8), src])
    return fixes


def apply_once(cache: dict, last_date: str) -> list[list]:
    """build_bars 用：快取沒有 exright_fix 版本標記才補，補完寫標記（冪等）。"""
    if (cache.get("exright_fix") or {}).get("version") == VERSION:
        return []
    fixes = fix_zero_returns(cache["bars"], last_date)
    cache["exright_fix"] = {"version": VERSION, "last_date": last_date, "n": len(fixes), "fixes": fixes,
                            "note": "先.一五八-3：官方日檔除權息日漲跌記 0 的補正（見 research/paper_opt_exright_fix.py）"}
    print(f"[exright_fix] 補正 {len(fixes)} 筆 0 報酬（≤{last_date}）")
    return fixes


def lookback_last() -> str:
    """模擬 I 回看期官方日檔最後一天（YYYY-MM-DD）；讀不到回空字串＝不補。"""
    fs = sorted(glob.glob(str(HERE / "data" / "paper_9_lookback" / "twse" / "*.json")))
    if not fs:
        return ""
    s = Path(fs[-1]).stem
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"
