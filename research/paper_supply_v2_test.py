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
    def __init__(self, seed=7, industries=(("A", 28), ("B", 27), ("C", 5)), settled=True, miss_prices=()):
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
        if self.drop_target or not self.settled:
            f = f[f["date"] != "2026-09-30"]
            b = b[b["date"] != "2026-09-30"]
            c = c[c["date"] != "2026-09-30"]
        return {"fs": (f, self.mtime), "bs": (b, self.mtime), "cf": (c, self.mtime)}

    def refresh_stmt(self, code, which):
        self.refresh_calls += 1
        if self.fail_refresh:
            raise RuntimeError(self.fail_msg)

    def prices(self, rows, start, end):
        if self.fail_prices:
            raise RuntimeError("synthetic price failure")
        return {c: self.bars[c].loc[start:end] for c, _ in rows if c not in self.miss}


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
