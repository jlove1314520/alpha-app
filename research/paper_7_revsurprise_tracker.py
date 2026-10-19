# -*- coding: utf-8 -*-
"""模擬 G（紙.七）：個股低換手（營收驚喜）前進式紙上追蹤（先.一一八-2，2026-10-18 總司令裁示採甲）。

規則照 `docs/PREREG_paper_g_revsurprise.md`（參數一次定死，不調參、不倒填）：
- 初次建倉 2026-11-02 起第一個有收盤資料的執行日（同模擬 F）；之後每季（2、5、8、11 月）第一個有收盤資料的執行日再平衡
  （2026-10-20 先.一一九-2 開始前修訂，原為 2027-01 起、1／4／7／10 月）。
- 宇宙：當天在市（data/listed_universe.json active）的上市＋上櫃普通股（4 碼、非 0 開頭、排除 91 開頭存託憑證），
  近 20 個交易日平均成交值 ≥ 3,000 萬元，且當天有收盤價。
- 因子：f_revenue_surprise 定義不變（research/factors.py `_revenue_surprise_sue`）：
  YoY＝(營收−去年同月)÷|去年同月|；SUE＝本月 YoY ÷ 含本月在內近 12 個 YoY 的樣本標準差；用每檔最近一個已公布月份，
  且該月不得早於再平衡月往前第 2 個月（例：11 月再平衡最舊只能用 9 月營收）。
- 組合：排名前 20 進場、跌出前 60 出場（或失去資格即出場）、空位由未持有的最高名次補滿 20 檔；每次再平衡全部回到等權。
- 成本：research/backtest/engine.py `buy_leg_rate`／`sell_leg_rate`（costs.py 1×、手續費不打折、證交稅 0.3%），依實際換手收。
資料全部讀 repo 既有檔（data/fundamentals.json 每日官方累積的 26 個月營收、data/price_history/），**零額外外部請求**。
輸出：research/data/paper_7_log.jsonl（帳本 append-only：inception／rebalance 事件帶 values_post，曲線由
build_strategy_curves.py 依每日還原收盤推算）、data/paper_7.json（App 摘要＋持股明細）。自身失敗只印警告、exit 0（十二節）。
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import price_history_store as PHS  # noqa: E402
from backtest.engine import BacktestConfig, buy_leg_rate, sell_leg_rate  # noqa: E402

TW = timezone(timedelta(hours=8))
LOG = ROOT / "research" / "data" / "paper_7_log.jsonl"
OUT = ROOT / "data" / "paper_7.json"
START_NOT_BEFORE = "2026-11-02"  # 先.一一九-2（開始前修訂，未觀察任何結果）：原 2027-01-01
REBAL_MONTHS = (2, 5, 8, 11)    # 先.一一九-2：原 (1, 4, 7, 10)
TOP_N, EXIT_RANK = 20, 60
MIN_TURNOVER = 30_000_000.0
LIQ_DAYS = 20
SUE_WINDOW = 12
MAX_REV_LAG_MONTHS = 2
INITIAL = 1_000_000.0
LABEL = "模擬 G 個股低換手（營收驚喜）"
NOTE = ("每季再平衡：月營收驚喜（今年比去年的成長率 ÷ 這檔股票成長率平常的波動）排名前 20 進場、跌出前 60 出場、等權；"
        "近 20 日平均成交值 ≥3,000 萬；成本 1×")
_CFG = BacktestConfig(start_date=START_NOT_BEFORE, end_date=START_NOT_BEFORE, initial_capital=INITIAL,
                      instrument_type="normal", book_name="paper_7_tracker")
BUY, SELL = buy_leg_rate(_CFG), sell_leg_rate(_CFG)


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def read_log() -> list:
    try:
        return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def append(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"logged_at": datetime.now(TW).isoformat(timespec="seconds"), **rec}, ensure_ascii=False) + "\n")


def is_common(code: str) -> bool:
    return len(code) == 4 and code.isdigit() and code[0] != "0" and not code.startswith("91")


def _ym_index(y: int, m: int) -> int:
    return y * 12 + (m - 1)


def revenue_sue(entry: dict, gap_rows: list | None = None) -> tuple[float, str] | None:
    """回傳 (SUE, 'YYYY-MM')；資料不足（不滿 24 個連續月份）回 None。定義同 factors._revenue_surprise_sue。
    gap_rows＝App 顯示用回補檔的同檔營收，只補官方累積檔沒有的月份（官方優先）。"""
    rows = {}
    for r in gap_rows or []:
        if r.get("revenue") is not None and r.get("year") and r.get("month"):
            rows[_ym_index(int(r["year"]), int(r["month"]))] = float(r["revenue"])
    for key in ("revenue_history_scoring", "month_revenue"):  # 後者較新、同年月覆蓋
        for r in entry.get(key) or []:
            if r.get("revenue") is not None and r.get("year") and r.get("month"):
                rows[_ym_index(int(r["year"]), int(r["month"]))] = float(r["revenue"])
    if not rows:
        return None
    last = max(rows)
    yoys = []
    for i in range(last - SUE_WINDOW + 1, last + 1):
        cur, prv = rows.get(i), rows.get(i - 12)
        if cur is None or prv is None or prv == 0:
            return None
        yoys.append((cur - prv) / abs(prv))
    sd = statistics.stdev(yoys)
    if not sd:
        return None
    return yoys[-1] / sd, f"{last // 12}-{last % 12 + 1:02d}"


class Px:
    def __init__(self, prices: dict):
        self.rows = prices

    def close_le(self, code: str, d: str):
        best = None
        for r in self.rows.get(code) or []:
            if r["date"] <= d:
                v = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
                if v is not None:
                    best = float(v)
            else:
                break
        return best

    def close_on(self, code: str, d: str):
        for r in self.rows.get(code) or []:
            if r["date"] == d:
                v = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
                return float(v) if v is not None else None
        return None

    def avg_turnover(self, code: str, d: str):
        vals = [float(r["turnover"]) for r in (self.rows.get(code) or []) if r["date"] <= d and r.get("turnover") is not None]
        vals = vals[-LIQ_DAYS:]
        return sum(vals) / len(vals) if len(vals) == LIQ_DAYS else None


def latest_date(px: Px) -> str | None:
    return max((rs[-1]["date"] for rs in px.rows.values() if rs), default=None)


def load_gap_fill() -> dict:
    """[自行裁量]（先.一一八-2b）：data/fundamentals.json 的 26 個月營收在 2024-12～2025-04 有缺口（2026-08-27 起始種子的範圍問題），
    2026-11、2027-02、2027-05 三次再平衡算 SUE 分母會缺月份；只拿 App 顯示用回補檔（FinMind，2024-12～2026-06，與官方重疊 756 個月全部一致）補缺月。
    這是前向追蹤的輸入（判定只看 2026-11 起的報酬），不是對 holdout 期間做回測或檢定；
    守門自測（scripts/selftest_display_only_files.py）對本檔單獨列名放行。總司令可推翻（替代：改 2027-08 起跑、不讀回補檔）。"""
    return ((_load(ROOT / "data" / "revenue_backfill.json", {}) or {}).get("stocks")) or {}


def ranking(px: Px, day: str, funds: dict, active: set, gap: dict | None = None) -> list:
    y, m = int(day[:4]), int(day[5:7])
    oldest_ok = _ym_index(y, m) - MAX_REV_LAG_MONTHS
    out = []
    for code in active:
        if not is_common(code) or px.close_on(code, day) is None:
            continue
        liq = px.avg_turnover(code, day)
        if liq is None or liq < MIN_TURNOVER:
            continue
        s = revenue_sue(funds.get(code) or {}, (gap or {}).get(code))
        if not s:
            continue
        sue, ym = s
        if _ym_index(int(ym[:4]), int(ym[5:])) < oldest_ok:
            continue
        out.append({"code": code, "sue": round(sue, 4), "rev_month": ym, "turnover_20d": round(liq)})
    out.sort(key=lambda r: (-r["sue"], r["code"]))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def current_values(px: Px, ev: dict, day: str) -> dict:
    vals = {}
    for code, v in (ev.get("values_post") or {}).items():
        p0, p1 = px.close_le(code, ev["date"]), px.close_le(code, day)
        vals[code] = v * (p1 / p0) if p0 and p1 else v
    return vals


def rebalance(px: Px, day: str, funds: dict, active: set, prev: dict | None, gap: dict | None = None) -> dict:
    rk = ranking(px, day, funds, active, gap)
    by = {r["code"]: r for r in rk}
    held = current_values(px, prev, day) if prev else {}
    nav_pre = sum(held.values()) if prev else INITIAL
    keep = [c for c in held if c in by and by[c]["rank"] <= EXIT_RANK]
    exits = [c for c in held if c not in keep]
    new = keep[:]
    for r in rk:
        if len(new) >= TOP_N:
            break
        if r["code"] not in new:
            new.append(r["code"])
    if not new:
        raise RuntimeError(f"{day} 合格宇宙是空的（營收或成交值資料不足），不建倉")
    # 先賣（含出場與減碼）、再買；等權目標以扣完賣出成本後的淨值計
    sells = {c: max(0.0, held.get(c, 0.0) - (0.0 if c not in new else nav_pre / len(new))) for c in held}
    cash = nav_pre - sum(held.values()) + sum(v * (1 - SELL) for v in sells.values())
    remain = {c: held.get(c, 0.0) - sells.get(c, 0.0) for c in new}
    # 解等權：每檔目標 T，需買入 (T−remain)，買入成本 BUY；T 滿足 sum(remain)+cash = n·T + BUY·sum(max(0,T−remain))
    lo, hi = 0.0, (sum(remain.values()) + cash) / len(new)
    for _ in range(60):
        t = (lo + hi) / 2
        need = sum(max(0.0, t - remain[c]) * (1 + BUY) for c in new) - sum(max(0.0, remain[c] - t) for c in new)
        lo, hi = (t, hi) if need <= cash else (lo, t)
    t = lo
    values_post = {c: round(t, 2) for c in new}
    traded = sum(sells.values()) + sum(max(0.0, t - remain[c]) for c in new)
    cost = sum(sells.values()) * SELL + sum(max(0.0, t - remain[c]) for c in new) * BUY
    return {"date": day, "event": "inception" if not prev else "rebalance", "values_post": values_post,
            "nav_pre": round(nav_pre, 2), "nav": round(sum(values_post.values()), 2),
            "rebalance_cost": round(cost, 2), "turnover_pct": round(traded / nav_pre * 100, 2) if nav_pre else None,
            "entered": [c for c in new if c not in held], "exited": exits, "kept": keep,
            "picks": [by[c] for c in new], "universe_n": len(rk), "costs": {"buy": BUY, "sell": SELL}}


def _next_rebalance_month(day: str) -> str:
    y, m = int(day[:4]), int(day[5:7])
    while True:
        m += 1
        if m > 12:
            y, m = y + 1, 1
        if m in REBAL_MONTHS:
            return f"{y}-{m:02d}"


def write_summary(px: Px | None, log: list, extra: dict | None = None) -> None:
    names = {}
    for row in (_load(ROOT / "data" / "stock_names.json", {}) or {}).get("tw") or []:
        if row:
            names[row[0]] = row[1]
    doc = {"label": LABEL, "note": NOTE, "start_not_before": START_NOT_BEFORE, "started": bool(log),
           "generated_at": datetime.now(TW).isoformat(timespec="seconds"),
           "judge": "滿 24 個月（8 次再平衡）判一次：扣 1× 成本年化 > 0050 含息、兩年中至少一年贏 0050、期間回撤 ≤50%（天條一）",
           "known_limit": "f_revenue_surprise 最近一次重驗 #404 FAIL（百分位 87.0，門檻 98.33）；只有 8 次再平衡，統計上很弱",
           "disclaimer": "紙上追蹤，非投資建議。虛擬帳戶，未使用真實資金。", **(extra or {})}
    if log and px:
        ev = log[-1]
        day = latest_date(px) or ev["date"]
        vals = current_values(px, ev, day)
        nav = sum(vals.values())
        picks = {p["code"]: p for p in ev.get("picks") or []}
        entry_date = {}
        for e in log:
            for c in e.get("entered") or []:
                entry_date[c] = e["date"]
        doc.update({"as_of_date": day, "nav": round(nav, 2), "initial_virtual_capital": INITIAL,
                    "total_return_pct": round((nav / INITIAL - 1) * 100, 2), "last_rebalance": ev["date"],
                    "next_rebalance_month": _next_rebalance_month(ev["date"]), "n_rebalances": len(log),
                    "holdings": sorted([{"code": c, "name": names.get(c, ""), "weight_pct": round(v / nav * 100, 2) if nav else None,
                                         "rank_at_rebalance": (picks.get(c) or {}).get("rank"),
                                         "rev_month": (picks.get(c) or {}).get("rev_month"),
                                         "since": entry_date.get(c)} for c, v in vals.items()],
                                       key=lambda h: (h["rank_at_rebalance"] or 9999)),
                    "last_entered": ev.get("entered") or [], "last_exited": ev.get("exited") or []})
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def step(today: str | None = None) -> dict:
    log = read_log()
    px = Px(PHS.load(ROOT / "data" / "price_history.json").get("prices") or {})
    day = latest_date(px)
    if not day:
        raise RuntimeError("price_history 讀不到任何收盤資料")
    if (today or day) < START_NOT_BEFORE:
        write_summary(px, log, {"why_not_started": f"{START_NOT_BEFORE[5:].replace('-', '/')} 起跟模擬 F 同一天建倉、之後每季（2、5、8、11 月）再平衡，不倒填"})
        return {"state": "NOT_STARTED", "day": day}
    quarter_key = day[:7]
    done = any(e["date"][:7] == quarter_key for e in log)
    if int(day[5:7]) not in REBAL_MONTHS or done or (log and day <= log[-1]["date"]):
        write_summary(px, log)
        return {"state": "HOLD", "day": day}
    funds = (_load(ROOT / "data" / "fundamentals.json", {}) or {}).get("fundamentals") or {}
    active = set((_load(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
    ev = rebalance(px, day, funds, active, log[-1] if log else None, load_gap_fill())
    append(ev)
    log = read_log()
    write_summary(px, log)
    return {"state": ev["event"].upper(), "day": day, "n": len(ev["values_post"]), "universe_n": ev["universe_n"]}


def main() -> int:
    try:
        print(json.dumps(step(), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 —— 十二節：自身失敗只警告
        print(f"[warn] 模擬 G 追蹤失敗：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
