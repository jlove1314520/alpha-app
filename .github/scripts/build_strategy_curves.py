"""先.六十八：「策略 vs 0050」卡資料 → data/strategy_curves.json（每日 market.yml 排程，零外部請求）。

每條線從各自起始日歸一為 100，並附同一條時間軸上的 0050 灰線（先.八十-12 起一律用還原權息收盤＝含息）。

一、選股三榜（估值／動能／未來）：重疊組合法（2026-10-11 總司令裁示更正）。
    - 每個交易日一個新批次（picks_ledger 該榜該日 Top20 等權買進，進場價＝快照的 close_price／price_date 收盤），
      持有 5 個交易日；同時最多 5 個批次在場，每批次佔 1/5 資金。
    - 組合日報酬＝當日在場各批次「當日報酬」的平均（每批次固定 1/5 權重；缺快照的空檔為現金、不計息）；
      批次當日報酬＝等權買進後持有不動的市值變化。
    - 成本只在批次進出時各扣一次：進場手續費 0.1425%，出場手續費 0.1425%＋證交稅 0.3%。
    - 舊算法（build_benchmark_comparison.py）把逐批 t5 報酬「依序串接複利」，等於把重疊的 5 日報酬
      重複計 5 次，誤放大約 5 倍——本檔取代之。
    - 同一 price_date 的多個快照（週末／重跑）只取第一個；price_stale 的個股不進批次。
二、紙上追蹤（紙.一／一b／三／四）：讀 research/data/paper_*_log.jsonl 事件（建倉、月底再平衡、閘門切換），
    事件之間各部位依 price_history 實際收盤逐日估值；CASH 不計息；紙.一 債券腿依央行一個月定存利率逐日計息
    （與 paper_7030_tracker 同一資料源 data/rf_monthly.json）。尚未建倉者只輸出起始日說明。
三、真錢 Bb-90：帳本在本機（不進 repo），由 alpha_live_server /auto/strategy_line 呼叫本檔 live_line() 算，
    本檔排程輸出只放佔位。
四、指標（metrics()，所有線共用同一個函式）：樣本天數、累計差距 pp、年化差距 pp（≥60 交易日才給）、MDD、
    區塊自助法 90% 區間（≥60 日，配對日報酬、區塊長度 round(n^(1/3))、2000 次、固定種子）；
    判讀規則固定：<60 日「尚不足以判斷」，≥60 日累計差距＋區間，≥250 日加年化，不寫任何推論文字。
"""
from __future__ import annotations

import json
import sys as _phs_sys  # 先.八十二-1：price_history 改拆檔（data/price_history/），讀寫一律走 scripts/price_history_store.py
from pathlib import Path as _phs_Path
_phs_sys.path.insert(0, str(_phs_Path(__file__).resolve().parents[2] / "scripts"))
import price_history_store as PHS  # noqa: E402
import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RDATA = ROOT / "research" / "data"
OUT = DATA / "strategy_curves.json"
TZ = timezone(timedelta(hours=8))

BENCH = "0050"
HOLD = 5
FEE = 0.001425
STOCK_TAX = 0.003
MIN_DAYS = 60
ANN_DAYS = 250
BOOT_N = 2000
BOARDS = [("value", "估值榜", "value_board_v2"), ("momentum", "動能榜", "momentum_board"), ("future", "未來榜", "future_board")]
CORRECTION = "10/11 更正：舊算法重複計算，數字放大約 5 倍；10/11 更正進場點（改為快照後第一個收盤進場）"
# 先.七十-5（2026-10-11 總司令裁示）：每條線的「設計目標」。裁示沒有指定的線（紙.一b、紙.二）標「未標示」，不自行推定。
# 先.七十二-A4：前台改白話（守回撤（天條一）→守住回檔；贏大盤＋守回撤→贏大盤也守回檔）；內部代號只留在 id。
GOALS = {"live_bb90": "守住回檔", "paper_1": "守住回檔", "paper_3": "守住回檔",
         "paper_4": "贏大盤也守回檔", "paper_5": "賺波動溢價（只是研究）", "paper_7": "選股研究（低換手）", "board_value": "選股研究", "board_momentum": "選股研究", "board_future": "選股研究"}
# 先.七十五-5：尚未開始的模擬寫明原因（卡片「X 月 X 日開始」下方顯示）
PLANNED_WHY = {"paper_2": "選股資料還在預熱", "paper_5": "11 月起用當月真實資料開始記，不倒填",
               "paper_7": "2027 年第一個交易日起每季再平衡，不倒填；2027 行事曆未公布，1/4 為預估"}
POSITIONING = "守回檔的策略大漲時會落後 0050，這是設計；看滿 60 個交易日與最大跌幅"


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(p: Path) -> list:
    out = []
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    except (OSError, ValueError):
        pass
    return out


class Px:
    """price_history 的還原權息收盤查詢（與 0050 交易日曆對齊）。

    先.八十-12（2026-10-12）研究口徑統一：曲線一律用還原收盤（adj_close，含息、含分割還原），0050 灰線因此含息，
    與紙上追蹤同口徑。少數列缺 adj_close（每日排程剛寫入、尚未回溯）時，用該檔「之後最近一筆有 adj 的列」的
    adj/close 係數補（之後沒有就用 1），避免同一檔還原與未還原混用造成假跳動。"""

    def __init__(self, doc: dict):
        self.rows = {}
        for c, rs in (doc.get("prices") or {}).items():
            rs = sorted((r for r in rs if r.get("close") is not None), key=lambda r: r["date"])
            m, f = {}, 1.0
            for r in reversed(rs):
                if r.get("adj_close") is not None and r["close"]:
                    f = r["adj_close"] / r["close"]
                m[r["date"]] = r["adj_close"] if r.get("adj_close") is not None else r["close"] * f
            self.rows[c] = m
        self.cal = sorted(self.rows.get(BENCH, {}))

    def close(self, code: str, d: str):
        return self.rows.get(code, {}).get(d)

    def close_le(self, code: str, d: str):
        m = self.rows.get(code) or {}
        if d in m:
            return m[d]
        ks = [k for k in m if k <= d]
        return m[max(ks)] if ks else None

    def idx(self, d: str):
        try:
            return self.cal.index(d)
        except ValueError:
            return None


# ---------- 指標（所有線共用） ----------
def _mdd(nav: list) -> float:
    peak, mdd = -1e18, 0.0
    for v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return round(mdd * 100, 2)


def _rets(nav: list) -> list:
    return [nav[i] / nav[i - 1] - 1 for i in range(1, len(nav))]


def metrics(nav: list, bench: list) -> dict:
    n = len(nav) - 1
    out = {"days": max(n, 0), "cum_pct": None, "bench_cum_pct": None, "cum_gap_pp": None, "ann_gap_pp": None,
           "mdd_pct": None, "bench_mdd_pct": None, "ci90_pp": None, "verdict": "尚不足以判斷"}
    if n < 1:
        return out
    cs, cb = nav[-1] / nav[0] - 1, bench[-1] / bench[0] - 1
    out.update(cum_pct=round(cs * 100, 2), bench_cum_pct=round(cb * 100, 2), cum_gap_pp=round((cs - cb) * 100, 2),
               mdd_pct=_mdd(nav), bench_mdd_pct=_mdd(bench))
    if n >= MIN_DAYS:
        out["ann_gap_pp"] = round(((1 + cs) ** (252 / n) - (1 + cb) ** (252 / n)) * 100, 2)
        rs, rb = _rets(nav), _rets(bench)
        blk = max(2, round(n ** (1 / 3)))
        rng = random.Random(20261011)
        gaps = []
        for _ in range(BOOT_N):
            ps = pb = 1.0
            k = 0
            while k < n:
                s = rng.randrange(0, n - blk + 1)
                for j in range(s, min(s + blk, s + n - k)):
                    ps *= 1 + rs[j]
                    pb *= 1 + rb[j]
                k += blk
            gaps.append((ps - pb) * 100)
        gaps.sort()
        out["ci90_pp"] = [round(gaps[int(0.05 * BOOT_N)], 2), round(gaps[int(0.95 * BOOT_N) - 1], 2)]
        out["verdict"] = f"跟 0050 差 {out['cum_gap_pp']:+.1f} 個百分點（九成機率落在 {out['ci90_pp'][0]:+.1f}～{out['ci90_pp'][1]:+.1f}）"
        if n >= ANN_DAYS:
            out["verdict"] += f"；每年約差 {out['ann_gap_pp']:+.1f} 個百分點"
    return out


def _line(id_, label, group, status, dates, nav, comp_max, note="", start=None, extra=None, px: Px | None = None,
          bench_vals: list | None = None) -> dict:
    if bench_vals is None:
        b0 = px.close(BENCH, dates[0]) if dates else None
        bench_vals = [round(100 * px.close_le(BENCH, d) / b0, 4) for d in dates] if b0 else []
    navn = [round(100 * v / nav[0], 4) for v in nav] if nav else []
    ln = {"id": id_, "label": label, "group": group, "status": status, "started": bool(dates),
          "start_date": dates[0] if dates else start, "as_of": dates[-1] if dates else None,
          "dates": dates, "nav": navn, "bench": bench_vals, "comp_max_abs_pct": comp_max,
          "metrics": metrics(navn, bench_vals) if len(navn) >= 2 and len(bench_vals) == len(navn) else metrics([], []), "note": note}
    if extra:
        ln.update(extra)
    ln["goal"] = GOALS.get(id_, "未標示")
    return ln


def _placeholder(id_, label, group, status, start, note, extra=None) -> dict:
    d = {"id": id_, "label": label, "group": group, "status": status, "started": False, "start_date": start,
         "as_of": None, "dates": [], "nav": [], "bench": [], "comp_max_abs_pct": [], "metrics": metrics([], []), "note": note,
         "goal": GOALS.get(id_, "未標示")}
    if extra:
        d.update(extra)
    return d


# ---------- 一、選股三榜：重疊組合法 ----------
def board_line(board: str, ledger: dict, px: Px) -> dict:
    batches = []
    seen = set()
    # 先.七十七-4：進場點更正——每批在快照 taken_at 之後第一個收盤進場（picks_ledger 回填時寫入的 entry_date／entry_price），
    # 不再用快照前的 price_date／close_price（未來函數）；進場日當天沒有收盤的個股不進該批
    for s in sorted((x for x in ledger.get("snapshots", []) if x.get("board") == board), key=lambda x: (x["snapshot_date"], x.get("taken_at", ""))):
        picks = [p for p in s.get("picks", []) if p.get("entry_date") and p.get("entry_price")]
        if not picks:
            continue
        ed_ = picks[0]["entry_date"]
        if ed_ in seen:
            continue
        i0 = px.idx(ed_)
        if i0 is None:
            continue
        seen.add(ed_)
        # 先.八十-12：進場價改取同一條還原序列在進場日的值（帳本 entry_price 是原始收盤，不能跟還原後的後續價格混用）
        batches.append({"i0": i0, "picks": [(p["code"], px.close(p["code"], ed_) or float(p["entry_price"]))
                                            for p in picks if p["entry_date"] == ed_]})
    if not batches:
        return None
    start_i = min(b["i0"] for b in batches)
    last_i = len(px.cal) - 1
    dates, nav, comp = [px.cal[start_i]], [1.0], [0.0]
    for j in range(start_i + 1, last_i + 1):
        d, dp = px.cal[j], px.cal[j - 1]
        day = []
        mx = 0.0
        for b in batches:
            if not (b["i0"] < j <= b["i0"] + HOLD):
                continue
            v_prev = v_now = 0.0
            for code, entry in b["picks"]:
                p0 = entry if j - 1 == b["i0"] else px.close_le(code, dp)
                p1 = px.close_le(code, d)
                if p0 is None or p1 is None:
                    continue
                v_prev += p0 / entry
                v_now += p1 / entry
                mx = max(mx, abs(p1 / p0 - 1))
            if v_prev <= 0:
                continue
            r = v_now / v_prev - 1
            if j - 1 == b["i0"]:
                r = (1 + r) / (1 + FEE) - 1           # 進場成本（只扣一次）
            if j == b["i0"] + HOLD:
                r = (1 + r) * (1 - FEE - STOCK_TAX) - 1  # 出場成本（只扣一次）
            day.append(r)
        # 每批次固定佔 1/5 資金：某天沒有新快照（假日重跑、缺快照）時，那 1/5 視為現金、不計息，
        # 不讓其他批次放大權重頂替（否則少於 5 批在場時會被放大）
        r_day = sum(day) / HOLD
        dates.append(d)
        nav.append(nav[-1] * (1 + r_day))
        comp.append(round(mx * 100, 4))
    return {"dates": dates, "nav": nav, "comp": comp, "n_batches": len(batches)}


def board_status(strategies: dict, sid: str) -> str:
    for s in (strategies or {}).get("strategies", []):
        if s.get("id") == sid:
            st = str(s.get("status") or "")
            if "回測未通過" in st:
                return "回測未通過"
            if "回測通過" in st:
                return "回測通過"
            return "未回測" if not s.get("backtest") else "回測未通過"
    return "未回測"


# ---------- 二、紙上追蹤：事件之間逐日估值 ----------
def _rf_daily(rf_doc: dict, d: str) -> float:
    ms = [m for m in (rf_doc or {}).get("monthly", []) if m["date"][:7] <= d[:7]]
    pct = ms[-1]["rf_rate_pct"] if ms else 0.0
    return (1 + pct / 100) ** (1 / 365) - 1


def paper_line_from_log(events: list, px: Px, value_key: str = "values_post", bond_key: str | None = None, rf_doc=None):
    ev = sorted([e for e in events if e.get("date")], key=lambda e: e["date"])
    ev = [e for e in ev if e.get("event") in ("inception", "month_end", "gate_switch", "rebalance")] or ev
    if not ev:
        return None
    i_start = px.idx(ev[0]["date"])
    if i_start is None:
        return None
    dates, nav, comp = [], [], []
    k = 0
    hold: dict = {}
    base_px: dict = {}
    pending_fee = False
    for j in range(i_start, len(px.cal)):
        d = px.cal[j]
        while k < len(ev) and ev[k]["date"] <= d:
            e = ev[k]
            if value_key == "legacy_7030":
                hold = {BENCH: e["stock_value_post"], "BOND": e["bond_value_post"]}
            else:
                vp = e.get(value_key) or {s: e["nav"] * w for s, w in (e.get("weights_post") or {}).items()}
                hold = dict(vp)
            base_px = {s: px.close_le(s, e["date"]) for s in hold if s not in ("CASH", "BOND")}
            # 先.八十-12：紙上帳戶補扣手續費——建倉事件記為「成本不計（虛擬建倉）」者，在這裡依買進金額扣一次手續費
            # （0.1425%，現金與債券腿不算；之後的月底再平衡由 tracker 記在 rebalance_cost／values_post，不重複扣）
            # （建倉當天的淨值記為扣費前金額，費用從下一個交易日起反映，否則歸一化會把它抵銷掉）
            if e.get("event") == "inception" and not (e.get("rebalance_cost") or 0) and not (e.get("rebalance_trade") or {}).get("cost"):
                pending_fee = True
            k += 1
        if j > i_start:
            dp = px.cal[j - 1]
            mx = 0.0
            for s in list(hold):
                if s in ("BOND", "CASH"):  # 先.八十-12：現金也按一個月定存利率逐日計息（與紙.一債券腿同一資料源）
                    days = (date.fromisoformat(d) - date.fromisoformat(dp)).days
                    hold[s] *= (1 + _rf_daily(rf_doc, d)) ** days
                elif s != "CASH":
                    p0, p1 = px.close_le(s, dp), px.close_le(s, d)
                    if p0 and p1:
                        hold[s] *= p1 / p0
                        mx = max(mx, abs(p1 / p0 - 1))
            comp.append(round(mx * 100, 4))
        else:
            comp.append(0.0)
        dates.append(d)
        nav.append(sum(hold.values()))
        if pending_fee:
            for s_ in list(hold):
                if s_ not in ("CASH", "BOND"):
                    hold[s_] *= 1 - FEE
            pending_fee = False
    return {"dates": dates, "nav": nav, "comp": comp}


def nav_line_from_log(events: list, px: Px):
    """先.九十一-1：模擬 F（選擇權）沒有 price_history 收盤可估值，直接用帳本每天記的 nav（tracker 用期交所當日收盤重估）。
    對齊 0050 交易日曆、缺日沿用前值；comp 留空（成分最大漲跌幅檢查不適用，同真錢線）。"""
    ev = sorted([e for e in events if e.get("date") and e.get("nav") is not None], key=lambda e: (e["date"], e.get("logged_at", "")))
    if not ev:
        return None
    i_start = px.idx(ev[0]["date"])
    if i_start is None:
        return None
    by = {}
    for e in ev:
        by[e["date"]] = float(e["nav"])
    dates, nav, last = [], [], None
    for d in px.cal[i_start:]:
        last = by.get(d, last)
        if last is None:
            continue
        dates.append(d)
        nav.append(last)
    return {"dates": dates, "nav": nav, "comp": []}


def paper_lines(px: Px) -> list:
    rf = _load(DATA / "rf_monthly.json", {})
    out = []
    specs = [
        ("paper_1", "模擬 A 穩健", RDATA / "paper_7030_log.jsonl", "legacy_7030", None, "2026-10-01"),
        ("paper_1b", "模擬 D 三檔分散", RDATA / "paper_1b_log.jsonl", "values_post", None, "2026-10-08"),  # 先.七十五：10/08 建倉
        ("paper_2", "模擬 E 供給緊縮", RDATA / "paper_supply_v2_log.jsonl", "values_post", None, "2026-11-16"),
        ("paper_3", "模擬 B 景氣閘門", RDATA / "paper_3_log.jsonl", "values_post", None, "2026-10-08"),
        ("paper_4", "模擬 C 加速", RDATA / "paper_4_log.jsonl", "values_post", "R1-C", "2026-10-08"),
        ("paper_5", "模擬 F 賣波動", RDATA / "paper_5_log.jsonl", "nav_log", None, "2026-11-02"),  # 先.九十一-1：#444 紙上追蹤，11 月起不倒填
        ("paper_7", "模擬 G 個股低換手（營收驚喜）", RDATA / "paper_7_log.jsonl", "values_post", None, "2027-01-04"),  # 先.一一八-2：2027 第一個交易日起每季再平衡，不倒填
    ]
    # 先.八十-7（2026-10-12）：模擬 C（R1 信用利差閘門）是看過 2025–26 樣本外結果之後才設計的，前台必須標明
    design_note = {"paper_4": "看過 2025–26 結果後才設計", "paper_5": "學界已知現象、只是研究",
                   "paper_7": "營收驚喜這個指標最近一次重驗沒通過、只是研究"}  # 先.一一八-2：PREREG 已知限制
    # 先.八十一-5（2026-10-13 總司令裁示①）：信用利差閘門 1990–2003 殺測失敗（#435/#436）——繼續紙上追蹤，但不再是真錢候選
    candidacy = {"paper_5": "不提請真錢：試驗 #444 通過但 DSR 算不出、年化約 4.6%、每組名目約數百萬元（先.九十一-1）", "paper_3": "閘門殺測失敗（#435/#436），不再是真錢候選", "paper_4": "閘門殺測失敗（#435/#436），不再是真錢候選"}
    # 先.八十一-16（2026-10-13 總司令裁示）：模擬 B／C／D 的建倉日是 10/11 事後決定、用 10/08 收盤倒填，照實標明；
    # 之後一律禁止事後倒填建倉日（research/MARATHON_PROTOCOL.md §9）
    backdated = {k: "建倉日 10/08 是 10/11 事後決定、用 10/08 收盤倒填（之後新策略一律禁止事後倒填建倉日）"
                 for k in ("paper_1b", "paper_3", "paper_4")}
    # 先.一一八-2c：策略監控台點開看持股明細（App 另讀這個檔；未開始的線也帶，點開寫不倒填原因）
    holdings_file = {"paper_7": "data/paper_7.json"}
    for id_, label, path, vk, book, planned in specs:
        evs = _jsonl(path)
        if book:
            evs = [e for e in evs if e.get("book") == book]
        built = None
        try:
            built = (nav_line_from_log(evs, px) if vk == "nav_log" else paper_line_from_log(evs, px, vk, rf_doc=rf)) if evs else None
        except Exception as e:  # noqa: BLE001 -- 單一紙上追蹤壞掉只影響自己那條線（十二節）
            print(f"[warn] {label} 曲線失敗：{type(e).__name__}: {e}")
        if not built or len(built["dates"]) < 1:
            why = PLANNED_WHY.get(id_, "")
            out.append(_placeholder(id_, label, "paper", "模擬中", planned, f"{planned[5:].replace('-', '/')} 開始" + (f"（{why}）" if why else ""),
                                    extra={k: v for k, v in (("why", why), ("design_note", design_note.get(id_)),
                                                             ("candidacy", candidacy.get(id_)),
                                                             ("holdings_file", holdings_file.get(id_))) if v} or None))
            continue
        note = "依每天還原權息收盤估算；現金與定存按一個月定存利率計息；建倉已扣手續費"
        if vk == "nav_log":
            note = "每月賣 1 組台指選擇權價平跨式、持有到期（1 倍名目、滑價每口 1 點、手續費與期交稅已扣）；每天用期交所收盤重估，到期用官方最後結算價"
        # 先.七十五-3：月中建倉的第一期是部分期（到第一個月底為止），報表標明
        first = next((e for e in sorted(evs, key=lambda e: e.get("date", "")) if e.get("event") == "inception"), None)
        if first and first.get("partial_first_period"):
            note = f"第一期 {first['date'][5:].replace('-', '/')}～10/31 為部分期；" + note
        if design_note.get(id_):
            note = design_note[id_] + "；" + note
        ln = _line(id_, label, "paper", "模擬中", built["dates"], built["nav"], built["comp"], note=note, px=px)
        if design_note.get(id_):
            ln["design_note"] = design_note[id_]
        if candidacy.get(id_):
            ln["candidacy"] = candidacy[id_]
        if backdated.get(id_):
            ln["inception_note"] = backdated[id_]
        if holdings_file.get(id_):
            ln["holdings_file"] = holdings_file[id_]
        out.append(ln)
    return out


# ---------- 三、真錢 Bb-90（本機伺服器呼叫） ----------
def live_line(perf: dict | None) -> dict:
    """perf＝auto_ledger_view.perf_series() 的輸出（nav/bench 皆為「市值÷投入」比值）。只回百分比曲線，不回金額。"""
    if not perf or perf.get("error") or not perf.get("points"):
        return _placeholder("live_bb90", "自動投資", "live", "真錢", None,
                            (perf or {}).get("error") or "第一批還沒成交")
    pts = perf["points"]
    dates = [p["date"] for p in pts]
    nav = [p["nav"] for p in pts]
    bench = [round(100 * p["bench"] / pts[0]["bench"], 4) for p in pts]
    ln = _line("live_bb90", "自動投資", "live", "真錢", dates, nav, [], bench_vals=bench,
               note="含手續費、未含稅；灰線＝同一天同樣的錢改買 0050")
    return ln


def build() -> dict:
    px = Px(PHS.load(DATA / "price_history.json") if PHS.exists(DATA / "price_history.json") else {})
    if not px.cal:
        raise SystemExit("price_history.json 讀不到 0050 日線")
    ledger = _load(DATA / "picks_ledger.json", {}) or {}
    strategies = _load(DATA / "strategies.json", {}) or {}
    lines = [_placeholder("live_bb90", "自動投資", "live", "真錢", None, "連上電腦才看得到")]
    lines += paper_lines(px)
    for b, label, sid in BOARDS:
        st = board_status(strategies, sid)
        try:
            r = board_line(b, ledger, px)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {label} 曲線失敗：{type(e).__name__}: {e}")
            r = None
        if not r:
            lines.append(_placeholder(f"board_{b}", label, "board", st, None, "還沒有資料"))
            continue
        # 先.八十-9：picks_ledger 標了 data_status.complete=false 的批次（進出場日缺收盤或全市場缺日）在曲線檔照實註明
        inc = sum(1 for x in ledger.get("snapshots", []) if x.get("board") == b and (x.get("data_status") or {}).get("complete") is False)
        lines.append(_line(f"board_{b}", label, "board", st, r["dates"], r["nav"], r["comp"], px=px,
                           note=f"每天快照後第一個收盤買進前 20 名、各放 {HOLD} 個交易日，同時 {HOLD} 批各佔五分之一；已扣手續費與證交稅"
                                + (f"；{inc} 批有個股缺進出場收盤（停牌或資料缺），該批只算有價的個股" if inc else ""),
                           extra={"n_batches": r["n_batches"], "incomplete_batches": inc}))
    return {"meta": {"generated_at": datetime.now(TZ).isoformat(timespec="seconds"), "source": ".github/scripts/build_strategy_curves.py",
                     "bench": BENCH, "bench_note": "灰線是同期 0050",
                     "price_asof": px.cal[-1], "correction": CORRECTION,
                     "rules": {"min_days": MIN_DAYS, "ann_days": ANN_DAYS, "bootstrap": f"區塊自助法、{BOOT_N} 次、90% 區間"},
                     "positioning": POSITIONING,
                     # 先.八十一-16：先.八十-12（10/12）起的計算口徑，前台「跟 0050 比」頁固定顯示這一行
                     "method_note": "口徑（10/12 起）：各線用還原權息收盤；0050 灰線同樣含息（還原權息收盤）；模擬帳戶的現金與定存按一個月定存利率計息；建倉已扣手續費",
                     "disclaimer": ""},
            "lines": lines}


def main() -> int:
    doc = build()
    s = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    try:
        o = json.loads(old) if old else {}
        if o.get("lines") == doc["lines"]:
            print("strategy_curves.json 內容未變，不重寫")
            return 0
    except ValueError:
        pass
    OUT.write_text(s, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for ln in doc["lines"]:
        m = ln["metrics"]
        print(f"{ln['label']}：{ln['status']}，{m['days']} 日，累計 {m['cum_pct']}% vs 0050 {m['bench_cum_pct']}%，MDD {m['mdd_pct']}%，{ln['note'][:30] if not ln['started'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
