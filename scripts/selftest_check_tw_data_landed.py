"""自測：台股當日資料落地檢查 `scripts/check_tw_data_landed.py`（先.一三五-1cw）。

`ROOT`／`ALARM_PATH`／`RUN_LOG_PATH` 換成暫存目錄、`--now` 固定時間、只跑 `--layer cloud`
（本機層會 git fetch／commit／gh workflow run，不在自測裡碰）：零外部請求、不動真實 data/。
確認：休市日（closed／unscheduled_closed／週末）不告警、20:30 前不告警、data_date 是今天不告警、不是今天才告警（exit 1＋寫告警檔）、
同一告警不重寫、資料進來後告警改成解除、日曆讀不到照週一～五、日曆未公布附註、輸入讀不到／損壞不拋未處理例外。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_tw_data_landed", ROOT / "scripts" / "check_tw_data_landed.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


CAL = {"tw": {"2026": {"published": True, "closed": ["2026-10-26"], "unscheduled_closed": ["2026-10-27"]}}}


def setup(root: Path, data_date="2026-10-29", cal=CAL, market_raw=None) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir(parents=True, exist_ok=True)
    mp = root / "data" / "market_tw.json"
    if market_raw is not None:
        mp.write_text(market_raw, encoding="utf-8")
    elif data_date is not False:
        mp.write_text(json.dumps({"data_date": data_date}), encoding="utf-8")
    elif mp.exists():
        mp.unlink()
    cp = root / "data" / "trading_calendar.json"
    if cal is None:
        if cp.exists():
            cp.unlink()
    else:
        cp.write_text(cal if isinstance(cal, str) else json.dumps(cal), encoding="utf-8")


def run(root: Path, now: str):
    B.ROOT = root
    B.ALARM_PATH = root / "data" / "tw_data_alarm.json"
    B.RUN_LOG_PATH = root / "research" / "tw_data_check.jsonl"
    B.CAL_NOTE["note"] = ""
    try:
        return B.main(["--layer", "cloud", "--now", now]), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def alarm(root: Path):
    p = root / "data" / "tw_data_alarm.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    def case(title, now, expect_rc, expect_alarm_file, **kw):
        r = base / title
        setup(r, **kw)
        rc, err = run(r, now)
        check(f"{title}：沒有未處理例外", err is None, repr(err))
        check(f"{title}：exit {expect_rc}", rc == expect_rc, rc)
        a = alarm(r)
        if expect_alarm_file:
            check(f"{title}：寫告警檔 alarm=true", a and a.get("alarm") is True and a.get("date") == now[:10], a)
        else:
            check(f"{title}：不寫告警檔", a is None, a)
        check(f"{title}：雲端層不寫執行紀錄", not (r / "research" / "tw_data_check.jsonl").exists())
        return r, a

    print("情境一：各種不告警")
    case("資料是今天", "2026-10-29T20:31:00+08:00", 0, False)
    case("20點29 還沒到", "2026-10-29T20:29:00+08:00", 0, False, data_date="2026-10-28")
    case("官方休市日", "2026-10-26T21:00:00+08:00", 0, False, data_date="2026-10-23")
    case("臨時休市日", "2026-10-27T21:00:00+08:00", 0, False, data_date="2026-10-23")
    case("週六", "2026-10-31T21:00:00+08:00", 0, False, data_date="2026-10-30")

    print("情境二：交易日 20:30 後資料不是今天 → 告警")
    r, a = case("資料停在昨天", "2026-10-29T20:31:00+08:00", 1, True, data_date="2026-10-28")
    check("告警訊息與 data_date", a and a["message"] == B.MESSAGE and a["market_tw_data_date"] == "2026-10-28", a)
    check("已公布日曆不附『尚未公布』註記", a and "尚未公布" not in a["reason"], a and a["reason"])
    ap = r / "data" / "tw_data_alarm.json"
    old_t = time.time() - 3600
    os.utime(ap, (old_t, old_t))
    rc, _ = run(r, "2026-10-29T20:45:00+08:00")
    check("同一告警再跑：仍 exit 1、不重寫", rc == 1 and abs(ap.stat().st_mtime - old_t) < 1, (rc, ap.stat().st_mtime - old_t))
    setup(r, data_date="2026-10-29")
    rc, err = run(r, "2026-10-29T21:10:00+08:00")
    a2 = alarm(r)
    check("資料進來後：exit 0、告警改成解除", err is None and rc == 0 and a2 and a2["alarm"] is False and a2["message"] == "", (rc, a2))
    setup(r, data_date="2026-10-29")
    os.utime(ap, (old_t, old_t))
    run(r, "2026-10-29T21:20:00+08:00")
    check("解除後再跑：不重寫", abs(ap.stat().st_mtime - old_t) < 1)
    r2, _ = case("資料是 None", "2026-10-29T20:31:00+08:00", 1, True, data_date=None)

    print("情境三：日曆讀不到／損壞／未公布 → 照週一～五")
    case("日曆不存在、平日", "2026-10-26T21:00:00+08:00", 1, True, data_date="2026-10-23", cal=None)
    case("日曆損壞、平日", "2026-10-26T21:00:00+08:00", 1, True, data_date="2026-10-23", cal="{")
    case("日曆不存在、週日", "2026-11-01T21:00:00+08:00", 0, False, data_date="2026-10-30", cal=None)
    _, a3 = case("日曆未公布", "2026-10-29T21:00:00+08:00", 1, True, data_date="2026-10-28",
                 cal={"tw": {"2026": {"published": False, "closed": []}}})
    check("未公布附註寫進告警原因", a3 and "尚未公布" in a3["reason"], a3 and a3["reason"])

    print("情境四：market_tw 讀不到／損壞 → 不拋未處理例外、exit 0")
    case("market_tw 不存在", "2026-10-29T21:00:00+08:00", 0, False, data_date=False)
    case("market_tw 損壞", "2026-10-29T21:00:00+08:00", 0, False, market_raw="{")
    case("market_tw 頂層不是物件", "2026-10-29T21:00:00+08:00", 0, False, market_raw="[1]")

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
