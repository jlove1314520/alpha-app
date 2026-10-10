"""常備.開發-18 自測：三種觸發（漲跌幅／到價／事件前一日）、每檔每日最多一則、
非盤中不動作、規則驗證、守門員自身失敗不拋例外。不送任何真推播（send 一律替換成假函式）。

執行：python research/price_alerts_selftest.py
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import price_alerts as pa  # noqa: E402

TW = pa.TW
FRI_10 = datetime(2026, 10, 16, 10, 0, tzinfo=TW)  # 週五盤中
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"（{detail}）" if detail and not cond else ""))


def fake_sender(log, ok=1, errors=()):
    def _s(title, body):
        log.append((title, body))
        return {"ok": ok, "errors": list(errors)}
    return _s


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        pa.save_rules(base, {"rules": {
            "2330": {"pct": 3, "above": None, "below": None, "event": False},
            "2454": {"pct": None, "above": 1500, "below": None, "event": False},
            "2317": {"pct": None, "above": None, "below": 100, "event": False},
            "0050": {"pct": None, "above": None, "below": None, "event": True},
            "1513": {"pct": 5, "above": None, "below": None, "event": True},
        }})
        quotes = {
            "2330": {"name": "台積電", "last": 1100, "change_pct": -3.4},
            "2454": {"name": "聯發科", "last": 1510, "change_pct": 1.2},
            "2317": {"name": "鴻海", "last": 99.5, "change_pct": -0.5},
            "1513": {"name": "中興電", "last": 150, "change_pct": 1.0},
        }
        # 週五 → 下一個平日是週一 10/19
        events = [{"code": "0050", "name": "元大台灣50", "date": "2026-10-19", "type": "除權息", "title": "除權息交易日（現金 1 元）"},
                  {"code": "1513", "name": "中興電", "date": "2026-10-17", "type": "法說會", "title": "週六不算"}]
        log = []
        r = pa.run_once(base, quotes, now=FRI_10, events=events, send=fake_sender(log))
        kinds = {s["code"]: s["kind"] for s in r["sent"]}
        check("觸發一：漲跌幅 ±X%（2330 −3.4% ≥ 3%）", kinds.get("2330") == "pct", str(kinds))
        check("觸發二：到價（2454 漲到 1500、2317 跌到 100）", kinds.get("2454") == "above" and kinds.get("2317") == "below", str(kinds))
        check("觸發三：事件前一日（週五提醒週一的 0050 除權息）", kinds.get("0050") == "event", str(kinds))
        check("未達門檻與週末事件不觸發（1513 +1% < 5%、10/17 週六不是下一個平日）", "1513" not in kinds, str(kinds))
        check("每則內文標「非投資建議」", all("非投資建議" in b for _, b in log))
        check("下跌文案正確（2330 寫「下跌」）", any("2330" in t and "下跌" in t for t, _ in log), str(log))

        log2 = []
        quotes["1513"]["change_pct"] = 6.0
        r2 = pa.run_once(base, quotes, now=FRI_10.replace(minute=1), events=events, send=fake_sender(log2))
        check("每檔每日最多一則：同日第二分鐘已推過的不再推，只推新觸發的 1513", [s["code"] for s in r2["sent"]] == ["1513"], str(r2["sent"]))
        log3 = []
        r3 = pa.run_once(base, quotes, now=datetime(2026, 10, 19, 9, 1, tzinfo=TW), events=events, send=fake_sender(log3))
        check("隔一個交易日重新計算（週一 2330 可再推）", "2330" in [s["code"] for s in r3["sent"]], str(r3["sent"]))

        r4 = pa.run_once(base, quotes, now=datetime(2026, 10, 19, 14, 0, tzinfo=TW), events=events, send=fake_sender([]))
        check("非盤中（13:30 後）不檢查", not r4["checked"] and not r4["sent"])
        r5 = pa.run_once(base, quotes, now=datetime(2026, 10, 18, 10, 0, tzinfo=TW), events=events, send=fake_sender([]))
        check("週日不檢查", not r5["checked"])

        # 沒有即時報價（只剩冷檔）→ 價格類不判斷，事件類照常
        b2 = Path(td) / "b2"
        pa.save_rules(b2, {"rules": {"2330": {"pct": 1, "event": True}}})
        r6 = pa.run_once(b2, None, now=FRI_10, events=[{"code": "2330", "date": "2026-10-19", "type": "法說會", "title": "Q3 法說"}], send=fake_sender([]))
        check("沒有即時報價時只發事件類", [s["kind"] for s in r6["sent"]] == ["event"], str(r6["sent"]))

        # 推播網路失敗：最多重試 MAX_SEND_ATTEMPTS 次；無訂閱屬永久性，當日不再試
        b3 = Path(td) / "b3"
        pa.save_rules(b3, {"rules": {"2330": {"pct": 1}}})
        cnt = []
        for m in range(5):
            pa.run_once(b3, quotes, now=FRI_10.replace(minute=m), events=[], send=fake_sender(cnt, ok=0, errors=["NETWORK:Timeout"]))
        check(f"網路失敗最多重試 {pa.MAX_SEND_ATTEMPTS} 次", len(cnt) == pa.MAX_SEND_ATTEMPTS, str(len(cnt)))
        b4 = Path(td) / "b4"
        pa.save_rules(b4, {"rules": {"2330": {"pct": 1}}})
        cnt4 = []
        for m in range(3):
            pa.run_once(b4, quotes, now=FRI_10.replace(minute=m), events=[], send=fake_sender(cnt4, ok=0, errors=["NO_SUBSCRIPTION:沒有任何裝置訂閱推播"]))
        check("無訂閱裝置屬永久性錯誤，當日只試一次", len(cnt4) == 1, str(len(cnt4)))

        # 規則驗證
        bad = [{"rules": {"AAPL": {"pct": 3}}}, {"rules": {"2330": {"pct": 30}}}, {"rules": {"2330": {"above": -1}}},
               {"rules": {"2330": {"above": 100, "below": 120}}}, {"rules": "x"}]
        rej = 0
        for p in bad:
            try:
                pa.validate_rules(p)
            except ValueError:
                rej += 1
        check("規則驗證：美股代號／超過 20%／負價／跌到價≥漲到價／格式錯 全部拒絕", rej == len(bad), f"{rej}/{len(bad)}")
        check("全空規則的代號被丟掉", pa.validate_rules({"rules": {"2330": {"pct": None, "event": False}}}) == {})

        # 守門員自身失敗不拋例外：規則檔損毀、send 拋例外
        b5 = Path(td) / "b5"
        b5.mkdir()
        (b5 / pa.RULES_NAME).write_text("{壞掉", encoding="utf-8")
        r7 = pa.run_once(b5, quotes, now=FRI_10, events=[], send=fake_sender([]))
        check("規則檔損毀 → 當作沒有規則、不拋例外", r7["ok"] and r7["sent"] == [])

        def boom(t, b):
            raise RuntimeError("x")
        r8 = pa.run_once(b4.parent / "b3", quotes, now=datetime(2026, 10, 20, 10, 0, tzinfo=TW), events=[], send=boom)
        check("send 拋例外 → 只記錄、不中斷", r8["ok"] and r8["sent"] and r8["sent"][0]["delivered"] == 0, str(r8))
        (b5 / pa.STATE_NAME).unlink(missing_ok=True)
        (b5 / pa.STATE_NAME).mkdir()  # 狀態檔路徑變成目錄 → 寫檔失敗
        pa.save_rules(b5, {"rules": {"2330": {"pct": 1}}})
        r9 = pa.run_once(b5, quotes, now=FRI_10, events=[], send=fake_sender([]))
        check("狀態檔寫入失敗 → 回傳 ok=false 與原因，不拋例外", r9["ok"] is False and r9["errors"], str(r9))

    n_fail = RESULTS.count(False)
    print(f"\n合計 {len(RESULTS) - n_fail}/{len(RESULTS)} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
