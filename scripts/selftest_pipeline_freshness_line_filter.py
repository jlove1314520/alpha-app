# -*- coding: utf-8 -*-
"""先.一三五-1kh-p（2026-11-04）自測：停擺自檢多支排程共用一份日誌時，line_filter／line_exclude 逐支取最後時間。

只用暫存檔、零外部請求、不讀真日誌。
1. log_last_timestamp＋line_filter：共用 scheduler.log，09:05／09:40 兩班各自取到自己的最後時間；只停 09:40 那支時抓得到（時間停在前一天）。
2. jsonl_last_field＋line_filter／line_exclude：晚班列帶 layer、早班不帶，各自取到自己的末筆。
3. 沒寫 line_filter 的條目行為不變（取全檔最後時間）。
4. 正規式寫錯只警告、照原文處理，不拋錯（十二節）。
跑法：python scripts/selftest_pipeline_freshness_line_filter.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import pipeline_freshness as P  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    log = td / "scheduler.log"
    # 11/04 09:40 那班沒跑（只停一支），其他照常
    log.write_text("\n".join([
        "[2026-11-03T09:05:00] task=run exit=0", "",
        "[2026-11-03T09:40:01] task=run exit=0", "",
        "[2026-11-04T09:05:00] task=run exit=0", "",
        "[2026-11-04T13:40:00] task=settle exit=0", "",
        "[2026-11-04T14:00:00] task=watchdog-settle exit=0", "",
    ]), encoding="utf-8")
    base = {"freshness": "log_last_timestamp"}
    t0905, _ = P._last_output({**base, "line_filter": r"T09:0\d:\d\d\] task=run\b"}, log)
    t0940, _ = P._last_output({**base, "line_filter": r"T09:[3-5]\d:\d\d\] task=run\b"}, log)
    tset, _ = P._last_output({**base, "line_filter": r"\] task=settle\b"}, log)
    tall, _ = P._last_output(base, log)
    check("1a 09:05 班取到 11/04 09:05", t0905 is not None and t0905.isoformat().startswith("2026-11-04T09:05"), str(t0905))
    check("1b 09:40 班停在 11/03 09:40（只停一支抓得到）", t0940 is not None and t0940.isoformat().startswith("2026-11-03T09:40"), str(t0940))
    check("1c settle 不會被 watchdog-settle 誤配", tset is not None and tset.isoformat().startswith("2026-11-04T13:40"), str(tset))
    check("3 沒寫 line_filter 取全檔最後（14:00）", tall is not None and tall.isoformat().startswith("2026-11-04T14:00"), str(tall))

    jl = td / "catchup.jsonl"
    jl.write_text("\n".join([
        '{"ts": "2026-11-03T17:41:55+08:00", "result": "catchup_ran"}',
        '{"ts": "2026-11-03T19:30:03+08:00", "result": "landed", "layer": "late_1930"}',
        '{"ts": "2026-11-04T17:40:00+08:00", "result": "catchup_ran"}',
    ]) + "\n", encoding="utf-8")
    js = {"freshness": "jsonl_last_field", "field": "ts"}
    early, _ = P._last_output({**js, "line_exclude": '"layer": "late_1930"'}, jl)
    late, _ = P._last_output({**js, "line_filter": '"layer": "late_1930"'}, jl)
    check("2a 早班取 11/04 17:40", early is not None and early.isoformat().startswith("2026-11-04T17:40"), str(early))
    check("2b 晚班停在 11/03 19:30", late is not None and late.isoformat().startswith("2026-11-03T19:30"), str(late))

    bad, how = P._last_output({**base, "task": "X", "line_filter": "([未閉合"}, log)
    check("4 正規式寫錯只警告、照原文處理", bad is not None and bad.isoformat().startswith("2026-11-04T14:00"), f"{bad} {how}")

print("PASS" if not fails else f"FAIL {len(fails)} 項：{fails}")
sys.exit(1 if fails else 0)
