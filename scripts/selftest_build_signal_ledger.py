"""自測：前瞻訊號台帳快照 `.github/scripts/build_signal_ledger.py`（先.一三五-1cl）。

events／news／price_history（暫存單檔）／台帳全部換成暫存路徑、「今天」固定：零外部請求、不讀也不動真實 data/。
B19 鐵律「訊號只能事前寫入、不得事後補建、寫入後不可修改」目前沒有任何自測守門，這裡確認：
新鮮度窗外的舊事件與未來日期事件不補建、只收 L1 白名單類型與來源、同 ID 已存在整筆跳過且既有訊號位元組不變、
新訊號 entry／returns 全 null、L1 或兩家獨立媒體才升「訊號」（經濟日報三個 RSS 只算一家）、價格序列不足標 unknown、
過期參考價記 null、台帳／價格檔讀不出來不覆寫歷史訊號。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime as _dt, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_signal_ledger", ROOT / ".github" / "scripts" / "build_signal_ledger.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

NOW = _dt(2026, 1, 30, 17, 13, tzinfo=B.TW_TZ)


class FixedDT(_dt):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


B.datetime = FixedDT

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def cal(n_end="2026-01-30", n=40):
    out, d = [], _dt.strptime(n_end, "%Y-%m-%d")
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y-%m-%d"))
        d -= timedelta(days=1)
    return sorted(out)


CAL = cal()
PH = {"meta": {}, "prices": {
    "2330": [{"date": x, "close": 500.0 + i, "volume": 1000} for i, x in enumerate(CAL)],
    "1101": [{"date": x, "close": 10.0, "volume": 1000} for x in CAL[-5:]],          # 序列不足
    "1102": [{"date": "2025-12-01", "close": 30.0, "volume": 1000}],                  # 參考價過期
}}
EVENTS = {"events": [
    {"code": "2330", "date": "2026-01-29", "type": "重大訂單", "title": "接大單", "source": "TWSE 重大訊息", "url": "u1"},
    {"code": "2330", "date": "2026-01-10", "type": "重大訂單", "title": "舊事件", "source": "TWSE 重大訊息", "url": "u2"},
    {"code": "2330", "date": "2026-02-05", "type": "重大訂單", "title": "未來日期", "source": "TWSE 重大訊息", "url": "u3"},
    {"code": "2330", "date": "2026-01-29", "type": "除權息", "title": "非白名單類型", "source": "TWSE 重大訊息", "url": "u4"},
    {"code": "2330", "date": "2026-01-29", "type": "重大訂單", "title": "非白名單來源", "source": "TWSE 除權息", "url": "u5"},
    {"code": "1101", "date": "2026-01-28", "type": "併購", "title": "併購案", "source": "TPEx 重大訊息", "url": "u6"},
]}
NEWS = {"news": [
    {"title": "A 報導", "url": "n1", "published": "Thu, 29 Jan 2026 08:00:00 +0800", "source": "經濟日報焦點", "codes": ["1102"]},
    {"title": "B 報導", "url": "n2", "published": "Thu, 29 Jan 2026 09:00:00 +0800", "source": "經濟日報產業", "codes": ["1102"]},
    {"title": "C 報導", "url": "n3", "published": "Thu, 29 Jan 2026 10:00:00 +0800", "source": "鉅亨", "codes": ["2345"]},
    {"title": "D 報導", "url": "n4", "published": "Thu, 29 Jan 2026 11:00:00 +0800", "source": "工商", "codes": ["2345"]},
    {"title": "日期壞", "url": "n5", "published": "not a date", "source": "工商", "codes": ["2345"]},
]}
OLD_SIG = {"id": "keepme", "recorded_at": "2026-01-02T17:13:00+08:00", "code": "9999", "status": "訊號",
           "entry_close": 1.0, "entry_date": "2026-01-05", "returns": {"t5": {"return_pct": 1.0}, "t20": None, "t60": None}}


def setup(base: Path, ledger=None, ledger_raw=None, ph_raw=None):
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "events.json").write_text(json.dumps(EVENTS, ensure_ascii=False), encoding="utf-8")
    (data / "news.json").write_text(json.dumps(NEWS, ensure_ascii=False), encoding="utf-8")
    (data / "price_history.json").write_text(ph_raw if ph_raw is not None else json.dumps(PH), encoding="utf-8")
    lp = data / "signal_ledger.json"
    if ledger_raw is not None:
        lp.write_text(ledger_raw, encoding="utf-8")
    elif ledger is not None:
        lp.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    elif lp.exists():
        lp.unlink()
    B.LEDGER_PATH, B.EVENTS_PATH, B.NEWS_PATH, B.PRICE_HISTORY_PATH = lp, data / "events.json", data / "news.json", data / "price_history.json"
    return lp


def run():
    try:
        B.main()
        return 0, None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("[1] 既有台帳＋新事件")
    lp = setup(base, ledger={"meta": {"created_at": "2026-01-01"}, "signals": [dict(OLD_SIG)]})
    code, err = run()
    check("正常執行不拋例外", err is None and code == 0, (code, err))
    doc = json.loads(lp.read_text(encoding="utf-8"))
    sigs = doc["signals"]
    titles = [s.get("title") for s in sigs]
    check("既有訊號位元組不變、仍在第一筆", json.dumps(sigs[0], sort_keys=True) == json.dumps(OLD_SIG, sort_keys=True))
    check("新鮮度窗內 L1 收進來", "接大單" in titles and "併購案" in titles, titles)
    check("窗外舊事件不補建", "舊事件" not in titles)
    check("未來日期事件不收", "未來日期" not in titles)
    check("非白名單類型／來源不收", "非白名單類型" not in titles and "非白名單來源" not in titles)
    check("published 壞掉的新聞不收", "日期壞" not in titles)
    new = [s for s in sigs if s["id"] != "keepme"]
    check("新訊號 entry 與 returns 全 null", all(s["entry_close"] is None and s["entry_date"] is None
                                              and s["returns"] == {"t5": None, "t20": None, "t60": None} for s in new))
    check("recorded_at＝固定的今天", all(s["recorded_at"] == NOW.isoformat() for s in new))
    by = {s["title"]: s for s in new}
    check("L1 直接升「訊號」", by["接大單"]["status"] == "訊號")
    check("經濟日報兩個 RSS 只算一家 → 待驗證線索", by["A 報導"]["status"] == "待驗證線索"
          and by["A 報導"]["cross_validation"]["independent_l3_sources"] == ["經濟日報"], by["A 報導"]["cross_validation"])
    check("兩家獨立媒體 → 升「訊號」", by["C 報導"]["status"] == "訊號", by["C 報導"]["cross_validation"])
    check("價格序列不足 → reflected=unknown", by["併購案"]["reflected"] == "unknown", by["併購案"].get("reason"))
    check("參考價過期 >10 天 → 記 null", by["A 報導"]["ref_close"] is None and by["A 報導"]["ref_close_date"] is None)
    check("有價 → 參考價＝今天以前最新收盤", by["接大單"]["ref_close_date"] == CAL[-1], by["接大單"]["ref_close_date"])
    check("meta.created_at 不改、total_signals 正確", doc["meta"]["created_at"] == "2026-01-01"
          and doc["meta"]["total_signals"] == len(sigs))

    print("[2] 重跑冪等")
    snap = json.dumps(doc["signals"], sort_keys=True)
    code, err = run()
    doc2 = json.loads(lp.read_text(encoding="utf-8"))
    check("重跑不新增、所有訊號位元組不變", err is None and json.dumps(doc2["signals"], sort_keys=True) == snap)

    print("[3] 台帳不存在（新環境）→ 建新檔")
    lp = setup(base)
    code, err = run()
    check("新建台帳", err is None and code == 0 and lp.exists()
          and len(json.loads(lp.read_text(encoding="utf-8"))["signals"]) == len(new), (code, err))

    print("[4] 台帳讀不出來／結構不對 → 不覆寫歷史")
    for label, raw in (("JSON 損壞", '{"signals": [ broken'), ("不是物件", "[1, 2]"), ("signals 不是陣列", '{"signals": {}}')):
        lp = setup(base, ledger_raw=raw)
        code, err = run()
        check(f"{label}：不拋未處理例外、非零結束、檔案不變", err is None and code not in (0, None)
              and lp.read_text(encoding="utf-8") == raw, (code, err))

    print("[5] price_history 讀不出來")
    B.PHS.time.sleep = lambda s: None  # 略過 _read 的重試等待（只影響本行程）
    lp = setup(base, ledger={"meta": {}, "signals": [dict(OLD_SIG)]}, ph_raw="{broken")
    raw = lp.read_bytes()
    code, err = run()
    check("價格檔損壞：不拋未處理例外、非零結束、台帳不變", err is None and code not in (0, None)
          and lp.read_bytes() == raw, (code, err))

print(f"\n合計 {ok} 過 / {fail} 失敗")
sys.exit(1 if fail else 0)
