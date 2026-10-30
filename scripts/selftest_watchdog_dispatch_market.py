"""自測：雲端補救觸發判斷 `scripts/watchdog_dispatch_market.py`（先.一三五-1cz）。

`ROOT` 換暫存目錄、`datetime.now` 固定、`subprocess.run` 換假的（不呼叫 gh、零外部請求）。
確認：17:45 前／非交易日（週末、休市、臨時休市、今天疑似臨時休市）／已落地／有進行中 run／今天已觸發過 → 不觸發；
全成立才觸發；日曆讀不到照週一～五；market_tw 讀不到／損壞不拋未處理例外；gh 失敗只警告、exit 0。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("watchdog_dispatch_market", ROOT / "scripts" / "watchdog_dispatch_market.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
TW = B.TW

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


NOW = [datetime(2026, 10, 29, 18, 0, tzinfo=TW)]


class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW[0].astimezone(tz) if tz else NOW[0]


B.datetime = FakeDT
CAL = {"tw": {"2026": {"closed": ["2026-10-26"], "unscheduled_closed": ["2026-10-27"]}}}


def setup(root: Path, cal=CAL, market=None) -> None:
    B.ROOT = root
    (root / "data").mkdir(parents=True, exist_ok=True)
    cp = root / "data" / "trading_calendar.json"
    if cal is None:
        if cp.exists():
            cp.unlink()
    else:
        cp.write_text(cal if isinstance(cal, str) else json.dumps(cal), encoding="utf-8")
    mp = root / "data" / "market_tw.json"
    if market is None:
        if mp.exists():
            mp.unlink()
    else:
        mp.write_text(market if isinstance(market, str) else json.dumps(market), encoding="utf-8")


def dec(now: datetime, data_date, runs=()) -> tuple[bool, str]:
    NOW[0] = now
    return B.decide(now, data_date, list(runs))


def t(day: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, day, h, m, tzinfo=TW)


with tempfile.TemporaryDirectory() as td:
    r = Path(td)
    setup(r)

    print("情境一：decide() 各條件")
    check("17:44 不觸發", dec(t(29, 17, 44), "2026-10-28")[0] is False)
    okk, why = dec(t(29, 17, 45), "2026-10-28")
    check("17:45 交易日未落地、無 run → 觸發", okk is True, why)
    check("23:59 仍會觸發", dec(t(29, 23, 59), "2026-10-28")[0] is True)
    check("週六不觸發", dec(t(31, 18), "2026-10-30")[0] is False)
    check("休市日 10/26 不觸發", dec(t(26, 18), "2026-10-23")[0] is False)
    check("臨時休市 10/27 不觸發", dec(t(27, 18), "2026-10-26")[0] is False)
    check("已落地不觸發", dec(t(29, 18), "2026-10-29")[0] is False)
    check("data_date 是 None → 觸發", dec(t(29, 18), None)[0] is True)
    for st in ("queued", "in_progress", "waiting", "pending", "requested"):
        check(f"有 {st} run 不觸發", dec(t(29, 18), "2026-10-28", [{"status": st, "databaseId": 1}])[0] is False)
    done = {"status": "completed", "event": "schedule", "createdAt": "2026-10-29T09:20:00Z"}
    check("今天只有已完成的排程 run → 觸發", dec(t(29, 18), "2026-10-28", [done])[0] is True)
    today_dispatch = {"status": "completed", "event": "workflow_dispatch", "createdAt": "2026-10-29T09:50:00Z"}
    check("今天已補救觸發過 → 不觸發", dec(t(29, 20), "2026-10-28", [today_dispatch])[0] is False)
    # 台北 10/29 00:00 = UTC 10/28 16:00；邊界前一秒算昨天
    y_dispatch = {"status": "completed", "event": "workflow_dispatch", "createdAt": "2026-10-28T15:59:59Z"}
    check("昨天（台北）的補救觸發不算今天 → 觸發", dec(t(29, 20), "2026-10-28", [y_dispatch])[0] is True)
    b_dispatch = {"status": "completed", "event": "workflow_dispatch", "createdAt": "2026-10-28T16:00:00Z"}
    check("台北 00:00 整的補救觸發算今天 → 不觸發", dec(t(29, 20), "2026-10-28", [b_dispatch])[0] is False)

    print("情境二：今天疑似臨時休市")
    cal2 = {"tw": {"2026": {"closed": [], "suspected_closed_today": {"date": "2026-10-29"}}}}
    setup(r, cal=cal2)
    check("今天疑似休市 → 不觸發", dec(t(29, 18), "2026-10-28")[0] is False)
    cal3 = {"tw": {"2026": {"closed": [], "suspected_closed_today": {"date": "2026-10-29"},
                            "suspected_closed_mismatch": {"date": "2026-10-29"}}}}
    setup(r, cal=cal3)
    check("疑似休市但收盤確認有成交 → 觸發", dec(t(29, 18), "2026-10-28")[0] is True)
    cal4 = {"tw": {"2026": {"closed": [], "suspected_closed_today": {"date": "2026-10-28"}}}}
    setup(r, cal=cal4)
    check("疑似休市是昨天的紀錄 → 今天照觸發", dec(t(29, 18), "2026-10-28")[0] is True)

    print("情境三：日曆讀不到／損壞 → 照週一～五")
    for label, cal in [("不存在", None), ("損壞", "{"), ("頂層陣列", "[1]")]:
        setup(r, cal=cal)
        check(f"日曆{label}、平日 → 觸發", dec(t(26, 18), "2026-10-23")[0] is True)
        check(f"日曆{label}、週日 → 不觸發", dec(t(25, 18), "2026-10-23")[0] is False)

    print("情境四：main() 端到端（假 gh）")
    calls: list[list[str]] = []

    def fake_run_factory(list_rc=0, list_out="[]", run_rc=0, raise_on=None):
        def fake_run(cmd, **kw):
            calls.append(cmd)
            if raise_on and cmd[1] == raise_on:
                raise FileNotFoundError("gh")
            if cmd[1] == "run":
                return SimpleNamespace(returncode=list_rc, stdout=list_out, stderr="boom")
            return SimpleNamespace(returncode=run_rc, stdout="", stderr="denied")
        return fake_run

    def main_at(now, **kw):
        NOW[0] = now
        calls.clear()
        B.subprocess = SimpleNamespace(run=fake_run_factory(**kw))
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = B.main()
            return rc, buf.getvalue(), None
        except Exception as e:  # noqa: BLE001
            return None, buf.getvalue(), e

    setup(r, market={"data_date": "2026-10-28"})
    rc, out, err = main_at(t(29, 18))
    check("未落地 → 送出 gh workflow run market.yml reason=watchdog_tw_catchup",
          rc == 0 and err is None and ["gh", "workflow", "run", "market.yml", "-f", "reason=watchdog_tw_catchup"] in calls, (rc, err, calls))
    rc, out, err = main_at(t(29, 17, 0))
    check("17:45 前連 gh run list 都不呼叫", rc == 0 and calls == [], calls)
    setup(r, market={"data_date": "2026-10-29"})
    rc, out, err = main_at(t(29, 18))
    check("已落地 → 只查 run 清單、不觸發", rc == 0 and len(calls) == 1 and calls[0][1] == "run", calls)
    for label, raw in [("不存在", None), ("損壞", "{"), ("頂層陣列", "[1]"), ("空檔", "")]:
        setup(r, market=raw)
        rc, out, err = main_at(t(29, 18))
        check(f"market_tw {label} → 警告＋照未落地觸發、exit 0",
              rc == 0 and err is None and "market_tw.json 讀取失敗" in out and any(c[1] == "workflow" for c in calls), (rc, err, out))
    setup(r, market={"data_date": "2026-10-28"})
    rc, out, err = main_at(t(29, 18), list_rc=1)
    check("gh run list 失敗 → 警告、不觸發、exit 0", rc == 0 and err is None and "自身失敗" in out
          and not any(c[1] == "workflow" for c in calls), (rc, err, out))
    rc, out, err = main_at(t(29, 18), list_out="not json")
    check("gh run list 回非 JSON → 警告、exit 0", rc == 0 and err is None and "自身失敗" in out, (rc, out))
    rc, out, err = main_at(t(29, 18), raise_on="run")
    check("找不到 gh 執行檔 → 警告、exit 0", rc == 0 and err is None and "自身失敗" in out, (rc, out))
    rc, out, err = main_at(t(29, 18), run_rc=1)
    check("gh workflow run 失敗 → 警告、exit 0", rc == 0 and err is None and "觸發 market.yml 失敗" in out, (rc, out))

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
