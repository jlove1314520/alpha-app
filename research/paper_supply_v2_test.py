"""紙.二（paper_supply_v2.py）合成資料自測。全程只用人造資料，不讀任何真實歷史行情、不算任何歷史績效。

跑法：python research/paper_supply_v2_test.py（全 PASS 才算過；失敗即非零退出）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_supply_v2 as pv2  # noqa: E402
import supply_tightness_core as core  # noqa: E402

TZ = pv2.TZ
BR, SR = core.rates(1.0)


def now_at(y, m, d, hh=15, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


# ───────────────────────── 合成資料 ─────────────────────────
def synth_frames(rng, first="2023Q1", last="2026Q3", with_bs=True, with_cf=True):
    qs = pd.period_range(first, last, freq="Q")
    fs, bs, cf = [], [], []
    base = rng.uniform(50, 200)
    cum = 0.0
    for i, q in enumerate(qs):
        d = str(q.end_time.date())
        rev = base * (1 + 0.02 * i) * rng.uniform(0.9, 1.1)
        gm = rng.uniform(0.2, 0.4)
        for t, v in (("Revenue", rev), ("GrossProfit", rev * gm), ("CostOfGoodsSold", rev * (1 - gm))):
            fs.append({"date": d, "type": t, "value": v})
        for t, v in (("TotalAssets", 1000 * rng.uniform(0.8, 1.2)), ("OtherCurrentLiabilities", 50 * rng.uniform(0.5, 1.5)),
                     ("CurrentContractLiabilities", 20 * rng.uniform(0.5, 1.5)), ("Inventories", 100 * rng.uniform(0.7, 1.3))):
            bs.append({"date": d, "type": t, "value": v})
        cum = 0.0 if q.quarter == 1 else cum
        cum -= rng.uniform(5, 15)
        cf.append({"date": d, "type": "PropertyAndPlantAndEquipment", "value": cum})
    f = pd.DataFrame(fs)
    b = pd.DataFrame(bs) if with_bs else pd.DataFrame(columns=["date", "type", "value"])
    c = pd.DataFrame(cf) if with_cf else None
    return f, b, c


def synth_bars(rng, cal, n0=50.0):
    c = n0 * np.exp(np.cumsum(rng.normal(0, 0.015, len(cal))))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.003, len(cal)))
    h = np.maximum(o, c) * 1.005
    lo = np.minimum(o, c) * 0.995
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c, "Adj Close": c}, index=cal)


class Synth:
    def __init__(self, seed=7, industries=(("A", 28), ("B", 27), ("C", 5)), settled=True, miss_prices=(), unsettled_codes=()):
        rng = np.random.default_rng(seed)
        self.cal = pd.bdate_range("2024-09-02", "2027-12-31")
        rows = []
        for ind, n in industries:
            for j in range(n):
                rows.append((f"{len(rows) + 1000}", ind))
        self.uni = pd.DataFrame({"code": [r[0] for r in rows], "industry": [r[1] for r in rows], "suffix": ".TW"})
        self.stm = {c: synth_frames(rng) for c in self.uni["code"]}
        self.bars = {c: synth_bars(rng, self.cal) for c in self.uni["code"]}
        self.bars50 = synth_bars(rng, self.cal, 100.0)
        self.settled = settled
        self.mtime = pd.Timestamp("2026-11-15 12:00", tz=TZ).timestamp() if settled else pd.Timestamp("2026-10-01", tz=TZ).timestamp()
        self.miss = set(miss_prices)
        self.fail_calendar = False
        self.fail_prices = False
        self.fail_refresh = False
        self.fail_msg = "FinMind rejected the request (HTTP 400, synthetic)"
        self.refresh_calls = 0
        self.drop_target = False
        self.unsettled_codes = set(unsettled_codes)
        self.px_unready = set()
        self.px_calls = 0
        self.fail_px = False
        self.px_msg = "FinMind rejected the request (HTTP 400, synthetic)"
        self.events_ok = True
        self.events_refreshed = 0
        self.fail_events = False
        self.fb_codes = set()
        self.fallback = set()
        self.open_override = {}

    def calendar(self, now):
        if self.fail_calendar:
            raise RuntimeError("synthetic calendar failure")
        d = self.bars50["Adj Close"]
        cut = pd.Timestamp(now.year, now.month, now.day)
        d = d[d.index <= cut]
        if len(d) and d.index[-1] == cut and (now.hour, now.minute) < pv2.CLOSE_HHMM:
            d = d.iloc[:-1]
        return d

    def universe(self):
        return self.uni

    def stmt_state(self, code):
        f, b, c = self.stm[code]
        old = pd.Timestamp("2026-10-01", tz=TZ).timestamp()
        if self.drop_target or not self.settled or code in self.unsettled_codes:
            f = f[f["date"] != "2026-09-30"]
            b = b[b["date"] != "2026-09-30"]
            c = c[c["date"] != "2026-09-30"]
        mt = old if code in self.unsettled_codes else self.mtime
        return {"fs": (f, mt), "bs": (b, mt), "cf": (c, mt)}

    def refresh_stmt(self, code, which):
        self.refresh_calls += 1
        if self.fail_refresh:
            raise RuntimeError(self.fail_msg)

    def prices(self, rows, start, end):
        if self.fail_prices:
            raise RuntimeError("synthetic price failure")
        self.fallback = {c for c, _ in rows if c in self.fb_codes and c not in self.miss}
        return {c: self.bars[c].loc[start:end] for c, _ in rows if c not in self.miss}

    def events_ready(self, need):
        return self.events_ok

    def refresh_events(self, max_age_hours=0):
        self.events_refreshed += 1
        if self.fail_events:
            raise RuntimeError(self.px_msg)
        self.events_ok = True

    def px_pending(self, code, need):
        return ["TaiwanStockPrice"] if code in self.px_unready else []

    def refresh_px(self, code, which):
        self.px_calls += 1
        if self.fail_px:
            raise RuntimeError(self.px_msg)
        self.px_unready.discard(code)

    def ensure_px(self, codes, last_bar):
        return 0

    def official_open(self, code, date):
        if (code, str(date.date())) in self.open_override:
            return self.open_override[(code, str(date.date()))]
        b = self.bars.get(code)
        return float(b.at[date, "Open"]) if b is not None and date in b.index else None


# ───────────────────────── 測試 ─────────────────────────
def test_rebalance_days():
    cal = pd.bdate_range("2026-01-01", "2027-12-31")
    got = {str(p): str(pv2.rebalance_day(cal, pv2.deadline(p)).date())
           for p in [pd.Period("2026Q3"), pd.Period("2026Q4"), pd.Period("2027Q1"), pd.Period("2027Q2"), pd.Period("2027Q3")]}
    assert got == {"2026Q3": "2026-11-16", "2026Q4": "2027-04-01", "2027Q1": "2027-05-17",
                   "2027Q2": "2027-08-16", "2027Q3": "2027-11-15"}, got
    assert pv2.target_period(pd.Timestamp("2026-11-16")) == pd.Period("2026Q3")
    assert pv2.target_period(pd.Timestamp("2027-04-01")) == pd.Period("2026Q4")
    assert pv2.target_period(pd.Timestamp("2027-05-17")) == pd.Period("2027Q1")


def test_quarter_table_identical_to_frozen_definition():
    import supply_tightness_panel as sp
    rng = np.random.default_rng(1)
    for kw in ({}, {"with_bs": False}, {"with_cf": False}):
        fs, bs, cf = synth_frames(rng, first="2021Q1", last="2024Q4", **kw)
        data = {"TaiwanStockFinancialStatements": fs, "TaiwanStockBalanceSheet": bs, "TaiwanStockCashFlowsStatement": cf}

        def fake(ds, code, suf=None, data=data):
            d = data[ds]
            return None if d is None else d.copy()

        old = sp._orig_read
        sp._orig_read = fake
        try:
            ref = sp._quarter_table_fs_tolerant("X")
        finally:
            sp._orig_read = old
        mine = pv2.quarter_table_from_frames(fs, bs, cf)
        for k in pv2.COLS:
            a, b = ref[k].astype(float), mine[k].astype(float)
            assert a.index.equals(b.index), kw
            assert ((a - b).abs().fillna(0) < 1e-12).all() and (a.isna() == b.isna()).all(), (kw, k)


def _signal_inputs(seed=7):
    s = Synth(seed)
    uni = s.uni
    tables = {c: pv2.quarter_table_from_frames(*s.stm[c]) for c in uni["code"]}
    R = pd.Timestamp("2026-11-16")
    bars = s.prices([(c, ".TW") for c in uni["code"]], R - pd.DateOffset(months=15), pd.Timestamp("2026-11-16"))
    return s, uni, tables, bars, R


def test_selection_rules():
    s, uni, tables, bars, R = _signal_inputs()
    per = pv2.target_period(R)
    sig = pv2.build_signal(R, per, uni, tables, bars, [])
    picks = sig["picks"]
    assert len(picks) == 20 and sig["n_cash_slots"] == 0, len(picks)
    assert sig["n_scored"] == 60 and all(p["bucket"] != "C" for p in picks)
    assert all(p["rank"] is not None and p["rank"] <= 20 for p in picks)
    sc = [p["score"] for p in picks]
    assert sc == sorted(sc, reverse=True)
    n_fin = lambda p: sum(p[k] is not None for k in pv2.COLS)  # noqa: E731
    assert all(n_fin(p) >= 3 for p in picks)
    # 至少 3 個指標可得：把入選者的 I1、I2 設成 NaN，必須被剔除
    victim = picks[0]["code"]
    t2 = dict(tables)
    t = tables[victim].copy()
    t.loc[per, ["I1", "I2"]] = np.nan
    t2[victim] = t
    sig2 = pv2.build_signal(R, per, uni, t2, bars, [])
    assert victim not in [p["code"] for p in sig2["picks"]] and sig2["n_scored"] == 59
    # 遲滯帶：排名 25 的前期持股應被保留，排名 20 者被擠出
    old = pv2.TOP_N
    pv2.TOP_N = 30
    try:
        wide = pv2.build_signal(R, per, uni, tables, bars, [])["picks"]
    finally:
        pv2.TOP_N = old
    r25, r20 = wide[24]["code"], wide[19]["code"]
    sig3 = pv2.build_signal(R, per, uni, tables, bars, [r25])
    codes3 = [p["code"] for p in sig3["picks"]]
    assert r25 in codes3 and r20 not in codes3 and len(codes3) == 20
    # 前期持股排名 > 30 不保留
    r35 = None
    old = pv2.TOP_N
    pv2.TOP_N = 36
    try:
        w36 = pv2.build_signal(R, per, uni, tables, bars, [])["picks"]
    finally:
        pv2.TOP_N = old
    if len(w36) >= 35:
        r35 = w36[34]["code"]
        assert r35 not in [p["code"] for p in pv2.build_signal(R, per, uni, tables, bars, [r35])["picks"]]
    # 落後池不足 20 檔 → 留現金，不補猜
    tiny = uni.iloc[:10].reset_index(drop=True)
    sig4 = pv2.build_signal(R, per, tiny, tables, bars, [])
    assert len(sig4["picks"]) <= 10 and sig4["n_cash_slots"] == 20 - len(sig4["picks"]) > 0
    # 首次換股日之前一律拒絕
    try:
        pv2.build_signal(pd.Timestamp("2026-10-01"), per, uni, tables, bars, [])
        raise AssertionError("應拒絕 R < 2026-11-16")
    except ValueError:
        pass
    # 快照只用 R 之前的 bar：把 R 當日及之後的價格亂改，結果不變
    b2 = {c: d.copy() for c, d in bars.items()}
    for d in b2.values():
        d.loc[d.index >= R, ["Open", "High", "Low", "Close", "Adj Close"]] *= 7.0
    assert [p["code"] for p in pv2.build_signal(R, per, uni, tables, b2, [])["picks"]] == [p["code"] for p in picks]


def _flat_bars(cal, codes, px=100.0):
    out = {}
    for c in codes:
        out[c] = pd.DataFrame({"Open": px, "High": px * 1.01, "Low": px * 0.99, "Close": px, "Adj Close": px}, index=cal)
    return out


def test_simulate_hand_check():
    cal = pd.bdate_range("2026-11-16", periods=40)
    bars = _flat_bars(cal, ["a", "b", "c"])
    sg = [{"period": "2026Q3", "after": cal[2], "picks": ["a", "b"]}]
    r = pv2.simulate(sg, cal, bars, BR, SR)
    assert r["t0"] == 3 and len(r["fills"]) == 2 and all(f["side"] == "buy" and f["date"] == cal[3] for f in r["fills"])
    assert abs(r["fills"][0]["value"] - 50000.0) < 1e-6 and abs(r["fills"][0]["cost"] - 50000 * BR) < 1e-6
    assert abs(r["eq"][0] - (1 - 0.1 * BR)) < 1e-9, r["eq"][0]
    assert abs(r["eq"][-1] - r["eq"][0]) < 1e-3     # 價格不動、只有微幅再平衡成本
    # 換股：a 賣出、c 買進
    sg2 = sg + [{"period": "2027Q1", "after": cal[10], "picks": ["b", "c"]}]
    r2 = pv2.simulate(sg2, cal, bars, BR, SR)
    sides = {(f["date"], f["code"], f["side"]) for f in r2["fills"]}
    assert (cal[11], "a", "sell") in sides and (cal[11], "c", "buy") in sides
    assert set(r2["held"]) == {"b", "c"}
    # 漲停鎖死：c 在成交日開盤＝最高＝最低且≥前收×1.095 → 當天不買，隔天補
    b3 = _flat_bars(cal, ["a", "b", "c"])
    c = b3["c"].copy()
    c.iloc[11] = [110.0, 110.0, 110.0, 110.0, 110.0]
    c.iloc[12:] = 110.0
    b3["c"] = c
    r3 = pv2.simulate(sg2, cal, b3, BR, SR)
    cb = [f for f in r3["fills"] if f["code"] == "c" and f["side"] == "buy"]
    assert len(cb) == 1 and cb[0]["date"] == cal[12], cb
    # 跌停鎖死賣不掉 → 第 10 個交易日強制以收盤賣出
    b4 = _flat_bars(cal, ["a", "b", "c"])
    a = b4["a"].copy()
    a.iloc[10] = [100.0, 100.0, 100.0, 100.0, 100.0]
    a.iloc[11:] = [90.0, 90.0, 90.0, 90.0, 90.0]
    # 第一天 11 日跌停（90 <= 100*0.905），之後價格維持 90 且 open=high=low 但前收 90 不再是跌停 → 其實 12 日可賣
    r4 = pv2.simulate(sg2, cal, {**b4, "a": a}, BR, SR)
    sa = [f for f in r4["fills"] if f["code"] == "a" and f["side"] == "sell"]
    assert len(sa) == 1 and sa[0]["date"] == cal[12], sa
    # 缺價（沒有 c 的任何 bar）→ 不補猜，不成交
    b5 = _flat_bars(cal, ["a", "b"])
    r5 = pv2.simulate(sg2, cal, b5, BR, SR)
    assert not [f for f in r5["fills"] if f["code"] == "c"]
    # 尚無啟動訊號 → None
    assert pv2.simulate([{"period": "x", "after": cal[-1], "picks": ["a"]}], cal, bars, BR, SR) is None


def test_bench_nav():
    cal = pd.bdate_range("2026-11-16", periods=6)
    adj = pd.Series([100, 100, 100, 101, 102.01, 102.01], index=cal, dtype=float)
    n = pv2.bench_nav(adj, 3, BR)
    assert abs(n[0] - 1.01 * (1 - BR)) < 1e-12 and abs(n[1] - 1.0201 * (1 - BR)) < 1e-12


def _lines(p):
    return [] if not Path(p).exists() else Path(p).read_text(encoding="utf-8").splitlines()


def test_run_idempotent_and_flow():
    with tempfile.TemporaryDirectory() as td:
        lp, sp_ = Path(td) / "log.jsonl", Path(td) / "state.json"
        src = Synth()
        kw = dict(log_path=lp, state_path=sp_, verbose=False)
        # 首次換股日之前：什麼都不寫
        r0 = pv2.run(src, now_at(2026, 10, 20), **kw)
        assert not lp.exists() and r0["new_events"] == 0
        r00 = pv2.run(src, now_at(2026, 9, 1), **kw)
        assert r00["status"] == "before_window" and not lp.exists()
        # 11/14 週六：週末不產生換股（找不到換股日）
        pv2.run(src, now_at(2026, 11, 14), **kw)
        assert not lp.exists()
        # 換股日 11/16 收盤後：產生訊號
        r1 = pv2.run(src, now_at(2026, 11, 16), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        sg = [e for e in ev if e["type"] == "signal"]
        assert len(sg) == 1 and sg[0]["R"] == "2026-11-16" and sg[0]["after_date"] == "2026-11-16", r1
        assert len(sg[0]["picks"]) == 20 and not [e for e in ev if e["type"] == "fill"]
        n1 = len(_lines(lp))
        # 同一時間重跑：不重複寫入
        pv2.run(src, now_at(2026, 11, 16), **kw)
        assert len(_lines(lp)) == n1
        # 11/17 收盤：產生 20 筆買進成交
        pv2.run(src, now_at(2026, 11, 17), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        fills = [e for e in ev if e["type"] == "fill"]
        assert len(fills) == 20 and {f["date"] for f in fills} == {"2026-11-17"} and all(f["side"] == "buy" for f in fills)
        assert all(abs(f["cost"] - f["value"] * BR) < 0.02 for f in fills)
        # 每次重跑逐位元相同（冪等）
        before = Path(lp).read_bytes()
        pv2.run(src, now_at(2026, 11, 17), **kw)
        pv2.run(src, now_at(2026, 11, 17, 20), **kw)
        assert Path(lp).read_bytes() == before
        # 12/2：記錄 11 月月末淨值＋同期 0050 還原淨值
        pv2.run(src, now_at(2026, 12, 2), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        navs = [e for e in ev if e["type"] == "nav"]
        assert [n["month"] for n in navs] == ["2026-11"] and navs[0]["date"] == "2026-11-30"
        assert navs[0]["nav"] > 0 and navs[0]["bench_nav_0050_adj"] > 0
        before = Path(lp).read_bytes()
        pv2.run(src, now_at(2026, 12, 2), **kw)
        assert Path(lp).read_bytes() == before
        # 舊事件原樣保留（append-only）：前 n1 行與第一次寫入完全相同
        assert _lines(lp)[: len(sg)] [0] == json.dumps(sg[0], ensure_ascii=False, default=pv2._js)
        # 壞行容忍：插入壞行，不改寫既有內容，只多一則警告
        with open(lp, "ab") as f:
            f.write(b"{garbage\n")
        snap = Path(lp).read_bytes()
        pv2.run(src, now_at(2026, 12, 3), **kw)
        assert Path(lp).read_bytes().startswith(snap)
        ev, bad = pv2.load_log(lp)
        assert bad == 1 and any(e["type"] == "warning" and e["reason"] == "log_bad_lines" for e in ev)


def test_degrade_no_fabrication():
    with tempfile.TemporaryDirectory() as td:
        lp, sp_ = Path(td) / "log.jsonl", Path(td) / "state.json"
        kw = dict(log_path=lp, state_path=sp_, verbose=False)
        # 日曆來源失敗：只留警告，不產生訊號
        s1 = Synth()
        s1.fail_calendar = True
        r = pv2.run(s1, now_at(2026, 11, 16), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        assert r["status"] == "degraded" and [e["type"] for e in ev] == ["warning"] and ev[0]["reason"] == "calendar_failed"
        # 價格覆蓋不足：不產生訊號
        s2 = Synth(miss_prices=[str(i) for i in range(1000, 1030)])
        lp2 = Path(td) / "log2.jsonl"
        pv2.run(s2, now_at(2026, 11, 16), log_path=lp2, state_path=Path(td) / "s2.json", verbose=False)
        ev = [json.loads(x) for x in _lines(lp2)]
        assert not [e for e in ev if e["type"] == "signal"] and any(e.get("reason") == "price_coverage_low" for e in ev)
        # 已有訊號後價格來源失敗：不補猜成交，也不影響既有訊號
        s3 = Synth()
        lp3 = Path(td) / "log3.jsonl"
        k3 = dict(log_path=lp3, state_path=Path(td) / "s3.json", verbose=False)
        pv2.run(s3, now_at(2026, 11, 16), **k3)
        s3.fail_prices = True
        pv2.run(s3, now_at(2026, 11, 17), **k3)
        ev = [json.loads(x) for x in _lines(lp3)]
        assert len([e for e in ev if e["type"] == "signal"]) == 1 and not [e for e in ev if e["type"] == "fill"]
        assert any(e.get("reason") == "price_fetch_failed" for e in ev)
        s3.fail_prices = False
        pv2.run(s3, now_at(2026, 11, 17), **k3)
        assert len([e for e in [json.loads(x) for x in _lines(lp3)] if e["type"] == "fill"]) == 20  # 恢復後補上，值為當日實際開盤
        # 持股缺價：只警告，其他檔照常
        s4 = Synth()
        lp4 = Path(td) / "log4.jsonl"
        k4 = dict(log_path=lp4, state_path=Path(td) / "s4.json", verbose=False)
        pv2.run(s4, now_at(2026, 11, 16), **k4)
        victim = json.loads(_lines(lp4)[0])["picks"][0]["code"]
        s4.miss = {victim}
        pv2.run(s4, now_at(2026, 11, 17), **k4)
        ev = [json.loads(x) for x in _lines(lp4)]
        assert len([e for e in ev if e["type"] == "fill"]) == 19 and any(e.get("reason") == "no_bars" for e in ev)


def test_data_unready_skip_and_refresh():
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / "log.jsonl"
        kw = dict(log_path=lp, state_path=Path(td) / "st.json", verbose=False)
        src = Synth(settled=False)
        src.fail_refresh = True
        # 換股日後 3 個交易日：資料未備 → 警告，不產生訊號、不 skip
        pv2.run(src, now_at(2026, 11, 19), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        assert not [e for e in ev if e["type"] in ("signal", "skipped_data_unready")]
        assert src.refresh_calls == 5 and any(e.get("reason") == "refresh_failed" for e in ev)   # 連續 5 次失敗即停
        # 封鎖類錯誤：立刻停手（只打 1 次，不再硬打）
        srcb = Synth(settled=False)
        srcb.fail_refresh = True
        srcb.fail_msg = "FinMind 目前處於封鎖冷卻中（synthetic）"
        pv2.run(srcb, now_at(2026, 11, 19), log_path=Path(td) / "lb.jsonl", state_path=Path(td) / "sb.json", verbose=False)
        assert srcb.refresh_calls == 1
        # 逾 10 個交易日：終局 skip，之後即使資料齊也不補算
        pv2.run(src, now_at(2026, 12, 2), **kw)
        ev = [json.loads(x) for x in _lines(lp)]
        assert [e["key"] for e in ev if e["type"] == "skipped_data_unready"] == ["skip|2026Q3"]
        src.mtime = pd.Timestamp("2026-12-03 12:00", tz=TZ).timestamp()
        pv2.run(src, now_at(2026, 12, 3), **kw)
        assert not [e for e in [json.loads(x) for x in _lines(lp)] if e["type"] == "signal"]
        # 本輪呼叫預算上限
        src2 = Synth(settled=False)
        calls = []
        src2.refresh_stmt = lambda c, w: calls.append((c, tuple(w)))
        pv2.run(src2, now_at(2026, 11, 16), budget=7, log_path=Path(td) / "l2.jsonl", state_path=Path(td) / "s2.json", verbose=False)
        assert len(calls) == 7
        # 期限日（含）之前不抓財報：沒有 D+1 之後的快取不可能「塵埃落定」，抓了也是白抓
        src3 = Synth(settled=False)
        n = []
        src3.refresh_stmt = lambda c, w: n.append(1)
        pv2.run(src3, now_at(2026, 11, 14), log_path=Path(td) / "l3.jsonl", state_path=Path(td) / "s3.json", verbose=False)
        assert not n
        # 缺目標季財報的個股視為缺值（不補猜），仍可在其餘個股上計分
        src4 = Synth()
        src4.drop_target = True
        lp4 = Path(td) / "l4.jsonl"
        pv2.run(src4, now_at(2026, 11, 16), log_path=lp4, state_path=Path(td) / "s4.json", verbose=False)
        sg = [json.loads(x) for x in _lines(lp4) if '"signal"' in x]
        assert sg and sg[0]["n_scored"] == 0 and sg[0]["picks"] == [] and sg[0]["n_cash_slots"] == 20


def test_report_gate():
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / "log.jsonl"
        lp.write_text("", encoding="utf-8")
        assert pv2.report(Synth(), now_at(2027, 3, 1), log_path=lp) is None     # 滿 4 季前不輸出任何績效數字


# ---------------- 先.六-一 新增：價格來源／覆蓋率 ----------------
class FakeFC:
    """假 finmind_client：只提供快取路徑與記錄 _fetch 呼叫，不連網。"""
    def __init__(self, root):
        self.root = Path(root)
        self.calls = []

    def _cache_path(self, ds, code, start, end):
        return self.root / f"{ds}__{code or 'ALL'}__{start}__{end or 'latest'}.parquet"

    def _fetch(self, ds, code, start, end, force_refresh=False):
        self.calls.append((ds, code))


def _live(td):
    s = pv2.LiveSource.__new__(pv2.LiveSource)
    s.fc = FakeFC(td)
    s.fallback = set()
    s.calendar_source = "finmind"
    s._ph = None
    return s


def _put(s, ds, code, df, mtime=None):
    p = s.fc._cache_path(ds, code, pv2.PRICE_START, None)
    df.to_parquet(p)
    if mtime is not None:
        import os
        os.utime(p, (mtime, mtime))


def _raw_px(dates, closes):
    c = np.array(closes, float)
    return pd.DataFrame({"date": dates, "stock_id": "X", "open": c * 0.99, "max": c * 1.01, "min": c * 0.98, "close": c})


def _evs(p):
    return [json.loads(x) for x in _lines(p)]


def test_adjust_bars_matches_backtest_logic():
    dates = [str(d.date()) for d in pd.bdate_range("2026-01-05", periods=30)]
    closes = [100 + i for i in range(30)]
    raw = _raw_px(dates, closes)
    import adjust as adj

    def ref(raw, div, spl, cr, pv):
        r = raw.sort_values("date")
        close = dict(zip(r["date"], r["close"]))
        ds = r["date"].tolist()
        ev = adj._combine_adjustment_events(div, spl, cr, pv, close, ds)
        fac = pd.Series(1.0, index=r["date"].values)
        d_arr = np.array(ds)
        for _, e in ev.sort_values("ex_date", ascending=False).iterrows():
            fac[d_arr < e["ex_date"]] = fac[d_arr < e["ex_date"]] * e["factor"]
        return r["close"].astype(float).values * fac.values

    div = pd.DataFrame([{"CashExDividendTradingDate": dates[10], "StockExDividendTradingDate": "", "CashEarningsDistribution": 2.0,
                         "StockEarningsDistribution": 0.0, "CashIncreaseSubscriptionRate": 0.0, "CashIncreaseSubscriptionpRrice": 0.0}])
    spl = pd.DataFrame([{"date": dates[20], "stock_id": "X", "before_price": 120.0, "after_price": 60.0}])
    cr = pd.DataFrame([{"date": dates[25], "stock_id": "X", "ClosingPriceonTheLastTradingDay": 100.0, "PostReductionReferencePrice": 90.0}])
    pvc = pd.DataFrame([{"date": dates[15], "stock_id": "X", "before_close": 100.0, "after_ref_close": 100.0}])
    got = pv2.adjust_bars(raw, div, spl, cr, pvc)
    exp = ref(raw, div, spl, cr, pvc)
    assert np.allclose(got["Adj Close"].values, exp, rtol=1e-12), (got["Adj Close"].values[:3], exp[:3])
    f_div = (closes[9] - 2.0) / closes[9]
    assert abs(got["Adj Close"].iloc[0] - closes[0] * 0.5 * 0.9 * f_div) < 1e-9
    assert abs(got["Adj Close"].iloc[-1] - closes[-1]) < 1e-9
    assert np.allclose(got["Open"].values, np.array(closes) * 0.99) and np.allclose(got["Close"].values, closes)
    plain = pv2.adjust_bars(raw, None, None, None, None)
    assert np.allclose(plain["Adj Close"].values, closes)
    assert pv2.adjust_bars(None, None, None, None, None) is None and pv2.adjust_bars(raw.iloc[0:0], None, None, None, None) is None
    bad = raw.copy()
    bad.loc[3, "close"] = 0.0
    bad.loc[4, "open"] = 0.0
    g2 = pv2.adjust_bars(bad, None, None, None, None)
    assert len(g2) == 29 and np.isnan(g2["Open"].iloc[3])


def test_live_source_finmind_primary_and_fallback():
    import types
    with tempfile.TemporaryDirectory() as td:
        s = _live(td)
        dates = [str(d.date()) for d in pd.bdate_range("2026-01-05", periods=40)]
        cl = [100.0] * 40
        _put(s, "TaiwanStockPrice", "1000", _raw_px(dates, cl))
        _put(s, "TaiwanStockPrice", "1001", _raw_px(dates, cl))
        yf_calls = []

        def fake_yf(self, rows, start, end):
            yf_calls.append([c for c, _ in rows])
            idx = pd.bdate_range("2026-01-05", periods=40)
            return {c: pd.DataFrame({"Open": 50.0, "High": 51.0, "Low": 49.0, "Close": 50.0, "Adj Close": 50.0}, index=idx) for c, _ in rows}

        s._yf_prices = types.MethodType(fake_yf, s)
        rows = [("1000", ".TW"), ("1001", ".TW"), ("1002", ".TW")]
        st, en = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-12-31")
        out = s.prices(rows, st, en)
        assert set(out) == {"1000", "1001", "1002"} and s.fallback == {"1000", "1001", "1002"}
        _put(s, "TaiwanStockSplitPrice", "", pd.DataFrame([{"date": dates[20], "stock_id": "1001", "before_price": 100.0, "after_price": 50.0}]))
        _put(s, "TaiwanStockParValueChange", "", pd.DataFrame({"date": [], "stock_id": [], "before_close": [], "after_ref_close": []}))
        out = s.prices(rows, st, en)
        assert s.fallback == {"1002"} and yf_calls[-1] == ["1002"]
        assert abs(out["1000"]["Adj Close"].iloc[0] - 100.0) < 1e-9 and abs(out["1001"]["Adj Close"].iloc[0] - 50.0) < 1e-9
        assert abs(out["1001"]["Open"].iloc[0] - 99.0) < 1e-9
        o2 = s.prices(rows[:2], pd.Timestamp(dates[10]), pd.Timestamp(dates[20]))
        assert str(o2["1000"].index[0].date()) == dates[10] and str(o2["1000"].index[-1].date()) == dates[20] and s.fallback == set()
        s._yf_prices = types.MethodType(lambda self, rows, a, b: {}, s)
        out = s.prices(rows, st, en)
        assert set(out) == {"1000", "1001"} and s.fallback == set()


def test_official_open_lookup():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "price_history.json"
        p.write_text(json.dumps({"meta": {}, "prices": {"1000": [{"date": "2026-11-17", "open": 50.5, "close": 51.0},
                                                                   {"date": "2026-11-18", "open": None, "close": 51.0}]}}), encoding="utf-8")
        old = pv2.PRICE_HISTORY_PATH
        pv2.PRICE_HISTORY_PATH = p
        try:
            s = _live(td)
            assert s.official_open("1000", pd.Timestamp("2026-11-17")) == 50.5
            assert s.official_open("1000", pd.Timestamp("2026-11-18")) is None
            assert s.official_open("1000", pd.Timestamp("2026-11-19")) is None and s.official_open("9999", pd.Timestamp("2026-11-17")) is None
            pv2.PRICE_HISTORY_PATH = Path(td) / "missing.json"
            assert _live(td).official_open("1000", pd.Timestamp("2026-11-17")) is None
        finally:
            pv2.PRICE_HISTORY_PATH = old


def _mk(td, name):
    return dict(log_path=Path(td) / f"{name}.jsonl", state_path=Path(td) / f"{name}.json", verbose=False)


def test_source_switch_flags_and_xcheck():
    with tempfile.TemporaryDirectory() as td:
        s = Synth()
        k = _mk(td, "a")
        pv2.run(s, now_at(2026, 11, 16), **k)
        sg = [e for e in _evs(k["log_path"]) if e["type"] == "signal"][0]
        assert sg["price_fallback_codes"] == [] and "備援" not in sg["price_source"]
        picks = [p["code"] for p in sg["picks"]]
        s.fb_codes = set(picks[:2])
        pv2.run(s, now_at(2026, 11, 17), **k)
        ev = _evs(k["log_path"])
        fills = {e["code"]: e for e in ev if e["type"] == "fill"}
        assert {c for c, e in fills.items() if e["price_source"] == "fallback"} == set(picks[:2])
        assert all(e["price_source"] == "finmind+adjust" for c, e in fills.items() if c not in picks[:2])
        assert any(e.get("reason") == "price_fallback_holdings" for e in ev)
        s2 = Synth()
        k2 = _mk(td, "b")
        pv2.run(s2, now_at(2026, 11, 16), **k2)
        pk = [p["code"] for p in [e for e in _evs(k2["log_path"]) if e["type"] == "signal"][0]["picks"]]
        d = pd.Timestamp("2026-11-17")
        o = lambda c: float(s2.bars[c].at[d, "Open"])  # noqa: E731
        s2.open_override = {(pk[0], "2026-11-17"): o(pk[0]) * 1.01, (pk[1], "2026-11-17"): o(pk[1]) * 1.003, (pk[2], "2026-11-17"): None}
        pv2.run(s2, now_at(2026, 11, 17), **k2)
        w = [e for e in _evs(k2["log_path"]) if e["type"] == "warning"]
        xs = [e for e in w if e["reason"].startswith("open_xcheck|")]
        assert [e["reason"] for e in xs] == [f"open_xcheck|{pk[0]}|2026-11-17"], xs
        miss = [e for e in w if e["reason"] == "open_xcheck_missing"]
        assert len(miss) == 1 and pk[2] in miss[0]["detail"]
        s3 = Synth()
        s3.fb_codes = {"1000", "1001", "1002"}
        k3 = _mk(td, "c")
        pv2.run(s3, now_at(2026, 11, 16), **k3)
        ev3 = _evs(k3["log_path"])
        sg3 = [e for e in ev3 if e["type"] == "signal"][0]
        assert sg3["price_fallback_codes"] == ["1000", "1001", "1002"] and "3 檔備援 yfinance" in sg3["price_source"]
        assert any(e.get("reason") == "price_fallback" for e in ev3)


def _big(**kw):
    return Synth(industries=(("A", 50), ("B", 45), ("C", 5)), **kw)


def _codes100():
    return [str(1000 + i) for i in range(100)]


def test_stmt_coverage_boundary_79_81():
    with tempfile.TemporaryDirectory() as td:
        cs = _codes100()
        base = _big()
        kb = _mk(td, "base")
        pv2.run(base, now_at(2026, 11, 16), **kb)
        sgb = [e for e in _evs(kb["log_path"]) if e["type"] == "signal"][0]
        assert sgb["stmt_mode"] == "full" and sgb["stmt_coverage"] == 1.0 and sgb["n_unsettled"] == 0
        s79 = _big(unsettled_codes=cs[-21:])
        k79 = _mk(td, "c79")
        pv2.run(s79, now_at(2026, 12, 2), **k79)
        ev = _evs(k79["log_path"])
        sk = [e for e in ev if e["type"] == "skipped_data_unready"]
        assert len(sk) == 1 and sk[0]["key"] == "skip|2026Q3" and sk[0]["stmt_coverage"] == 0.79, sk
        assert not [e for e in ev if e["type"] == "signal"]
        s81 = _big(unsettled_codes=cs[-19:])
        k81 = _mk(td, "c81")
        pv2.run(s81, now_at(2026, 12, 2), **k81)
        ev = _evs(k81["log_path"])
        assert not [e for e in ev if e["type"] == "skipped_data_unready"]
        sg = [e for e in ev if e["type"] == "signal"]
        assert len(sg) == 1 and sg[0]["stmt_mode"] == "partial" and sg[0]["stmt_coverage"] == 0.81 and sg[0]["n_unsettled"] == 19, sg
        assert not set(p["code"] for p in sg[0]["picks"]) & set(cs[-19:]) and sg[0]["R"] == "2026-11-16"
        s81b = _big(unsettled_codes=cs[-19:])
        k81b = _mk(td, "c81b")
        pv2.run(s81b, now_at(2026, 11, 19), **k81b)
        assert not [e for e in _evs(k81b["log_path"]) if e["type"] in ("signal", "skipped_data_unready")]
        s98 = _big(unsettled_codes=cs[-2:])
        k98 = _mk(td, "c98")
        pv2.run(s98, now_at(2026, 11, 19), **k98)
        sg98 = [e for e in _evs(k98["log_path"]) if e["type"] == "signal"]
        assert len(sg98) == 1 and sg98[0]["stmt_mode"] == "full" and sg98[0]["stmt_coverage"] == 0.98
        s97 = _big(unsettled_codes=cs[-3:])
        k97 = _mk(td, "c97")
        pv2.run(s97, now_at(2026, 11, 19), **k97)
        assert not [e for e in _evs(k97["log_path"]) if e["type"] in ("signal", "skipped_data_unready")]
        pv2.run(s97, now_at(2026, 12, 2), **k97)
        sg97 = [e for e in _evs(k97["log_path"]) if e["type"] == "signal"]
        assert len(sg97) == 1 and sg97[0]["stmt_mode"] == "partial" and sg97[0]["stmt_coverage"] == 0.97
        s79.unsettled_codes = set()
        pv2.run(s79, now_at(2026, 12, 3), **k79)
        assert not [e for e in _evs(k79["log_path"]) if e["type"] == "signal"]


def test_price_coverage_boundary_79_81_and_px_refresh():
    with tempfile.TemporaryDirectory() as td:
        cs = _codes100()
        s79 = _big(miss_prices=cs[-21:])
        k = _mk(td, "p79")
        pv2.run(s79, now_at(2026, 11, 19), **k)
        ev = _evs(k["log_path"])
        assert any(e.get("reason") == "price_coverage_low" for e in ev) and not [e for e in ev if e["type"] in ("signal", "skipped_data_unready")]
        pv2.run(s79, now_at(2026, 12, 2), **k)
        sk = [e for e in _evs(k["log_path"]) if e["type"] == "skipped_data_unready"]
        assert len(sk) == 1 and sk[0]["price_coverage"] == 0.79 and sk[0]["stmt_coverage"] == 1.0, sk
        s81 = _big(miss_prices=cs[-19:])
        k81 = _mk(td, "p81")
        pv2.run(s81, now_at(2026, 11, 16), **k81)
        sg = [e for e in _evs(k81["log_path"]) if e["type"] == "signal"]
        assert len(sg) == 1 and sg[0]["price_coverage"] == 0.81
        sp = _big()
        sp.px_unready = set(cs[:30])
        kp = _mk(td, "px")
        pv2.run(sp, now_at(2026, 11, 19), **kp)
        assert sp.px_calls == 30 and not sp.px_unready
        sgp = [e for e in _evs(kp["log_path"]) if e["type"] == "signal"]
        assert len(sgp) == 1 and sgp[0]["px_ready"] == 1.0
        sf = _big()
        sf.px_unready = set(cs[:30])
        sf.fail_px = True
        kf = _mk(td, "pxf")
        pv2.run(sf, now_at(2026, 11, 19), **kf)
        assert sf.px_calls == 5 and not [e for e in _evs(kf["log_path"]) if e["type"] == "signal"]
        pv2.run(sf, now_at(2026, 12, 2), **kf)
        sgf = [e for e in _evs(kf["log_path"]) if e["type"] == "signal"]
        assert len(sgf) == 1 and sgf[0]["px_ready"] == 0.7 and sgf[0]["stmt_mode"] == "full"
        sb = _big()
        sb.px_unready = set(cs[:30])
        sb.fail_px = True
        sb.px_msg = "FinMind blocked (synthetic) 封鎖"
        pv2.run(sb, now_at(2026, 11, 19), **_mk(td, "pxb"))
        assert sb.px_calls == 1
        se = _big()
        se.events_ok = False
        se.fail_events = True
        ke = _mk(td, "ev")
        pv2.run(se, now_at(2026, 11, 19), **ke)
        assert not [e for e in _evs(ke["log_path"]) if e["type"] == "signal"]
        pv2.run(se, now_at(2026, 12, 2), **ke)
        eve = _evs(ke["log_path"])
        assert len([e for e in eve if e["type"] == "signal"]) == 1 and any(e.get("reason") == "events_stale" for e in eve)


def test_no_holdings_before_first_rebalance():
    with tempfile.TemporaryDirectory() as td:
        k = _mk(td, "pre")
        s = Synth()
        for day in [(2026, 9, 1), (2026, 10, 1), (2026, 10, 14), (2026, 10, 20), (2026, 11, 2), (2026, 11, 13), (2026, 11, 14), (2026, 11, 15)]:
            pv2.run(s, now_at(*day), **k)
        assert not [e for e in _evs(k["log_path"]) if e["type"] in ("signal", "fill", "nav")] if k["log_path"].exists() else True


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    bad = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception:  # noqa: BLE001
            bad += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} 通過")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
