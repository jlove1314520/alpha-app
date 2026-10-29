"""自測：盤前日報／週覆盤 `.github/scripts/build_daily_brief.py`（先.一三五-1cg）。

`DATA`／`OUT` 換成暫存目錄、「現在」固定為 2026-10-30（週五）08:00 台北：零外部請求、不讀也不動真實 data/。
App 今日頁盤前日報與日誌頁週覆盤唯一來源，這裡確認：各塊數字照輸入、資料日期照輸入標示、
未來 3 天事件窗與重大訊息日、本週加權漲跌、任一輸入缺只讓該塊標 error 其他照出、全部缺時不覆寫既有輸出。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_daily_brief", ROOT / ".github" / "scripts" / "build_daily_brief.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)


class _FixedNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 30, 8, 0, tzinfo=tz)


D.datetime = _FixedNow

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


MARKET_US = {"fetched_at": "2026-10-30T05:10", "indices": {
    "^GSPC": {"name": "S&P 500", "close": 6800.0, "change_pct": 0.456, "as_of": "2026-10-29"},
    "^IXIC": {"name": "Nasdaq", "close": 23000.0, "change_pct": -1.234, "as_of": "2026-10-29"}}}
MARKET_TW = {"fetched_at": "2026-10-29T17:13", "taiex": {
    "close": 28000.0, "change_pct": 0.5,
    "sparkline": [27000.0, 27200.0, 27500.0, 27800.0, 27900.0, 28000.0],
    "sparkline_dates": ["2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29"]},
    "futures": {"TX": {"contract_month": "202611", "last": 28100.0, "change_pct": 0.3,
                       "trading_session": "夜", "date": "20261029"}}}
EVENTS = {"events": [
    {"date": "2026-10-30", "type": "法說會", "code": "2330", "name": "台積電", "title": "法說"},
    {"date": "2026-11-02", "type": "除權息", "code": "0050", "name": "元大台灣50", "title": "除息"},
    {"date": "2026-11-03", "type": "法說會", "code": "2454", "name": "聯發科", "title": "法說"},  # 超出 3 天窗
    {"date": "2026-10-29", "type": "重大訊息", "source": "TWSE 重大訊息", "code": "2330"},
    {"date": "2026-10-29", "type": "重大訊息", "source": "TPEx 重大訊息", "code": "6488"},
    {"date": "2026-10-29", "type": "董事會", "source": "TWSE 重大訊息", "code": "2330"},
    {"date": "2026-10-28", "type": "重大訊息", "source": "TWSE 重大訊息", "code": "1101"},
    {"date": "2026-10-30", "type": "重大訊息", "source": "TWSE 重大訊息", "code": "9999"},  # 今天的不算前一日
]}
NEWS = {"fetched_at": "2026-10-30T07:00", "news": [{"codes": ["2330", "2317"]}, {"codes": ["2330"]}, {"codes": []}]}
CURVES = {"lines": [
    {"group": "paper", "id": "p1", "label": "模擬 A", "started": True, "start_date": "2026-10-01",
     "as_of": "2026-10-29", "metrics": {"cum_pct": 1.234, "bench_cum_pct": 0.5}},
    {"group": "paper", "id": "p2", "label": "模擬 B", "started": False, "inception_note": "11/2 開跑"},
    {"group": "picks", "id": "x", "label": "不是紙上"}]}


def setup(d: Path, skip=()) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name, doc in (("market_us.json", MARKET_US), ("market_tw.json", MARKET_TW), ("events.json", EVENTS),
                      ("news.json", NEWS), ("strategy_curves.json", CURVES)):
        if name not in skip:
            (d / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def run(d: Path, out: Path):
    D.DATA = d
    D.OUT = out
    try:
        D.main()
        return None
    except Exception as e:  # noqa: BLE001
        return e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    out = base / "daily_brief.json"

    print("情境一：輸入齊全")
    d1 = base / "d1"
    setup(d1)
    err = run(d1, out)
    check("沒有例外", err is None, repr(err))
    doc = json.loads(out.read_text(encoding="utf-8"))
    pm = doc["premarket"]
    check("date＝今天、data_asof＝加權最後交易日", doc["date"] == "2026-10-30" and doc["data_asof"] == "2026-10-29",
          (doc["date"], doc["data_asof"]))
    check("免責字樣", doc["disclaimer"] == D.DISCLAIMER)
    check("美股行帶資料日與漲跌", pm["lines"][0] == "美股（2026-10-29）：S&P 500 +0.46%、Nasdaq -1.23%", pm["lines"][0])
    check("台指期行（夜盤、千分位）", pm["lines"][1] == "台指期 202611（夜盤）28,100，+0.30%", pm["lines"][1])
    check("台指期資料日由 YYYYMMDD 轉成 2026-10-29", pm["tw"]["tx_futures"]["as_of"] == "2026-10-29")
    check("line_dates／line_markets 與 lines 等長", len(pm["line_dates"]) == len(pm["lines"]) == len(pm["line_markets"]))
    check("行情行的市場標記", pm["line_markets"][:3] == ["us", "tw", "tw"], pm["line_markets"])
    ev = pm["events"]
    check("未來 3 天：法說會 1、除權息 1（11/3 超出窗不算）", ev["upcoming_counts"] == {"法說會": 1, "除權息": 1}, ev["upcoming_counts"])
    check("重大訊息日＝今天以前最後一天 10-29", ev["material_date"] == "2026-10-29", ev["material_date"])
    check("10-29 重大訊息 3 則、依代號計數", ev["material_total"] == 3 and ev["material_by_code"] == {"2330": 2, "6488": 1},
          ev["material_by_code"])
    check("新聞（無存檔索引→退回 news.json）依代號計數", pm["news"]["by_code"] == {"2330": 2, "2317": 1}, pm["news"])
    wk = doc["weekly"]
    check("週起日＝週一 10-26", wk["week_start"] == "2026-10-26", wk["week_start"])
    check("本週加權：上週五 27200→28000、4 天", wk["taiex_week"] == {"from_close": 27200.0, "to_close": 28000.0,
          "to_date": "2026-10-29", "change_pct": 2.94, "days": 4}, wk["taiex_week"])
    check("紙上追蹤只取 paper 組、1／2 已啟動", wk["lines"][1] == "紙上追蹤：1／2 條已啟動（模擬 A 累計 +1.23%）", wk["lines"])
    good = out.read_text(encoding="utf-8")

    print("情境二：market_tw.json 缺 → 只有台股塊標 error，其他照出")
    d2 = base / "d2"
    setup(d2, skip=("market_tw.json",))
    out2 = base / "brief2.json"
    err = run(d2, out2)
    check("沒有例外", err is None, repr(err))
    check("有寫出檔案", out2.exists())
    if out2.exists():
        doc2 = json.loads(out2.read_text(encoding="utf-8"))
        check("台股塊標 error", "error" in doc2["premarket"]["tw"])
        check("美股行照出", doc2["premarket"]["lines"][0].startswith("美股（2026-10-29）"))
        check("data_asof 留空、不編日期", doc2["data_asof"] is None, doc2["data_asof"])
        check("週覆盤紙上追蹤照出", any(x.startswith("紙上追蹤") for x in doc2["weekly"]["lines"]))

    print("情境三：輸入全部讀不到 → 不覆寫既有輸出")
    d3 = base / "d3"
    d3.mkdir()
    (d3 / "market_us.json").write_text("{壞", encoding="utf-8")
    err = run(d3, out)
    check("沒有例外", err is None, repr(err))
    check("既有輸出未被改", out.read_text(encoding="utf-8") == good)

    print("情境四：週一盤前本週沒有收盤 → 改報上一週")
    _FixedNow.now = classmethod(lambda cls, tz=None: datetime(2026, 11, 2, 8, 0, tzinfo=tz))
    out4 = base / "brief4.json"
    err = run(d1, out4)
    doc4 = json.loads(out4.read_text(encoding="utf-8"))
    check("沒有例外", err is None, repr(err))
    check("週起日退回 10-26、仍是 4 天", doc4["weekly"]["week_start"] == "2026-10-26"
          and (doc4["weekly"]["taiex_week"] or {}).get("days") == 4, doc4["weekly"])

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
