# -*- coding: utf-8 -*-
"""自測：模擬 M～R 前向追蹤程式（先.一三六-B7；涵蓋 M／N／P／Q／R，O 模型訓練後補進來）。

全部在暫存目錄進行，不碰真實帳本／摘要；只檢查結構，**不印任何淨值或報酬**
（測試用到的價格日期落在 holdout 期間，只當程式輸入、不評估任何策略）。
1. 正式設定（起跑 2027-01-04）下 step() 都是 NOT_STARTED、不寫帳本。
2. 假裝已起跑（起跑日改成價格日曆倒數第 15 個交易日）＋合成事件：會寫帳本、再跑一次不新增列（冪等）；
   只在 t1＝t0 下一個交易日進場；同代號去重；漲停鎖死放棄；除權息排除。
3. P 的標題分類規則（收／排除字）。
4. Q 的資料日對照（先.一三六-B7a）：累積檔有 data_dates 時 t0＝官方資料日（不是執行日鍵）、同一資料日只算一次、
   上櫃代號取 tpex 資料日；沒有 data_dates 時走後備（鍵對到 ≤ 鍵的最後交易日）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_forward_common as C  # noqa: E402
import paper_forward_events as E  # noqa: E402
import paper_16_order_win_tracker as P  # noqa: E402
import paper_17_margin_liquidation_tracker as Q  # noqa: E402
import paper_18_sbl_covering_tracker as R  # noqa: E402
import paper_14_grid_range_tracker as N  # noqa: E402
import paper_13_ml_low_beta_tracker as MM  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def lines(p: Path) -> int:
    return len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]) if p.exists() else 0


px = C.load_px()
cal = px.calendar
active = set((C.load_json(ROOT / "data" / "listed_universe.json", {}) or {}).get("active") or [])
td = Path(tempfile.mkdtemp(prefix="paper_13_18_selftest_"))


def redirect(sp: C.Spec, name: str) -> C.Spec:
    sp.log_path, sp.out_path = td / f"{name}_log.jsonl", td / f"{name}.json"
    return sp


# 1. 正式起跑日前 NOT_STARTED、不寫帳本
check(cal[-1] < "2027-01-04", f"價格最新日 {cal[-1]} 早於 2027-01-04（本測試前提）")
real = [("P", redirect(P.spec(P.raw_events(P.load_all(), px)), "p_real")),
        ("Q", redirect(Q.spec(Q.raw_events(C.load_json(Q.MARGIN, {}), px, Q.ex_dates(C.load_json(Q.EXDIV, {}))), set()), "q_real")),
        ("R", redirect(R.spec(R.raw_events(C.load_json(R.SBL, {}), px, C.load_json(R.EXDIV, {}))), "r_real"))]
for name, sp in real:
    r = C.step(sp, {"px": px}, px=px, active=active)
    check(r["state"] == "NOT_STARTED" and not sp.log_path.exists(), f"{name}: 起跑前 NOT_STARTED 且不寫帳本")
    check(C.load_json(sp.out_path, {}).get("started") is False and "nav" not in C.load_json(sp.out_path, {}),
          f"{name}: 起跑前摘要沒有淨值欄")
    check(sp.start_not_before == "2027-01-04", f"{name}: 起跑日 2027-01-04")

# 2. 合成事件：挑最後 15 日內每天都有收盤、流動性夠的在市普通股
start = cal[-15]
liquid = sorted(c for c in active if C.is_common(c) and all(px.close_on(c, d) for d in cal[-40:])
                and (px.avg_turnover(c, cal[-16], inclusive=False) or 0) >= 1e8)[:3]
check(len(liquid) == 3, "找到 3 檔合成事件用股票")
a, b, c = liquid
t0 = cal[-16]  # → t1＝start
syn = [{"code": a, "t0": t0}, {"code": b, "t0": t0}, {"code": a, "t0": cal[-14]}]  # 第三筆 20 日內重複
ded = E.dedupe(syn, px, 20)
check(len(ded) == 2 and all(e["t0"] == t0 for e in ded), "去重：同代號 20 個交易日內只算第一個")

for name, mod, sp in [("Q", Q, Q.spec(ded, set())), ("R", R, R.spec([dict(e, bal_5ago=2e6, bal_t0=1e6) for e in ded])),
                      ("P", P, P.spec([dict(e, title="得標") for e in ded]))]:
    sp = redirect(sp, f"{name.lower()}_syn")
    sp.start_not_before = start
    r1 = C.step(sp, {"px": px}, px=px, active=active)
    n1 = lines(sp.log_path)
    r2 = C.step(sp, {"px": px}, px=px, active=active)
    check(r1["state"] == "PROCESSED" and n1 == len([d for d in cal if d >= start]), f"{name}: 起跑後每個交易日一列")
    check(r2["state"] == "HOLD" and lines(sp.log_path) == n1, f"{name}: 再跑一次不新增列（冪等）")
    log = C.read_log(sp)
    first = log[0]
    check(first["date"] == start and sorted(first["entered"]) == sorted({a, b}), f"{name}: 只在 t1（t0 下一個交易日）進場")
    check(all(not e.get("entered") for e in log[1:]), f"{name}: 之後沒有事件就不進場")
    for e in log:
        for k in ("date", "event", "nav", "cash", "positions"):
            assert k in e
    if name == "Q":
        closed = [t for e in log for t in e.get("closed_trades") or []]
        check(len(closed) == 2 and all(t["exit_date"] == cal[cal.index(start) + Q.H] for t in closed), "Q: 持有 5 個交易日出場")

# 漲停鎖死放棄（合成價格：t1 一字漲停）
fake = {"9999": [{"date": cal[-3], "open": 10, "high": 10, "low": 10, "close": 10},
                 {"date": cal[-2], "open": 11, "high": 11, "low": 11, "close": 11}]}
fpx = C.Px(fake)
check(E.locked_up(fpx, "9999", cal[-2]) and not E.locked_up(fpx, "9999", cal[-3]), "一字漲停判鎖死、前一天不判")

# 除權息排除（R：±10 個交易日）
lo, hi = E.trading_window(px, cal[-30], 10)
check(lo == cal[-40] and hi == cal[-20], "除權息窗口＝前後 10 個交易日")
lo2, hi2 = E.trading_window(px, cal[-3], 10)
check(hi2 > cal[-1], "除權息窗口右側超出日曆時用週一～五往後延")

# 4. 模擬 N（網格，日頻增量）
for name, shadow in [("N", False), ("N影子", True)]:
    sp = redirect(N.make_spec(shadow), f"n_real_{int(shadow)}")
    r = N.run_one(sp, px, active, not shadow)
    check(r["state"] == "NOT_STARTED" and not sp.log_path.exists(), f"{name}: 起跑前 NOT_STARTED 且不寫帳本")
d0, d1, d2, d3 = "2030-01-02", "2030-01-03", "2030-01-04", "2030-01-07"
def bar(d, o, c):
    return {"date": d, "open": o, "high": max(o, c), "low": min(o, c), "close": c, "adj_close": c, "turnover": 1e9}
spx = C.Px({"1234": [bar(d0, 101, 101), bar(d1, 100.5, 99), bar(d2, 99, 102.5), bar(d3, 103, 103)]})
st = N.empty_state()
st.update(month="2030-01", universe=["1234"], last_c={"1234": 101.0},
          grids={"1234": {"lines": [100 + 2 * k for k in range(-5, 6)], "prev_sig": 101.0, "built": d0, "g": 2.0}})
import json as _j  # noqa: E402
recs = [_j.loads(_j.dumps(N.process_day(spx, d, st, {"1234"}, True))) for d in (d1, d2, d3)]  # 正式流程每天當下即序列化寫入帳本
check(recs[0]["grid_state"]["pend_buy"].get("1234") == [0] and not recs[0]["positions"], "N: 收盤跌破格下緣 → 掛隔日買單、當天不成交")
check("1234" in recs[1]["positions"] and recs[1]["grid_state"]["pend_sell"].get("1234") == [0], "N: 隔日開盤買進；收盤站上上緣 → 掛賣單")
ct = recs[2]["closed_trades"]
check(len(ct) == 1 and ct[0]["entry_date"] == d2 and ct[0]["exit_date"] == d3 and not recs[2]["positions"], "N: 再隔日開盤賣出、記一筆已平倉")
st2 = N.empty_state()
st2.update(month="2030-01", universe=["1234"], last_c={"1234": 101.0},
           grids={"1234": {"lines": [100 + 2 * k for k in range(-5, 6)], "prev_sig": 101.0, "built": d0, "g": 2.0}})
spx2 = C.Px({"1234": [bar(d0, 101, 101), bar(d1, 100, 89)]})
r2 = N.process_day(spx2, d1, st2, {"1234"}, True)
check("1234" not in r2["grid_state"]["grids"] and r2["grid_state"]["cool_left"].get("1234") == N.N and not r2["grid_state"]["pend_buy"],
      "N: 跌破 L-5 → 停損優先、不買、冷卻 20 日")
for name, shadow in [("N", False), ("N影子", True)]:
    sp = redirect(N.make_spec(shadow), f"n_syn_{int(shadow)}")
    sp.start_not_before = start
    r1 = N.run_one(sp, px, active, not shadow)
    n1 = lines(sp.log_path)
    r2 = N.run_one(sp, px, active, not shadow)
    check(r1["state"] == "PROCESSED" and n1 == len([d for d in cal if d >= start]) and lines(sp.log_path) == n1,
          f"{name}: 起跑後每個交易日一列、再跑一次不新增（冪等，狀態從帳本接續）")
    first = C.read_log(sp)[0]
    el, bt = set(first.get("eligible_nofilter") or []), set(first.get("built") or [])
    check(bt <= el and (bt == el if shadow else True) and first.get("universe_n") == N.TOPN, f"{name}: 月初建格 ⊆ 不看濾網可建格；影子＝全建；宇宙 50 檔")

# 5. 模擬 M（低 beta 選股規則，合成排名）
rk = [{"code": f"{1000 + i}", "rank": i, "score": -i} for i in range(1, 101)]
betas = {r["code"]: (r["rank"] % 7) / 10 if r["rank"] != 3 else None for r in rk}
held = {"1061", "1070", "1095"}  # 61 名 beta 0.5、70 名 beta 0.0、95 名
out, stt = MM.select(rk, betas, held)
tg = [r for r in out if r["role"] == "target"]
check(len(tg) == 30 and all(r["model_rank"] <= 60 for r in tg) and stt["pool_beta_nan"] == 1, "M: 目標集合＝前 60 名、beta 非 NaN 中最低 30 檔")
check([r["beta_60d"] for r in tg] == sorted(r["beta_60d"] for r in tg), "M: 目標集合依 beta 由低到高")
keep = {r["code"] for r in out if r["role"] == "keep"}
check("1070" in keep and "1095" not in keep and ("1061" in keep) == (betas["1061"] <= stt["target_max_beta"]), "M: 續抱＝前 90 名且 beta ≤ 目標集合最大 beta")
sp = redirect(MM.spec(), "m_real")
r = C.step(sp, {"px": px}, px=px, active=active)
check(r["state"] == "NOT_STARTED" and not sp.log_path.exists(), "M: 起跑前 NOT_STARTED 且不寫帳本")

# 3. P 標題分類
check(P.is_order_win({"source": "TWSE 重大訊息", "title": "本公司接獲台電公司採購案"}), "P: 接獲採購案 → 收")
check(P.is_order_win({"source": "TPEx 重大訊息", "title": "公告本公司得標新北市工程"}), "P: 得標 → 收")
check(not P.is_order_win({"source": "TWSE 重大訊息", "title": "更正本公司得標金額"}), "P: 含『更正』→ 排除")
check(not P.is_order_win({"source": "新聞", "title": "接獲大單"}), "P: 非重大訊息來源 → 不收")

# 4. Q 資料日對照（合成融資序列＋真實價格：借一個真實「當日跌 ≥5%」的交易日當資料日，不評估任何報酬）
exq = Q.ex_dates(C.load_json(Q.EXDIV, {}))
pick = None
for ci in range(len(cal) - 3, 25, -1):
    d0 = cal[ci]
    for code in list(px.rows)[:400]:
        if C.is_common(code) and d0 not in exq.get(code, set()):
            rr = E.raw_ret(px, code, d0)
            if rr is not None and rr <= -Q.R_DROP:
                pick = (code, d0, ci)
                break
    if pick:
        break
check(pick is not None, "Q: 找得到一個真實大跌日當合成資料日（測試前提）")
if pick:
    code, d0, ci = pick
    nxt8, nxt2_8 = cal[ci + 1].replace("-", ""), cal[ci + 2].replace("-", "")
    v = [800.0, 1000.0, 0.0]  # 融資 −20%
    base = {"series": {code: {nxt8: v, nxt2_8: v}}}
    mq = {**base, "data_dates": {nxt8: {"twse": d0.replace("-", ""), "tpex": None},
                                 nxt2_8: {"twse": d0.replace("-", ""), "tpex": None}}}
    ev = Q.raw_events(mq, px, exq)
    check(len(ev) == 1 and ev[0]["t0"] == d0, f"Q: 有 data_dates → t0＝資料日 {d0}（不是執行日鍵 {cal[ci + 1]}），同資料日兩鍵只算一次")
    check(Q.resolve_t0(px, base, nxt8, code) == cal[ci + 1], "Q: 沒有 data_dates → 後備＝鍵對到 ≤ 鍵的最後交易日")
    mt = {**base, "tpex_codes": [code], "data_dates": {nxt8: {"twse": nxt2_8, "tpex": d0.replace("-", "")}}}
    check(Q.data_day(mt, nxt8, code) == d0 and Q.data_day({**mt, "tpex_codes": []}, nxt8, code) == cal[ci + 2],
          "Q: 上櫃代號取 tpex 資料日、上市取 twse 資料日")
    check(Q.resolve_t0(px, {**base, "data_dates": {nxt8: {"twse": "20991231"}}}, nxt8, code) is None,
          "Q: 資料日不在價格日曆 → 不出事件（不猜）")
    # 先.一三五-1bl：前一鍵有資料日、後一鍵上市資料日是 null（晚班推不出）但數值相同 → 後一鍵當複本去掉，不多出一筆晚一天的事件
    mm = {**base, "data_dates": {nxt8: {"twse": d0.replace("-", ""), "tpex": None}, nxt2_8: {"twse": None, "tpex": None}}}
    ev = Q.raw_events(mm, px, exq)
    check(len(ev) == 1 and ev[0]["t0"] == d0, "Q: 前鍵有資料日、後鍵資料日 null 且數值相同 → 只算一次、t0＝前鍵資料日")

print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL'}（暫存目錄 {td}）")
sys.exit(1 if fails else 0)
