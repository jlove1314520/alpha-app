# -*- coding: utf-8 -*-
"""先.一四九-2 甲：自選股日內分時匯出自測（暫存目錄、假熱檔，不碰真檔、不提交、零外部請求）。
用法：python scripts/selftest_export_intraday_tw.py
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import export_intraday_tw as X  # noqa: E402

TW = timezone(timedelta(hours=8))
tmp = Path(tempfile.mkdtemp())
(tmp / "research").mkdir()
X.ROOT, X.HOT, X.WATCH = tmp, tmp / "research" / "hot.json", tmp / "research" / "wl.json"
X.WATCH.write_text(json.dumps({"codes": ["2330", "AAPL.US", "9999"]}), encoding="utf-8")


def hot(upd, day="2026-11-06"):
    bar = lambda hm, c: {"t": f"{day}T{hm}", "o": c, "h": c, "l": c, "c": c, "v": 1}
    X.HOT.write_text(json.dumps({"updated_at": upd, "kbars": {
        "2330": [bar("09:00", 10), bar("09:01", 11), {"t": "2026-11-05T13:30", "c": 9}],
        "TAIEX": [bar("09:00", 100)], "TXF_NEAR": [bar("09:00", 1)]}}), encoding="utf-8")


out = tmp / "data" / "intraday_tw" / "2026-11-06.json"
res = []
X.HOT.unlink(missing_ok=True)
res.append(("沒有熱檔→不寫", X.run(datetime(2026, 11, 6, 10, 0, tzinfo=TW), commit=False).startswith("skip_讀不到") and not out.exists()))
hot("2026-11-05T13:45:00+08:00")
res.append(("熱檔是昨天→不寫", "不是今天" in X.run(datetime(2026, 11, 6, 10, 0, tzinfo=TW), commit=False) and not out.exists()))
hot("2026-11-06T09:30:00+08:00")
res.append(("熱檔 30 分鐘沒更新（盤中）→不寫", "沒更新" in X.run(datetime(2026, 11, 6, 10, 0, tzinfo=TW), commit=False) and not out.exists()))
hot("2026-11-06T09:58:00+08:00")
r = X.run(datetime(2026, 11, 6, 10, 0, tzinfo=TW), commit=False)
d = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
idx = json.loads((tmp / "data" / "intraday_tw" / "index.json").read_text(encoding="utf-8")) if out.exists() else {}
res.append(("正常→只含自選股＋指數、只收當天 bar、不含期貨／美股／沒資料代號", r.startswith("written")
            and sorted(d.get("bars", {})) == ["2330", "TAIEX"] and d["bars"]["2330"] == [["09:00", 10, 10, 10, 10, 1], ["09:01", 11, 11, 11, 11, 1]]))
res.append(("index.json 指向今天", idx.get("latest") == "2026-11-06"))
res.append(("10 分鐘後→skip_gap", X.run(datetime(2026, 11, 6, 10, 10, tzinfo=TW), commit=False).startswith("skip_gap")))
hot("2026-11-06T10:19:00+08:00")
res.append(("20 分鐘後→再寫", X.run(datetime(2026, 11, 6, 10, 20, tzinfo=TW), commit=False).startswith("written")))
res.append(("13:36（距上次不到 14 分鐘也要寫收盤版）", X.run(datetime(2026, 11, 6, 13, 36, tzinfo=TW), commit=False).startswith("written")
            if X.run(datetime(2026, 11, 6, 13, 30, tzinfo=TW), commit=False) else False))
res.append(("收盤版寫過→skip_final_done", X.run(datetime(2026, 11, 6, 13, 45, tzinfo=TW), commit=False) == "skip_final_done"))
X.HOT.write_text("{壞掉", encoding="utf-8")
res.append(("自身例外不丟出（十二節）", isinstance(X.run(datetime(2026, 11, 7, 10, 0, tzinfo=TW), commit=False), str)))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
