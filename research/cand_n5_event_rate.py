# -*- coding: utf-8 -*-
"""候選 N5（借券賣出餘額 5 日大幅回補後漂移，前向、只做上市）事件抽取＋事件率量測（先.一三五-1f ①）。

草稿：docs/PREREG_DRAFT_SBL_COVERING_DRIFT_FORWARD.md §2。
- 只量「籌碼／申報條件」：上市普通股、5 個交易日前借券賣出餘額 ≥ 100 萬股、t0 餘額 ÷ 5 日前 − 1 ≤ −40%、
  t0 前後 10 個交易日內有除權息者排除（只讀 data/ex_dividend_events.json 的 ex_date）、同代號 60 個交易日去重。
- **不讀任何價格、不算任何報酬、零外部請求**；流動性門檻、t1 漲停放棄要價格，留給定稿後追蹤程式 → 事件數是**上限**。
- 只讀 data/securities_lending_sell_history.json 的 series_twse（sbl_balance＝第 5 欄）、data/listed_universe.json、
  data/trading_calendar.json、data/ex_dividend_events.json。輸出 research/data/cand_n5_event_rate.json。
- 「5 個交易日前」用休市日曆算，不用陣列位置：中間漏一天資料時找不到恰好 5 個交易日前的列 → 該日不判（照實計數）。
自測：python research/cand_n5_event_rate.py --selftest
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

import cand_n1_event_rate as N1
import cand_n2_event_rate as N2

ROOT = N1.ROOT
SRC = ROOT / "data" / "securities_lending_sell_history.json"
EXDIV = ROOT / "data" / "ex_dividend_events.json"
OUT = ROOT / "research" / "data" / "cand_n5_event_rate.json"
LOOKBACK_TD = 5          # 草稿 §2，寫死
MIN_BASE_SHARES = 1_000_000
C = 0.40                 # 草稿 §3
EXDIV_TD = 10            # 草稿 §2，前後 10 個交易日
DEDUP_TD = 60
BAL_IDX = 4              # series_twse 欄位：sbl_prev_balance, sbl_sell, sbl_return, sbl_adjust, sbl_balance, quota


def iso(k: str) -> str:
    return f"{k[:4]}-{k[4:6]}-{k[6:8]}"


def shift_td(d: str, n: int, closed: set[str]) -> str:
    """d 往前（n<0）或往後（n>0）數 |n| 個交易日。"""
    x, step, left = date.fromisoformat(d), (1 if n > 0 else -1), abs(n)
    while left:
        x += timedelta(days=step)
        if x.weekday() < 5 and x.isoformat() not in closed:
            left -= 1
    return x.isoformat()


def is_signal(bal_t0: float, bal_base: float) -> bool:
    return bal_base >= MIN_BASE_SHARES and round(bal_t0 / bal_base - 1, 9) <= -C


def near_exdiv(d: str, exdates: list[str], closed: set[str]) -> bool:
    lo, hi = shift_td(d, -EXDIV_TD, closed), shift_td(d, EXDIV_TD, closed)
    return any(lo <= x <= hi for x in exdates)


def load_exdiv() -> dict[str, list[str]] | None:
    try:
        ev = json.loads(EXDIV.read_text(encoding="utf-8")).get("events") or {}
        return {c: sorted(str(r.get("ex_date")) for r in rows if r.get("ex_date")) for c, rows in ev.items()}
    except Exception as e:  # noqa: BLE001 —— 讀不到就不做除權息排除（事件數偏多），照實寫進輸出
        print(f"[warn] ex_dividend_events 讀取失敗，略過除權息排除：{e}")
        return None


def extract(series: dict, closed: set[str], exdiv: dict[str, list[str]] | None) -> tuple[list[dict], dict]:
    hits, n_judged, n_no_base, n_exdiv = [], 0, 0, 0
    for code, s in series.items():
        if not N1.is_common_stock(code):
            continue
        for k in sorted(s):
            d = iso(k)
            base_k = shift_td(d, -LOOKBACK_TD, closed).replace("-", "")
            if base_k not in s:
                n_no_base += 1
                continue
            n_judged += 1
            b0, bb = float(s[k][BAL_IDX]), float(s[base_k][BAL_IDX])
            if not is_signal(b0, bb):
                continue
            if exdiv is not None and near_exdiv(d, exdiv.get(code, []), closed):
                n_exdiv += 1
                continue
            hits.append({"code": code, "date": d, "sbl_balance_base": bb, "sbl_balance_t0": b0,
                         "chg_pct": round((b0 / bb - 1) * 100, 2)})
    hits.sort(key=lambda x: (x["date"], x["code"]))
    out, last, dropped = [], {}, 0
    for h in hits:
        p = last.get(h["code"])
        if p is not None and N2.trading_days_between(p, h["date"], closed) < DEDUP_TD:
            dropped += 1
            continue
        last[h["code"]] = h["date"]
        out.append(h)
    return out, {"n_stock_days_judged": n_judged, "n_stock_days_no_base_row": n_no_base,
                 "n_signal_rows_excluded_exdiv": n_exdiv, "n_signal_rows_before_dedup": len(hits),
                 "n_dropped_by_dedup": dropped}


def main() -> int:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    series = doc.get("series_twse") or {}
    try:
        active = set(json.loads(N1.UNIVERSE.read_text(encoding="utf-8")).get("active") or [])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] listed_universe 讀取失敗，在市比例略過：{e}")
        active = None
    closed = N2.load_closed()
    exdiv = load_exdiv()
    evs, st = extract(series, closed, exdiv)
    keys = sorted({k for s in series.values() for k in s})
    span_td = (N2.trading_days_between(iso(keys[0]), iso(keys[-1]), closed) + 1) if keys else 0
    judged_days = max(span_td - LOOKBACK_TD, 0)  # 前 5 個交易日沒有基準列，不能判
    weekly: dict[str, int] = {}
    for e in evs:
        weekly[N1.iso_week(e["date"])] = weekly.get(N1.iso_week(e["date"]), 0) + 1
    per_year = round(len(evs) / judged_days * 245, 1) if judged_days else None
    out = {
        "generated_at": datetime.now(N1.TW).isoformat(timespec="seconds"),
        "item": "先.一三五-1f ①",
        "prereg_draft": "docs/PREREG_DRAFT_SBL_COVERING_DRIFT_FORWARD.md",
        "source_file": "data/securities_lending_sell_history.json（series_twse.sbl_balance）",
        "source_generated_at": (doc.get("meta") or {}).get("generated_at"),
        "source_key_range": [keys[0], keys[-1]] if keys else None,
        "source_span_trading_days": span_td,
        "judgeable_trading_days": judged_days,
        "rule": {"market": "只上市（TWT93U）", "common_stock": "4 碼數字、非 0 開頭、排除 91 開頭",
                 "lookback_trading_days": LOOKBACK_TD, "min_base_balance_shares": MIN_BASE_SHARES,
                 "max_5d_change": -C, "exdiv_exclusion_trading_days": EXDIV_TD if exdiv is not None else None,
                 "dedup_trading_days": DEDUP_TD,
                 "not_applied_need_price": ["前 20 日均成交值 ≥ 1,000 萬", "t1 漲停放棄", "t0 當天在市（用今天的 active 快照近似）"]},
        **st,
        "n_events": len(evs),
        "n_codes": len({e["code"] for e in evs}),
        "n_in_active_universe": sum(1 for e in evs if e["code"] in active) if active is not None else None,
        "weekly": {k: weekly[k] for k in sorted(weekly)},
        "est_events_per_year_upper_bound": per_year,
        "est_events_24m_upper_bound": round(per_year * 2) if per_year is not None else None,
        "events": evs,
        "note": ("只讀借券賣出餘額、除權息日期、在市名冊、休市日曆；未讀任何價格、未算報酬、零外部請求。"
                 "流動性門檻未套，事件數是上限。年化＝事件數 ÷ 可判交易日（樣本交易日 − 5）× 245；"
                 "60 交易日去重在只有約 3 週可判的樣本裡幾乎不起作用，長期事件率會比這裡低（同代號重複觸發會被吃掉），誤差大。"
                 "除權息排除用 ex_dividend_events.json 現有事件（含預告），t0 後 10 日的除權息在前向追蹤時要等預告公布才看得到。"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫入 {OUT.relative_to(ROOT)}：可判股日 {st['n_stock_days_judged']}（缺基準列 {st['n_stock_days_no_base_row']}）、"
          f"除權息排除 {st['n_signal_rows_excluded_exdiv']}、訊號列 {st['n_signal_rows_before_dedup']} → 去重後事件 {len(evs)}"
          f"（{out['n_codes']} 檔）、可判 {judged_days} 交易日、年化上限約 {per_year}、24 個月上限約 {out['est_events_24m_upper_bound']}")
    return 0


def selftest() -> int:
    closed = {"2026-10-09"}
    assert shift_td("2026-10-13", -5, closed) == "2026-10-05"   # 10/12、10/08、10/07、10/06、10/05（跳 10/09 休市、週末）
    assert shift_td("2026-10-05", 5, closed) == "2026-10-13"
    assert is_signal(600_000, 1_000_000) and not is_signal(600_001, 1_000_000) and not is_signal(0, 999_999)
    row = lambda b: [0, 0, 0, 0, b, 0]  # noqa: E731
    series = {
        "2330": {"20261005": row(2_000_000), "20261013": row(1_000_000)},        # −50% → 事件
        "2317": {"20261005": row(2_000_000), "20261013": row(1_000_000)},        # 除權息 10/20 在 10 日內 → 排除
        "2454": {"20261006": row(2_000_000), "20261013": row(1_000_000)},        # 基準日錯位（不是恰好 5 日前）→ 不判
        "00878": {"20261005": row(2_000_000), "20261013": row(0)},              # 非普通股
    }
    ev, st = extract(series, closed, {"2317": ["2026-10-20"]})
    assert [(e["code"], e["date"]) for e in ev] == [("2330", "2026-10-13")], ev
    assert st["n_signal_rows_excluded_exdiv"] == 1 and st["n_stock_days_judged"] == 2, st
    series2 = {"2330": {"20261005": row(2_000_000), "20261013": row(1_000_000),
                        "20261006": row(2_000_000), "20261014": row(1_000_000)}}  # 隔天又觸發 → 60 日去重
    ev2, st2 = extract(series2, closed, {})
    assert len(ev2) == 1 and st2["n_dropped_by_dedup"] == 1, (ev2, st2)
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
