# -*- coding: utf-8 -*-
"""自測：個股前向追蹤共用框架＋模擬 J／K／L 訊號（先.一三二-5）。

全部在暫存目錄進行，不碰真實帳本／摘要。只檢查結構（冪等、NOT_STARTED、帳本欄位、記憶體），
**不印任何淨值或報酬**（測試用到的價格日期落在 holdout 期間，只當程式輸入、不評估任何策略）。
1. 正式設定（起跑 2026-12-01）下三個模擬 step() 都是 NOT_STARTED、不寫帳本。
2. 假裝已起跑（起跑日改成價格日曆倒數第 15 個交易日）：monthly（K）與 event（J，合成處置事件）各跑一次會寫帳本，
   再跑一次不新增任何列（冪等）；帳本每列有 date／event／nav／cash／positions，已平倉交易有 stock_id／entry_date／exit_date。
3. J 的延長合併、控制組方向；K 的 L 週對照窗；L 的起跑前提順延規則。
4. 峰值記憶體 < 1GB（tracemalloc 峰值＋行程 RSS（有 psutil 才量））。
"""
from __future__ import annotations

import sys
import tempfile
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

tracemalloc.start()
import paper_forward_common as C  # noqa: E402
import paper_10_disposition_tracker as J  # noqa: E402
import paper_11_tdcc_bigholder_tracker as K  # noqa: E402
import paper_12_warrant_wave_tracker as L  # noqa: E402

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
td = Path(tempfile.mkdtemp(prefix="paper_fwd_selftest_"))


def redirect(sp: C.Spec, name: str) -> C.Spec:
    sp.log_path, sp.out_path = td / f"{name}_log.jsonl", td / f"{name}.json"
    return sp


# 1. 正式起跑日前一律 NOT_STARTED
check(cal[-1] < "2026-12-01", f"價格最新日 {cal[-1]} 早於 2026-12-01（本測試前提）")
for name, sp in [("k", redirect(K.spec(), "k_real")), ("l", redirect(L.spec(), "l_real"))]:
    r = C.step(sp, {"px": px, "appear": {"warrants": {}}}, px=px, active=active)
    check(r["state"] == "NOT_STARTED" and not sp.log_path.exists(), f"{name}: 起跑前 NOT_STARTED 且不寫帳本")
jm, jc = J.specs([])
for sp in (redirect(jm, "j_real"), redirect(jc, "jc_real")):
    r = C.step(sp, {"px": px}, px=px, active=active)
    check(r["state"] == "NOT_STARTED" and not sp.log_path.exists(), f"{sp.key}: 起跑前 NOT_STARTED 且不寫帳本")

# 2a. monthly（K）假裝已起跑：起跑日設在某月第一個交易日
fake_start = cal[-15]
k = redirect(K.spec(), "k_fake")
k.start_not_before = fake_start
r1 = C.step(k, {"px": px}, px=px, active=active)
n1 = lines(k.log_path)
r2 = C.step(k, {"px": px}, px=px, active=active)
check(n1 == 15 and lines(k.log_path) == n1 and r2["state"] == "HOLD", f"K monthly：補跑 {n1} 個交易日（應 15），再跑一次不新增（冪等）")
log = C.read_log(k)
check(all(set(e) >= {"date", "event", "nav", "cash", "positions"} for e in log), "K 帳本每列有 date／event／nav／cash／positions")
check(log[0]["event"] in ("inception", "skip"), f"K 第一天事件＝{log[0]['event']}（inception 或 TDCC 缺週 skip）")
reb = [e for e in log if e["event"] in ("inception", "rebalance")]
check(all(len(e["positions"]) <= K.M for e in reb), "K 每次再平衡持股 ≤ 20 檔")
check(all("etf_0050_006208_member" in p for e in reb for p in e.get("picks") or []), "K 入選標的帶 etf_0050_006208_member 欄")
if reb and reb[0]["positions"]:
    vals = [p["units"] * px.close_on(c, reb[0]["date"]) for c, p in reb[0]["positions"].items()]
    check(max(vals) - min(vals) < 1.0, "K 建倉後等權（各檔市值差 < 1 元）")
months = [e.get("rebalance_month") for e in log if e["event"] in ("inception", "rebalance", "skip")]
check(len(months) == len(set(months)), "K 每月最多再平衡一次")

# 2b. event（J）合成處置事件：解除日 r＝起跑日前一交易日；另一段延長事件不得進場
i0 = cal.index(fake_start)
r_day = cal[i0 - 1]
codes = [c for c in sorted(active) if C.is_common(c) and px.close_on(c, r_day) and px.close_on(c, fake_start)
         and (px.avg_turnover(c, cal[i0 - 8], inclusive=False) or 0) >= J.MIN_PRE_TURNOVER][:6]
segs = [{"code": c, "start": cal[i0 - 8], "end": r_day} for c in codes[:4]]
segs.append({"code": codes[4], "start": cal[i0 - 8], "end": r_day})
segs.append({"code": codes[4], "start": fake_start, "end": cal[i0 + 3]})  # 延長：不算解除
ev = J.merged_events(segs, px)
check(sum(1 for e in ev if e["code"] == codes[4]) == 1 and [e for e in ev if e["code"] == codes[4]][0]["end"] == cal[i0 + 3],
      "J 延長處置合併成一個事件、解除日取最後一段迄日")
jm, jc = J.specs(segs)
for sp in (jm, jc):
    redirect(sp, sp.key + "_fake")
    sp.start_not_before = fake_start
ctx = {"px": px}
C.step(jm, ctx, px=px, active=active)
C.step(jc, {"px": px}, px=px, active=active)
lj, lc = C.read_log(jm), C.read_log(jc)
ent_m = set(lj[0].get("entered") or [])
ent_c = set(lc[0].get("entered") or [])
check(not (ent_m & ent_c), "J 主帳本與影子帳本進場標的互斥（期間下跌 vs ≥0）")
check(codes[4] not in ent_m | ent_c, "J 仍在延長處置中的股票不進場")
check(len(ent_m | ent_c) == len(set(codes[:4])) - len([s for s in (ctx.get("skips") or {}).get(fake_start, [])]),
      "J 四個合成解除事件全部分到主帳本或影子帳本（扣掉照實記的 skip）")
check(all(len(e["positions"]) <= J.M for e in lj), "J 持股 ≤ 20 檔")
n_before = lines(jm.log_path)
C.step(jm, {"px": px}, px=px, active=active)
check(lines(jm.log_path) == n_before, "J 再跑一次不新增（冪等）")
# 持有 H 天出場：日曆只剩 14 天，H=20 → 不應有 hold_days 出場
check(not any(t["exit_reason"] == "hold_days" for e in lj for t in e.get("closed_trades") or []), "J 未滿 20 個交易日不出場")
jm.hold_days = 3
redirect(jm, "j_h3")
C.step(jm, {"px": px}, px=px, active=active)
closed = [t for e in C.read_log(jm) for t in e.get("closed_trades") or []]
ent_h3 = {c for e in C.read_log(jm) for c in e.get("entered") or []}
check(bool(closed) == bool(ent_h3) and all(set(t) >= {"stock_id", "entry_date", "exit_date", "entry_px", "exit_px"} for t in closed),
      "J（H 改 3 只測機制）滿 H 天出場、已平倉交易欄位可餵 run_random_timing_control")
if closed:
    t = closed[0]
    check(sum(1 for d in cal if t["entry_date"] < d <= t["exit_date"]) == 3, "J 持有天數＝H 個交易日")

# 3. K 的 L 週窗
h = [{"date": "20261002", "big_holder_ratio": 50.0}, {"date": "20261009", "big_holder_ratio": 51.0},
     {"date": "20261030", "big_holder_ratio": 53.0}, {"date": "20261106", "big_holder_ratio": 54.0}]
d = K.delta_for(h, "2026-11-09")
check(d is not None and abs(d[0] - 3.0) < 1e-9 and d[2] == "20261009", "K Δ＝最新週 − 相隔 4～6 週內最近一週")
check(K.delta_for(h, "2026-11-06") is not None and K.delta_for(h, "2026-11-06")[1] == "20261030", "K 只用資料日早於再平衡日的週（PIT）")
check(K.delta_for(h[2:], "2026-11-09") is None, "K 相隔不足 4 週 → 無訊號")

# 4. L 起跑前提
class _Cal:
    def __init__(self, cal):
        self.calendar = cal


def _mk(root: Path, days):
    for dd in days:
        (root / dd).mkdir(parents=True, exist_ok=True)
        (root / dd / "meta.json").write_text("{}", encoding="utf-8")
        for s in L.SOURCES:
            (root / dd / f"{s}.json.gz").write_bytes(b"")


nov = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24",
       "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-30"]
snap = td / "snap"
_mk(snap, nov[:10])
st, info = L.start_date(_Cal(nov), snap)
check(st == L.START and info["start_deferred"] is False, "L 11/30 前連續 10 個交易日成功 → 12/01 起跑")
_mk(td / "snap_gap", nov[:5] + nov[6:])  # 11/23 缺 → 最長連續 5 天，未達成
check(L.start_date(_Cal(nov), td / "snap_gap")[0] is None, "L 中間缺一天就重算連續天數 → 未達成")
st0, info0 = L.start_date(_Cal(nov), td / "nosnap")
check(st0 is None, "L 快照不足 → 尚未起跑（NOT_STARTED）")


class _FakePx:
    calendar = ["2026-11-20", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-30",
                "2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04", "2026-12-07"]


for dd in _FakePx.calendar:
    (td / "snap2" / dd).mkdir(parents=True, exist_ok=True)
    (td / "snap2" / dd / "meta.json").write_text("{}", encoding="utf-8")
    for s in L.SOURCES:
        (td / "snap2" / dd / f"{s}.json.gz").write_bytes(b"")
st2, info2 = L.start_date(_FakePx(), td / "snap2")
check(st2 == "2027-01-01" and info2["start_deferred"] is True, "L 12 月才達成 → 順延到 2027-01 月初，start_deferred=True")

cur, peak = tracemalloc.get_traced_memory()
rss = None
try:
    import psutil  # noqa: PLC0415
    rss = psutil.Process().memory_info().peak_wset if hasattr(psutil.Process().memory_info(), "peak_wset") else psutil.Process().memory_info().rss
except Exception:  # noqa: BLE001
    pass
check(peak < 1024 ** 3 and (rss is None or rss < 1024 ** 3),
      f"峰值記憶體 < 1GB（tracemalloc 峰值 {peak / 1e6:.0f} MB；行程 {'%.0f MB' % (rss / 1e6) if rss else '未量（無 psutil）'}）")

print(f"\n{'全部通過' if not fails else f'{len(fails)} 項失敗'}")
sys.exit(1 if fails else 0)
