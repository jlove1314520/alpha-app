# -*- coding: utf-8 -*-
"""先.十四-三 自測：紙.一 帳本 date+event 重複偵測。

全部在暫存目錄進行，不碰真實的 paper_7030_log.jsonl／paper_7030.json／PROGRESS_HEARTBEAT.jsonl。
檢查：①無重複→None ②重複→指出列號 ③_abort_duplicate 寫 last_error=DUPLICATE_LOG_ENTRY 與心跳 ERROR
④run() 遇重複即中止、不呼叫價格載入、不寫帳本、不刪任何列 ⑤守門員自身失敗（summary 目錄不可寫）只降級不拋例外。
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paper_7030_tracker as T  # noqa: E402

ROW = {"date": "2026-10-01", "event": "inception", "nav": 1000000.0, "stock_weight_post": 0.7,
       "bond_weight_post": 0.3, "rebalance_trade": {"direction": "none", "notional": 0.0, "cost": 0.0}}
ROW2 = dict(ROW, date="2026-10-30", event="month_end")
results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


check("無重複回 None", T._find_duplicate([ROW, ROW2]) is None)
check("空帳本回 None", T._find_duplicate([]) is None)
d = T._find_duplicate([ROW, ROW2, dict(ROW2)])
check("重複指出第3列", d is not None and d.startswith("第3列"))
check("同日不同 event 不算重複", T._find_duplicate([ROW, dict(ROW, event="month_end")]) is None)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    T.LOG_PATH = td / "log.jsonl"
    T.APP_SUMMARY_PATH = td / "paper_7030.json"
    T.HEARTBEAT_PATH = td / "hb.jsonl"
    with open(T.LOG_PATH, "w", encoding="utf-8") as f:
        for r in (ROW, ROW2, ROW2):
            f.write(json.dumps(r) + "\n")
    before = T.LOG_PATH.read_bytes()
    called = {"prices": 0}

    def fake_prices():
        called["prices"] += 1
        return []

    T._load_0050_price_series = fake_prices
    out = T.run()
    check("run() 中止並回 aborted", out.get("aborted") is True and "重複" in out.get("reason", ""))
    check("run() 未載入價格", called["prices"] == 0)
    check("帳本位元組未變（未刪、未寫）", T.LOG_PATH.read_bytes() == before)
    s = json.loads(T.APP_SUMMARY_PATH.read_text(encoding="utf-8"))
    check("last_error.status=DUPLICATE_LOG_ENTRY", s.get("last_error", {}).get("status") == "DUPLICATE_LOG_ENTRY")
    hb = [json.loads(x) for x in T.HEARTBEAT_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]
    check("心跳 status=ERROR 且標 紙.一", hb and hb[-1]["status"] == "ERROR" and hb[-1]["item"] == "紙.一")

    # 守門員自身失敗：summary 路徑指向不存在的磁碟機，寫入必失敗，仍不得拋例外
    T.APP_SUMMARY_PATH = Path("Q:/nonexistent_dir/paper_7030.json")
    T.HEARTBEAT_PATH = td / "hb2.jsonl"
    try:
        T._abort_duplicate("自測注入")
        check("守門員自身寫檔失敗只降級不拋例外", True)
    except Exception as e:  # noqa: BLE001
        check(f"守門員自身寫檔失敗只降級不拋例外（拋出 {type(e).__name__}）", False)
    check("summary 寫失敗時心跳仍寫入", T.HEARTBEAT_PATH.exists())

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
