"""自測：price_history 零成交日（close=0／adj_close=0、no_trade=True）不得被當成價格（先.一三五-1ja）。

背景：先.一三五-1iy 發現 price_history 以 close=0 記零成交日（2026-11-03 實測 3,648 列／286 檔，全部帶 no_trade），
`paper_forward_common.Px` 把 0 當價格會除以零或以 0 計值。本支檢查其他讀 price_history 的上線程式。
列的形狀照真實資料（open/high/low/close/adj_close 全 0、volume>0、no_trade=True）。零外部請求、不讀寫真實 data/。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def row(d: str, c: float, adj: float | None = None) -> dict:
    return {"date": d, "open": c, "high": c, "low": c, "close": c, "adj_close": c if adj is None else adj,
            "volume": 1000.0, "turnover": 1000.0 * c}


def zero(d: str) -> dict:
    return {"date": d, "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "adj_close": 0.0,
            "volume": 96.0, "turnover": 2997.0, "no_trade": True}


print("build_strategy_curves.Px")
B = load("build_strategy_curves", ".github/scripts/build_strategy_curves.py")
px = B.Px({"prices": {"0050": [row("2026-10-01", 100), row("2026-10-02", 101), row("2026-10-05", 102)],
                      "9999": [row("2026-10-01", 50), zero("2026-10-02"), row("2026-10-05", 55)]}})
check("零成交日 close() 回 None（不是 0）", px.close("9999", "2026-10-02") is None, px.close("9999", "2026-10-02"))
check("零成交日 close_le() 沿用前一筆真實價", px.close_le("9999", "2026-10-02") == 50, px.close_le("9999", "2026-10-02"))
check("其他日不受影響", px.close("9999", "2026-10-05") == 55)

print("update_picks_ledger_returns._lookup_price_on")
U = load("update_picks_ledger_returns", ".github/scripts/update_picks_ledger_returns.py")
ph = {"9999": [row("2026-10-01", 50), zero("2026-10-02")]}
r = U._lookup_price_on("9999", "2026-10-02", ph)
check("零成交日取前一筆真實收盤（不是 0）", r[0] == 50 and r[1] == "2026-10-01", r)
ph2 = {"9999": [zero("2026-10-01"), zero("2026-10-02")]}
r2 = U._lookup_price_on("9999", "2026-10-02", ph2)
check("全是零成交日→無價（None）", r2[0] is None, r2)

print("build_signal_ledger._reflected／_ref_price")
S = load("build_signal_ledger", ".github/scripts/build_signal_ledger.py")
days = [f"2026-09-{i:02d}" for i in range(1, 31)]
seq = [row(d, 100 + i) for i, d in enumerate(days)]
seq[-1 - S.RUN_BEFORE_DAYS] = zero(seq[-1 - S.RUN_BEFORE_DAYS]["date"])  # 回看基準日剛好零成交
try:
    ref = S._reflected("9999", days[-1], {"9999": seq})
    check("回看基準日零成交不除以零、run_before 為有限正值", ref.get("run_before") is not None and -0.5 < ref["run_before"] < 0.5, ref)
except ZeroDivisionError as e:
    check("回看基準日零成交不除以零", False, repr(e))
p, pd_ = S._ref_price("9999", "2026-10-02", {"9999": [row("2026-10-01", 50), zero("2026-10-02")]})
check("參考價跳過零成交日", p == 50 and pd_ == "2026-10-01", (p, pd_))

print("update_margin_maintenance.closes_from_price_history")
M = load("update_margin_maintenance", ".github/scripts/update_margin_maintenance.py")


class _FakePHS:
    @staticmethod
    def load(_path, codes=None):
        return {"prices": {"9999": [row("2026-10-01", 50), zero("2026-10-02")],
                           "1111": [row("2026-10-02", 20)]}}


M.PHS = _FakePHS
cl = M.closes_from_price_history("2026-10-02")
check("零成交日不以 0 元入擔保品（當缺價）", "9999" not in cl, cl)
check("有成交的照常", cl.get("1111") == 20, cl)

print("generate_scores_momentum._priced_rows＋價格類因子")
sys.path.insert(0, str(ROOT / "research"))
G = load("generate_scores_momentum", "research/generate_scores_momentum.py")
base = [f"2026-07-{i:02d}" for i in range(20, 32)] + [f"2026-08-{i:02d}" for i in range(1, 32)] + [f"2026-09-{i:02d}" for i in range(1, 31)]
seq = [row(d, 100 + i * 0.1) for i, d in enumerate(base)]
seq[-1] = zero(seq[-1]["date"])
pr = G._priced_rows(seq)
check("_priced_rows 去掉零成交列", len(pr) == len(seq) - 1 and all(r["close"] > 0 for r in pr), len(pr))
nh = G._new_high_breakout(pr)
check("最後一天零成交時創新高不算成 −100%", nh is not None and nh > -0.5, nh)
check("對照：未過濾會算成 −100%（記錄修前行為）", G._new_high_breakout(seq) == -1.0, G._new_high_breakout(seq))

print("generate_scores_live._ma_breakout")
L = load("generate_scores_live", "research/generate_scores_live.py")
mb = L._ma_breakout(seq)
check("最後一天零成交時 MA60 突破不算成約 −100%", mb is not None and abs(mb) < 0.5, mb)

print("build_monthly_close（月底那天零成交）")
import json as _json
import tempfile as _tf
MC = load("build_monthly_close", "scripts/build_monthly_close.py")
_ph = {f"{1000 + i}": [row("2026-09-29", 10), row("2026-09-30", 11)] for i in range(520)}
_ph["9999"] = [row("2026-09-29", 50), zero("2026-09-30")]


class _FakePHS2:
    @staticmethod
    def load(_path, codes=None):
        return {"prices": _ph}


with _tf.TemporaryDirectory() as td:
    MC.PHS, MC.DATA, MC.OUT = _FakePHS2, Path(td), Path(td) / "monthly_close.json"
    MC.main()
    mc = _json.loads(MC.OUT.read_text(encoding="utf-8")).get("closes") or {}
check("月底零成交不寫 0 元月底價", (mc.get("9999") or {}).get("2026-09") is None, mc.get("9999"))
check("其他檔月底價照常", (mc.get("1000") or {}).get("2026-09") == 11, mc.get("1000"))

print("build_sector_flow._closes／_daily_px")
SF = load("build_sector_flow", "scripts/build_sector_flow.py")
_doc = {"prices": {"9999": [row("2026-10-01", 50), zero("2026-10-02")], "1111": [row("2026-10-02", 20)]}}
cs = SF._closes(_doc)
check("最新一天零成交不當 0 元價", "9999" not in cs and cs.get("1111") == 20, cs)
dp = SF._daily_px({"prices": {"9999": [row("2026-10-01", 50), zero("2026-10-02"), row("2026-10-05", 52)]}})["9999"]
check("零成交日不入日價表、隔天不拿 0 當前一天", "20261002" not in dp and dp["20261005"][2] != 0, dp)

print("update_strategy_performance.close_on")
USP = load("update_strategy_performance", "research/update_strategy_performance.py")
check("零成交日回 None", USP.close_on({"9999": [row("2026-10-01", 50), zero("2026-10-02")]}, "9999", "2026-10-02") is None)

print("auto_trading_review._prev_close_before")
ATR = load("auto_trading_review", "research/auto_trading_review.py")
_pd = {"prices": {"0050": [row("2026-10-01", 50), zero("2026-10-02")]}}
check("前收沿用前一筆真實收盤", ATR._prev_close_before("2026-10-03", "0050", _pd) == 50, ATR._prev_close_before("2026-10-03", "0050", _pd))

print("auto_ledger_view._close_on_or_before（先.一三五-1jc：日誌頁真錢帳本估值）")
ALV = load("auto_ledger_view", "research/auto_ledger_view.py")
_rows = [row("2026-10-01", 50), zero("2026-10-02"), row("2026-10-05", 52)]
check("零成交日沿用前一筆真實收盤（不以 0 估值）", ALV._close_on_or_before(_rows, "2026-10-02") == 50, ALV._close_on_or_before(_rows, "2026-10-02"))
check("之後的真實收盤照常取", ALV._close_on_or_before(_rows, "2026-10-05") == 52)
check("只有零成交列 → None（交給呼叫端既有缺價處理）", ALV._close_on_or_before([zero("2026-10-02")], "2026-10-02") is None)

print("paper_1b_tracker／paper_3_tracker._closes（先.一三五-1je）")
for _nm, _rel in (("paper_1b_tracker", "research/paper_1b_tracker.py"), ("paper_3_tracker", "research/paper_3_tracker.py")):
    _M = load(_nm, _rel)
    _cl = _M._closes({"00697B": [row("2026-10-01", 40), zero("2026-10-02"), row("2026-10-05", 41)]}, "00697B")
    check(f"{_nm} 零成交日不進價格序列（不以 0 計值／不除以零）", "2026-10-02" not in _cl and _cl.get("2026-10-05") == 41, _cl)

print("build_picks_ledger.build_snapshot（先.一三五-1je：報價檔 close=0 也是零成交）")
import json as _json  # noqa: E402
import tempfile as _tf  # noqa: E402
BPL = load("build_picks_ledger", ".github/scripts/build_picks_ledger.py")
with _tf.TemporaryDirectory() as _td:
    _sp = Path(_td) / "scores.json"
    _sp.write_text(_json.dumps({"meta": {"data_asof": "2026-10-02"}, "stocks": [
        {"code": "9999", "name": "零成交", "rank": 1, "total_score": 1},
        {"code": "1111", "name": "有成交", "rank": 2, "total_score": 1}]}), encoding="utf-8")
    _q = {"9999": {"close": 0.0, "date": "2026-10-02"}, "1111": {"close": 20.0, "date": "2026-10-02"}}
    _snap = BPL.build_snapshot("test", _sp, _q, None)
    _pk = {p["code"]: p for p in (_snap or {}).get("picks", [])}
    check("報價 close=0 不記成 0 元快照價", (_pk.get("9999") or {}).get("close_price", "x") is None, _pk.get("9999"))
    check("有成交的照常記價", (_pk.get("1111") or {}).get("close_price") == 20.0, _pk.get("1111"))

print(f"\n合計 {ok} 項通過、{fail} 項失敗")
sys.exit(1 if fail else 0)
