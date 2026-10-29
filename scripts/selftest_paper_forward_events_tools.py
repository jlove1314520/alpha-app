# -*- coding: utf-8 -*-
"""自測：事件型前向模擬（模擬 P／Q／R，2027-01-04 起跑）共用小工具與兩個未被直接測過的函式（先.一三五-1ax／1ay）。

背景：先.一三五-1av 涵蓋表之後再掃一次，`research/paper_forward_events.py` 的 row_on／prev_row／tindex／
weekday_shift 沒有被任何 selftest 直接呼叫；`paper_16.audit_status()`、`paper_17.news_by_day()` 也沒有。
全部用合成資料與暫存檔，不讀真實價格、不算任何策略報酬、零網路請求、不改追蹤程式。

paper_forward_events：
1. iso：'20261027'／'2026-10-27' 都回 '2026-10-27'。
2. row_on／prev_row：命中、該日不存在 → None、第一列沒有前一列 → None。
3. raw_ret：用原始 close（不是 adj_close）算；缺前一列 → None。
4. tindex：交易日回自己位置；非交易日回「≤d 最後交易日」；早於日曆 → -1；晚於日曆 → 最後一個位置。
5. weekday_shift：跨週末（週五 +1 → 週一、週一 -1 → 週五）；n=0 回原日。
6. dedupe：同代號 gap 個交易日內第二個事件剔除、剛好滿 gap 保留、不同代號互不影響、輸入順序不影響結果。
7. trading_window：日曆內兩側；左側超出用週一～五近似；右側超出從日曆最後一天往後補足；d 在日曆之後從 d 起算。
   d 是非交易日時以「≤d 最後交易日」為中心——記成現行行為（KNOWN_BEHAVIOR），不判對錯。
paper_16 audit_status：
8. 稽核檔不存在 → PENDING（附已累積事件數）；precision 0.69 → DATA_DEFECT；0.70 → PASSED（門檻含等號）。
paper_17 news_by_day：
9. 檔案不存在 → 空集合（不拋錯）；空行略過；code 轉字串；壞 JSON 行只略過那一行（1az 修正前會丟掉壞行之後全部）。
"""
from __future__ import annotations

import json
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
import paper_16_order_win_tracker as P16  # noqa: E402
import paper_17_margin_liquidation_tracker as P17  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def note(msg: str) -> None:
    print("KNOWN_BEHAVIOR " + msg)


# 合成日曆：2026-12-28（一）～2027-01-08（五），扣掉 2027-01-01（五）休市
CAL = ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-04",
       "2027-01-05", "2027-01-06", "2027-01-07", "2027-01-08"]


def _rows(closes, adj=None):
    return [{"date": d, "open": c, "high": c, "low": c, "close": c,
             "adj_close": (adj[i] if adj else c)} for i, (d, c) in enumerate(zip(CAL, closes))]


px = C.Px({
    "1101": _rows([10, 11, 12, 12, 12, 12, 12, 12, 12], adj=[5, 5, 5, 5, 5, 5, 5, 5, 5]),
    "2330": _rows([100] * 9),
})

# 1
check(E.iso("20261027") == "2026-10-27" and E.iso("2026-10-27") == "2026-10-27", "iso 兩種格式")
# 2
check(E.row_on(px, "1101", "2026-12-29")["close"] == 11, "row_on 命中")
check(E.row_on(px, "1101", "2027-01-01") is None and E.row_on(px, "9999", "2026-12-29") is None, "row_on 非交易日／無代號 → None")
check(E.prev_row(px, "1101", "2026-12-29")["date"] == "2026-12-28", "prev_row 前一列")
check(E.prev_row(px, "1101", "2026-12-28") is None, "prev_row 第一列 → None")
# 3
r = E.raw_ret(px, "1101", "2026-12-29")
check(r is not None and abs(r - 0.1) < 1e-12, "raw_ret 用原始 close（11/10−1，不是 adj 的 0）")
check(E.raw_ret(px, "1101", "2026-12-28") is None, "raw_ret 缺前一列 → None")
# 4
check(E.tindex(px, "2027-01-04") == 4, "tindex 交易日")
check(E.tindex(px, "2027-01-01") == 3, "tindex 非交易日 → ≤d 最後交易日（12-31）")
check(E.tindex(px, "2026-12-01") == -1, "tindex 早於日曆 → -1")
check(E.tindex(px, "2027-02-01") == len(CAL) - 1, "tindex 晚於日曆 → 最後位置")
# 5
check(E.weekday_shift("2027-01-08", 1) == "2027-01-11", "weekday_shift 週五 +1 → 週一")
check(E.weekday_shift("2027-01-04", -1) == "2027-01-01", "weekday_shift 週一 -1 → 週五（不看休市，近似）")
check(E.weekday_shift("2027-01-06", 0) == "2027-01-06", "weekday_shift n=0 回原日")
# 6
evs = [{"code": "1101", "t0": "2027-01-04"}, {"code": "1101", "t0": "2026-12-28"},
       {"code": "1101", "t0": "2027-01-05"}, {"code": "2330", "t0": "2026-12-29"}]
out = E.dedupe(evs, px, 4)
got = [(e["code"], e["t0"]) for e in out]
check(got == [("1101", "2026-12-28"), ("2330", "2026-12-29"), ("1101", "2027-01-04")],
      f"dedupe gap=4：12-28 採計、01-04（距 4 日）保留、01-05（距 1 日）剔除、他檔不受影響，實得 {got}")
check([(e["code"], e["t0"]) for e in E.dedupe(list(reversed(evs)), px, 4)] == got, "dedupe 輸入順序不影響")
check([(e["code"], e["t0"]) for e in E.dedupe(evs, px, 5)] == [("1101", "2026-12-28"), ("2330", "2026-12-29"), ("1101", "2027-01-05")],
      "dedupe gap=5：01-04（距 4 日）剔除、01-05（距 5 日＝滿 gap）保留")
# 7
check(E.trading_window(px, "2027-01-04", 2) == ("2026-12-30", "2027-01-06"), "trading_window 日曆內")
check(E.trading_window(px, "2026-12-29", 3) == ("2026-12-24", "2027-01-04"), "trading_window 左側超出 → 週一～五近似")
check(E.trading_window(px, "2027-01-07", 3) == ("2027-01-04", "2027-01-12"),
      "trading_window 右側超出 → 從 01-08 再往後補 2 個平日")
check(E.trading_window(px, "2027-01-20", 2)[1] == "2027-01-22", "trading_window d 在日曆之後 → 從 d 起算")
w = E.trading_window(px, "2027-01-01", 1)
note(f"trading_window 非交易日 01-01 n=1 → {w}（以 12-31 為中心，左側＝12-30）")
check(w == ("2026-12-30", "2027-01-04"), "trading_window 非交易日行為與上列記錄一致")

# 8 / 9：暫存檔，跑完還原模組常數
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    old_audit, old_news = P16.AUDIT, P17.NEWS
    try:
        P16.AUDIT = tdp / "audit.json"
        s = P16.audit_status(12)
        check(s["state"] == "PENDING" and s["events_since_start"] == 12 and s["audit_at_n"] == 60, "audit_status 無檔 → PENDING")
        P16.AUDIT.write_text(json.dumps({"precision": 0.69}), encoding="utf-8")
        check(P16.audit_status(60)["state"] == "DATA_DEFECT", "audit_status 0.69 → DATA_DEFECT")
        P16.AUDIT.write_text(json.dumps({"precision": 0.70}), encoding="utf-8")
        check(P16.audit_status(60)["state"] == "PASSED", "audit_status 0.70 → PASSED（含等號）")

        P17.NEWS = tdp / "none.jsonl"
        check(P17.news_by_day() == set(), "news_by_day 無檔 → 空集合")
        P17.NEWS = tdp / "news.jsonl"
        P17.NEWS.write_text('{"code": 2330, "date": "2027-01-04"}\n\n{"code": "1101", "date": "2027-01-05"}\n',
                            encoding="utf-8")
        check(P17.news_by_day() == {("2330", "2027-01-04"), ("1101", "2027-01-05")}, "news_by_day 空行略過、code 轉字串")
        P17.NEWS.write_text('{"code": "2330", "date": "2027-01-04"}\n{壞\n{"code": "1101", "date": "2027-01-05"}\n',
                            encoding="utf-8")
        check(P17.news_by_day() == {("2330", "2027-01-04"), ("1101", "2027-01-05")},
              "news_by_day 壞 JSON 行只略過那一行，前後列都保留（先.一三五-1az 修正）")
    finally:
        P16.AUDIT, P17.NEWS = old_audit, old_news

print(f"\n{'全部通過' if not FAILS else f'{len(FAILS)} 項失敗'}")
sys.exit(1 if FAILS else 0)
