# -*- coding: utf-8 -*-
"""自測：模擬 J／K／L（paper_10～12）事件抽取邏輯（先.一三五-1x）。

全部用暫存目錄＋虛構代號（88xx）＋合成價格／合成事件，**不讀真實價格、不印任何淨值或報酬**，
不碰真實帳本／摘要／累積檔。只測邏輯，不改追蹤程式的判定規則。
既有共用自測（selftest_paper_forward_common.py）已覆蓋：J 延長合併、主／影帳本互斥、仍在處置不進場、H 天出場、冪等；
K 4～6 週窗基本例與 PIT；L 起跑前提（連續 10 天、缺一天重算、順延跨年）。本檔補其餘未覆蓋的事件抽取函式：
- J：accumulate 去重／迄日只延長不縮短／壞列略過；merged_events 相接（下一交易日）合併、隔一交易日不合併、
  日曆尚未到時日曆天 ≤4 後備；make_signal 條件切點 0（=0 歸影子帳本）、流動性 1,000 萬門檻、資料不滿 20 天、
  缺收盤 skip、不在宇宙 skip、同日依處置期間報酬由低到高再依代號、limit_up_at_entry 官方漲停價邊界（2026-10-29 先.一四一-1 PREREG 修訂 R1 起，原 1.095 已拿掉）。
- K：delta_for 窗口邊界（28／42 天含、27／43 天不含）、取窗內最近一週、None 比例略過、資料日＝再平衡日不可用；
  signal Δ 由大到小再依代號、Δ≤0 排除、不在宇宙忽略、全市場算不出 → None＋skip_reason、0050 成分欄 null／布林。
- L：snapshot_ok 缺任一來源即 False；calls_in 只收上市認購＋上櫃 type=認購；update_appearances 首批 null、
  之後記出現日、不完整快照不處理、重跑冪等；signal 缺快照 >5 天不調倉（=5 天照跑）、窗口外不計、
  排序（檔數大→成交值小→代號）、不在宇宙排除。
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_forward_common as C  # noqa: E402
import paper_10_disposition_tracker as J  # noqa: E402
import paper_11_tdcc_bigholder_tracker as K  # noqa: E402
import paper_12_warrant_wave_tracker as L  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


td = Path(tempfile.mkdtemp(prefix="paper_10_12_selftest_"))

# 合成交易日曆：2031-01-06 起 60 個平日（虛構未來日期，不對應任何真實價格）
cal, d0 = [], date(2031, 1, 6)
while len(cal) < 60:
    if d0.weekday() < 5:
        cal.append(d0.isoformat())
    d0 += timedelta(days=1)


def series(path_fn, turnover=5e7, raw_fn=None):
    """path_fn(i)→還原收盤；raw_fn(i)→原始收盤（預設同還原）。"""
    return [{"date": d, "close": (raw_fn or path_fn)(i), "adj_close": path_fn(i), "turnover": turnover}
            for i, d in enumerate(cal)]


# ---------------------------------------------------------------- J
# 1. accumulate
flags_p, ev_p = td / "flags.json", td / "events.json"
flags_p.write_text(json.dumps({"disposal": {
    "8801": {"start": "2031-02-03", "end": "2031-02-14", "announced": "2031-01-31", "source": "syn"},
    "8802": {"start": "2031-02-03"},  # 缺迄日 → 略過
    "8803": None}}), encoding="utf-8")
doc = J.accumulate(flags_p, ev_p, today="2031-02-03")
check([s["code"] for s in doc["segments"]] == ["8801"], "J accumulate：缺起迄／空值的列略過")
flags_p.write_text(json.dumps({"disposal": {"8801": {"start": "2031-02-03", "end": "2031-02-21"}}}), encoding="utf-8")
doc = J.accumulate(flags_p, ev_p, today="2031-02-05")
s = doc["segments"]
check(len(s) == 1 and s[0]["end"] == "2031-02-21" and s[0]["first_seen"] == "2031-02-03" and s[0]["last_seen"] == "2031-02-05",
      "J accumulate：同（代號、起日）去重、延長公告更新迄日、保留 first_seen")
flags_p.write_text(json.dumps({"disposal": {"8801": {"start": "2031-02-03", "end": "2031-02-10"}}}), encoding="utf-8")
doc = J.accumulate(flags_p, ev_p, today="2031-02-06")
check(doc["segments"][0]["end"] == "2031-02-21", "J accumulate：迄日只延長不縮短")
flags_p.write_text(json.dumps({"disposal": {}}), encoding="utf-8")
doc = J.accumulate(flags_p, ev_p, today="2031-02-07")
check(len(doc["segments"]) == 1, "J accumulate：當下清單沒有了也保留已累積事件")

# 2. merged_events
px = C.Px({"8801": series(lambda i: 100.0)})
i5 = 20
a_end = cal[i5]
segs = [{"code": "8801", "start": cal[i5 - 4], "end": a_end},
        {"code": "8801", "start": cal[i5 + 1], "end": cal[i5 + 5]}]  # 起日＝前段迄日的下一交易日 → 合併
ev = J.merged_events(segs, px)
check(len(ev) == 1 and ev[0]["start"] == cal[i5 - 4] and ev[0]["end"] == cal[i5 + 5], "J 合併：起日＝前段迄日下一交易日 → 同一事件")
segs = [{"code": "8801", "start": cal[i5 - 4], "end": a_end},
        {"code": "8801", "start": cal[i5 + 2], "end": cal[i5 + 5]}]  # 隔一個交易日 → 不合併
check(len(J.merged_events(segs, px)) == 2, "J 合併：中間隔一個交易日 → 兩個事件")
segs = [{"code": "8801", "start": cal[i5 - 4], "end": cal[i5 + 3]},
        {"code": "8801", "start": cal[i5 + 1], "end": cal[i5 + 2]}]  # 重疊且後段較短 → 迄日取較晚者
ev = J.merged_events(segs, px)
check(len(ev) == 1 and ev[0]["end"] == cal[i5 + 3], "J 合併：重疊時迄日取最晚")
# 日曆還沒到（迄日＝日曆最後一天之後）：退回日曆天 ≤4
last = date.fromisoformat(cal[-1])
seg_a = {"code": "8801", "start": cal[-3], "end": (last + timedelta(days=2)).isoformat()}
ok4 = {"code": "8801", "start": (last + timedelta(days=6)).isoformat(), "end": (last + timedelta(days=9)).isoformat()}
no5 = {"code": "8801", "start": (last + timedelta(days=7)).isoformat(), "end": (last + timedelta(days=9)).isoformat()}
check(len(J.merged_events([seg_a, ok4], px)) == 1, "J 合併後備：價格日曆未到時日曆天差 4 天 → 合併")
check(len(J.merged_events([seg_a, no5], px)) == 2, "J 合併後備：日曆天差 5 天 → 不合併")
check(len(J.merged_events([{"code": "8801", "start": cal[5], "end": cal[8]},
                           {"code": "8802", "start": cal[9], "end": cal[12]}], px)) == 2, "J 合併：不同代號不合併")

# 3. make_signal
ds, r_i = 25, 34          # 處置起日 cal[25]、解除日 r＝cal[34]、判斷日 day＝cal[35]
day, r = cal[r_i + 1], cal[r_i]


def path(pre, at_r, at_day=None):
    def f(i):
        if i < ds:
            return pre
        if i < r_i:
            return pre
        if i == r_i:
            return at_r
        return at_day if at_day is not None else at_r
    return f


prices = {
    "8811": series(path(100, 90)),                       # −10%
    "8812": series(path(100, 80)),                       # −20%（應排第一）
    "8813": series(path(100, 90)),                       # −10%，同分依代號排在 8811 後
    "8814": series(path(100, 110)),                      # +10% → 影子
    "8815": series(path(100, 100)),                      # 0 → 影子（切點 0：<0 才算主帳本）
    "8816": series(path(100, 90), turnover=9_999_999),   # 流動性不足
    "8817": series(path(100, 90), turnover=10_000_000),  # 剛好門檻 → 收
    "8818": series(path(100, 90)),                       # 不在宇宙
    "8820": series(path(100, 90, 99.0)),                 # 進場日 99.0 ≥ 官方漲停價（前收 90 → 99.00）→ 漲停 true（PREREG 修訂 R1）
    "8821": series(path(100, 90, 98.95)),                # 98.95 < 99.00（差一檔）→ false
}
prices["8819"] = [r_ for r_ in series(path(100, 90)) if r_["date"] != cal[ds - 1]]  # 處置起日前一日缺收盤
prices["8822"] = series(path(100, 90))[ds - 15:]        # 處置前資料不滿 20 天
px = C.Px(prices)
codes = sorted(prices)
segs = [{"code": c, "start": cal[ds], "end": r} for c in codes]
uni = {c: 5e7 for c in codes if c != "8818"}
ctx = {"px": px}
main = J.make_signal(segs, control=False)(ctx, day, uni)
skips = {s["code"]: s["reason"] for s in ctx["skips"][day]}
ctx2 = {"px": px}
ctrl = J.make_signal(segs, control=True)(ctx2, day, uni)
mc = [c["code"] for c in main]
check(mc[:3] == ["8812", "8811", "8813"], "J 排序：處置期間報酬由低到高、同分依代號")
check({c["code"] for c in ctrl} == {"8814", "8815"}, "J 切點 0：期間報酬 ≥0（含 =0）只進影子帳本")
check(not ({c["code"] for c in main} & {c["code"] for c in ctrl}), "J 主／影候選互斥")
check("8816" in skips and "1,000 萬" in skips["8816"] and "8817" in mc, "J 流動性：9,999,999 排除、10,000,000 收")
check("8822" in skips and "8822" not in mc, "J 處置前資料不滿 20 天 → 無訊號（skip）")
check("8819" in skips and "缺收盤" in skips["8819"], "J 處置起日前一日缺收盤 → skip 照實記")
check("8818" in skips and "不在宇宙" in skips["8818"], "J 不在宇宙 → skip 照實記")
lu = {c["code"]: c["limit_up_at_entry"] for c in main}
check(lu.get("8820") is True and lu.get("8821") is False and lu.get("8811") is False, "J limit_up_at_entry：≥官方漲停價才標 true（R1）")
check(all(c["release_date"] == r and c["disposal_start"] == cal[ds] for c in main), "J 候選帶處置起日與解除日")
check(J.make_signal(segs, control=False)({"px": px}, cal[r_i + 2], uni) == [], "J 只在 r 的下一交易日判斷（隔天不再出現）")
segs_ext = segs + [{"code": "8811", "start": day, "end": cal[r_i + 4]}]
check("8811" not in [c["code"] for c in J.make_signal(segs_ext, control=False)({"px": px}, day, uni)],
      "J 判斷日仍被新一段處置涵蓋 → 不算解除")

# ---------------------------------------------------------------- K
H = lambda d, v: {"date": d, "big_holder_ratio": v}  # noqa: E731
check(K.delta_for([H("20310101", 50), H("20310129", 52)], "2031-02-02") is not None, "K 窗口：相隔 28 天（含）有訊號")
check(K.delta_for([H("20310101", 50), H("20310128", 52)], "2031-02-02") is None, "K 窗口：相隔 27 天無訊號")
check(K.delta_for([H("20310101", 50), H("20310212", 52)], "2031-02-16") is not None, "K 窗口：相隔 42 天（含）有訊號")
check(K.delta_for([H("20310101", 50), H("20310213", 52)], "2031-02-16") is None, "K 窗口：相隔 43 天無訊號")
d = K.delta_for([H("20310101", 40), H("20310108", 45), H("20310205", 50)], "2031-02-09")
check(d is not None and d[2] == "20310108" and abs(d[0] - 5.0) < 1e-9, "K 窗內有多週時取最接近 4 週的那一週")
d = K.delta_for([H("20310101", 40), {"date": "20310129", "big_holder_ratio": None}, H("20310122", 41)], "2031-02-02")
check(d is None, "K 最新週比例為 None → 略過該週，剩下的相隔不足 → 無訊號")
check(K.delta_for([H("2031-01-01", 50), H("2031-01-29", 53)], "2031-02-02")[0] == 3.0, "K 日期 ISO 格式也可解析")
check(K.delta_for([H("20310101", 50), H("20310129", 53)], "2031-01-29") is None, "K 資料日＝再平衡日不可用（PIT 嚴格早於）")

holders = {"stocks": {
    "8831": {"history": [H("20310101", 50), H("20310129", 53)]},   # +3
    "8832": {"history": [H("20310101", 50), H("20310129", 55)]},   # +5
    "8833": {"history": [H("20310101", 50), H("20310129", 53)]},   # +3 同分，代號較大
    "8834": {"history": [H("20310101", 50), H("20310129", 50)]},   # 0 → 排除
    "8835": {"history": [H("20310101", 50), H("20310129", 49)]},   # −1 → 排除
    "8836": {"history": [H("20310101", 50), H("20310129", 60)]},   # 不在宇宙
}}
_orig_load = K.C.load_json


def _fake_load(holders_doc, tw50_doc):
    def f(p, default):
        name = Path(p).name
        if name == "holders.json":
            return holders_doc
        if name == "tw50_constituents.json":
            return tw50_doc if tw50_doc is not None else default
        return _orig_load(p, default)
    return f


uni_k = {c: 4e7 for c in ["8831", "8832", "8833", "8834", "8835", "8837"]}
try:
    K.C.load_json = _fake_load(holders, None)
    ctx = {}
    rows = K.signal(ctx, "2031-02-02", uni_k)
    check([r_["code"] for r_ in rows] == ["8832", "8831", "8833"], "K 排序：Δ 由大到小、同分依代號；Δ≤0 排除；不在宇宙忽略")
    check(all(r_["etf_0050_006208_member"] is None for r_ in rows), "K 沒有成分股檔 → 成分欄記 null")
    check("skip_reason" not in ctx, "K 有算得出的股票時不記 skip_reason")
    K.C.load_json = _fake_load(holders, {"codes": ["8832"]})
    rows = K.signal({}, "2031-02-02", uni_k)
    m = {r_["code"]: r_["etf_0050_006208_member"] for r_ in rows}
    check(m == {"8832": True, "8831": False, "8833": False}, "K 有成分股檔 → 成分欄記布林（只揭露）")
    K.C.load_json = _fake_load({"stocks": {"8831": {"history": [H("20310120", 50), H("20310129", 53)]}}}, None)
    ctx = {}
    check(K.signal(ctx, "2031-02-02", uni_k) is None and "TDCC 缺週" in ctx.get("skip_reason", ""),
          "K 全市場算不出 → 回 None、記 skip_reason（本月不調倉）")
    K.C.load_json = _fake_load({"stocks": {"8834": holders["stocks"]["8834"]}}, None)
    ctx = {}
    rows = K.signal(ctx, "2031-02-02", uni_k)
    check(rows == [] and "skip_reason" not in ctx, "K 算得出但全部 Δ≤0 → 空清單（不是缺週）")
finally:
    K.C.load_json = _orig_load

# ---------------------------------------------------------------- L
snap = td / "snap"


def mk_snap(d, twse_calls=None, tpex_issue=None, skip_source=None):
    p = snap / d
    p.mkdir(parents=True, exist_ok=True)
    (p / "meta.json").write_text("{}", encoding="utf-8")
    for s_ in L.SOURCES:
        if s_ == skip_source:
            continue
        obj = []
        if s_ == "quotes_twse_call":
            obj = twse_calls or []
        elif s_ == "issue_tpex":
            obj = tpex_issue or {}
        with gzip.open(p / f"{s_}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(obj, f)


lc = cal[:30]
mk_snap(lc[0], [{"code": "W001", "underlying": "8841"}], {"T001": {"type": "認購", "underlying_code": "8842"}})
mk_snap(lc[1], [{"code": "W001", "underlying": "8841"}, {"code": "W002", "underlying": "8841"}, {"code": "", "underlying": "8841"}],
        {"T001": {"type": "認購", "underlying_code": "8842"}, "T002": {"type": "認售", "underlying_code": "8842"},
         "T003": {"type": "認購", "underlying_code": "8843"}})
mk_snap(lc[2], [{"code": "W003", "underlying": "8841"}], {}, skip_source="quotes_tpex")  # 不完整
check(L.snapshot_ok(lc[1], snap) and not L.snapshot_ok(lc[2], snap) and not L.snapshot_ok(lc[5], snap),
      "L snapshot_ok：缺任一來源或整天缺 → False")
calls = L.calls_in(lc[1], snap)
check(calls == {"W001": "8841", "W002": "8841", "T001": "8842", "T003": "8843"}, "L calls_in：只收上市認購與上櫃 type=認購、空代號略過")
ap_p = td / "appear.json"
ap = L.update_appearances(snap, ap_p)
w = ap["warrants"]
check(w["W001"]["first_seen"] is None and w["T001"]["first_seen"] is None, "L 出現日：首批快照已存在的權證記 null")
check(w["W002"]["first_seen"] == lc[1] and w["T003"]["first_seen"] == lc[1], "L 出現日：之後第一次出現的那天")
check("W003" not in w and lc[2] not in ap["dates_processed"], "L 不完整快照不處理（不記出現日）")
mk_snap(lc[2], [{"code": "W003", "underlying": "8841"}], {})  # 補齊後下次處理
ap = L.update_appearances(snap, ap_p)
check(ap["warrants"]["W003"]["first_seen"] == lc[2] and ap["warrants"]["W002"]["first_seen"] == lc[1],
      "L 補齊快照後才記出現日、既有出現日不被覆寫（冪等）")


class _FakePx:
    def __init__(self, c):
        self.calendar = c


day_l = lc[25]
win = lc[6:26]  # W=20 → lo = lc[6]
snap2 = td / "snap2"
for d_ in win:
    (snap2 / d_).mkdir(parents=True, exist_ok=True)
    (snap2 / d_ / "meta.json").write_text("{}", encoding="utf-8")
    for s_ in L.SOURCES:
        (snap2 / d_ / f"{s_}.json.gz").write_bytes(b"")
appear = {"warrants": {
    "a1": {"first_seen": lc[6], "underlying": "8851"}, "a2": {"first_seen": lc[25], "underlying": "8851"},
    "b1": {"first_seen": lc[10], "underlying": "8852"}, "b2": {"first_seen": lc[11], "underlying": "8852"},
    "c1": {"first_seen": lc[12], "underlying": "8853"},
    "d1": {"first_seen": lc[5], "underlying": "8854"},     # 窗口前一天 → 不計
    "e1": {"first_seen": None, "underlying": "8855"},      # 首批 → 不計
    "f1": {"first_seen": lc[26], "underlying": "8856"},    # 判斷日之後 → 不計
    "g1": {"first_seen": lc[15], "underlying": "8857"},    # 不在宇宙
}}
uni_l = {"8851": 9e7, "8852": 4e7, "8853": 5e7, "8854": 5e7, "8855": 5e7, "8856": 5e7}
ctx = {"px": _FakePx(lc), "appear": appear, "snap": snap2}
rows = L.signal(ctx, day_l, uni_l)
check([(r_["code"], r_["new_calls"]) for r_ in rows] == [("8852", 2), ("8851", 2), ("8853", 1)],
      "L 訊號：窗口含首尾、檔數大→成交值小→代號；窗口外／首批／判斷日後／不在宇宙不計")
for d_ in win[:5]:
    (snap2 / d_ / "meta.json").unlink()
ctx = {"px": _FakePx(lc), "appear": appear, "snap": snap2}
check(L.signal(ctx, day_l, uni_l) is not None and "skip_reason" not in ctx, "L 窗內缺快照 5 天（=門檻）照常調倉")
(snap2 / win[5] / "meta.json").unlink()
ctx = {"px": _FakePx(lc), "appear": appear, "snap": snap2}
check(L.signal(ctx, day_l, uni_l) is None and "缺快照 6 天" in ctx.get("skip_reason", ""), "L 窗內缺快照 6 天（>5）→ 本月不調倉")

print(f"\n暫存目錄：{td}")
print(f"結果：{'全部通過' if not fails else f'{len(fails)} 項失敗'}")
raise SystemExit(1 if fails else 0)
