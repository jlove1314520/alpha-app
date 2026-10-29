"""自測：research/forward_source_gap_watch.py（先.一三五-1ae）。

合成目錄情境：正常、缺一期、日曆壞檔、目錄不存在、融資／借券累積檔（先.一三五-1ba） → 都要 exit 0、只降級警告（CLAUDE.md 十二節）。
零外部請求，只寫暫存目錄。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "research" / "forward_source_gap_watch.py"
NOW = "2026-10-28T22:00:00"  # 週三晚上：今天算到期
CAL = {"tw": {"2026": {"closed": ["2026-10-09", "2026-10-10", "2026-10-26"], "unscheduled_closed": ["2026-10-23"]}}}
TRADING = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-27", "2026-10-28"]

ok = fail = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def make(root: Path, *, skip_warrant: str | None = None, skip_tdcc_week: bool = False,
         calendar: str | None = "good", with_dirs: bool = True) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "research" / "data").mkdir(parents=True, exist_ok=True)
    if calendar == "good":
        (root / "data" / "trading_calendar.json").write_text(json.dumps(CAL), encoding="utf-8")
    elif calendar == "bad":
        (root / "data" / "trading_calendar.json").write_text("{壞掉", encoding="utf-8")
    if not with_dirs:
        return
    t = root / "research" / "data" / "tdcc"
    t.mkdir()
    for d in ["20261008", "20261016", "20261022"]:
        if skip_tdcc_week and d == "20261016":
            continue
        (t / f"{d}.csv").write_text("x", encoding="utf-8")
    w = root / "research" / "data" / "warrant_snapshots"
    for d in TRADING:
        if d == skip_warrant or d == "2026-10-23":  # 10/23 臨時休市：合成資料沒有這天的快照
            continue
        (w / d).mkdir(parents=True)
        (w / d / "meta.json").write_text("{}", encoding="utf-8")
    (w / "_raw").mkdir()
    lim = root / "research" / "data" / "tpex_limit_next"
    lim.mkdir()
    for d in TRADING:
        (lim / f"{d}.json").write_text("{}", encoding="utf-8")
    with (root / "research" / "data" / "mops_events_archive.jsonl").open("w", encoding="utf-8") as f:
        for d in TRADING[:-1]:
            f.write(json.dumps({"date": d, "title": "t"}) + "\n")
        f.write("壞行\n")
    (root / "research" / "data" / "warrant_snapshot_cycle.log").write_text(
        "===== warrant_snapshot launcher: 2026-10-21 17:30:00 =====\n"
        "[17:37:14] warrant_snapshot.py exit=1 tpex_basic\n[17:37:14] stderr: ChunkedEncodingError\n",
        encoding="utf-8")


def run(root: Path) -> tuple[int, dict | None, str]:
    p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--now", NOW],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    f = root / "research" / "data" / "forward_source_gap_watch.json"
    doc = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return p.returncode, doc, p.stdout + p.stderr


with tempfile.TemporaryDirectory() as td:
    print("情境一：正常")
    r = Path(td) / "a"
    make(r)
    rc, doc, out = run(r)
    check("exit 0", rc == 0, out)
    s = doc["sources"]
    check("warrant OK、10/26 休市不算缺", s["warrant"]["status"] == "OK", s["warrant"])
    check("tdcc OK", s["tdcc"]["status"] == "OK", s["tdcc"])
    check("tpex_limit_next OK", s["tpex_limit_next"]["status"] == "OK", s["tpex_limit_next"])
    check("mops OK、壞行計數 1", s["mops_events"]["status"] == "OK" and s["mops_events"]["bad_lines"] == 1, s["mops_events"])
    check("停資停券目錄不存在 → NOT_STARTED", s["margin_suspension"]["status"] == "NOT_STARTED")
    check("融資／借券累積檔不存在 → 四源 NOT_STARTED",
          all(s[k]["status"] == "NOT_STARTED" for k in ("margin_twse", "margin_tpex", "sbl_twse", "sbl_tpex")))
    check("overall OK", doc["overall"] == "OK", doc["overall"])
    check("臨時休市 10/23（unscheduled_closed）沒快照不算缺", "2026-10-23" not in s["warrant"].get("missing", []), s["warrant"])

    print("情境二：權證缺 10/21、TDCC 缺一週")
    r = Path(td) / "b"
    make(r, skip_warrant="2026-10-21", skip_tdcc_week=True)
    rc, doc, out = run(r)
    s = doc["sources"]
    check("exit 0", rc == 0, out)
    check("warrant GAP 缺 10/21", s["warrant"]["status"] == "GAP" and s["warrant"]["missing"] == ["2026-10-21"], s["warrant"])
    check("缺期附 stderr 原因", "ChunkedEncodingError" in s["warrant"]["reasons"]["2026-10-21"], s["warrant"].get("reasons"))
    check("tdcc GAP 缺 10/12 當週", s["tdcc"]["missing"] == ["2026-10-12 當週"], s["tdcc"])
    check("overall GAP", doc["overall"] == "GAP")

    print("情境三：日曆壞檔 → 只排除週末")
    r = Path(td) / "c"
    make(r, calendar="bad")
    rc, doc, out = run(r)
    check("exit 0", rc == 0, out)
    check("降級警告", "交易日曆讀不到" in out, out)
    check("calendar 標只排除週末", doc["calendar"].startswith("只排除週末"), doc["calendar"])
    check("10/26 被當交易日 → warrant 缺 10/26", "2026-10-26" in doc["sources"]["warrant"]["missing"], doc["sources"]["warrant"])

    print("情境四：目錄全不存在、日曆也沒有")
    r = Path(td) / "d"
    make(r, calendar=None, with_dirs=False)
    rc, doc, out = run(r)
    check("exit 0", rc == 0, out)
    check("全部 NOT_STARTED、不崩", doc and all(v["status"] == "NOT_STARTED" for v in doc["sources"].values()), doc)

    print("情境六（先.一三五-1ba）：融資 data_dates／借券 series 鍵；借券上櫃缺 10/22")
    r = Path(td) / "f"
    make(r)
    (r / "data" / "margin_by_stock_history.json").write_text(json.dumps({
        "dates": ["20261024", "20261028"],  # 執行日鍵（含週六）不看
        "data_dates": {"20261023": {"twse": "20261022", "tpex": None}, "20261028": {"twse": "20261027", "tpex": "20261027"},
                       "20261024": "壞值"},
        "series": {"1101": {"20261024": [1, 2, 3]}}}), encoding="utf-8")
    (r / "data" / "securities_lending_sell_history.json").write_text(json.dumps({
        "series_twse": {"2330": {"20261021": [1], "20261022": [1]}, "2317": {"20261027": [1]}},
        "series_tpex": {"6488": {"20261021": [1], "20261027": [1]}}}), encoding="utf-8")
    rc, doc, out = run(r)
    s = doc["sources"]
    check("exit 0", rc == 0, out)
    check("margin_twse OK（起算 10/22，到期 10/27；10/23 臨時休市、10/26 休市不算）", s["margin_twse"]["status"] == "OK", s["margin_twse"])
    check("margin_tpex 起算 10/27 → OK（data_dates 之前不算缺）", s["margin_tpex"]["status"] == "OK", s["margin_tpex"])
    check("sbl_twse 跨代號合併 → OK", s["sbl_twse"]["status"] == "OK", s["sbl_twse"])
    check("sbl_tpex GAP 缺 10/22", s["sbl_tpex"]["status"] == "GAP" and s["sbl_tpex"]["missing"] == ["2026-10-22"], s["sbl_tpex"])
    check("今天 10/28 不算到期", s["sbl_twse"]["due_through"] == "2026-10-27", s["sbl_twse"])

    print("情境七：借券檔壞 JSON → 只有 sbl 兩源 ERROR、其他照跑")
    (r / "data" / "securities_lending_sell_history.json").write_text("{壞", encoding="utf-8")
    rc, doc, out = run(r)
    s = doc["sources"]
    check("exit 0", rc == 0, out)
    check("sbl_twse／sbl_tpex ERROR", s["sbl_twse"]["status"] == "ERROR" and s["sbl_tpex"]["status"] == "ERROR", s["sbl_twse"])
    check("margin_twse 仍 OK", s["margin_twse"]["status"] == "OK", s["margin_twse"])

    print("情境五：--root 指到不能寫的位置（看守員自身失敗）→ 仍 exit 0")
    bad = Path(td) / "e"
    bad.write_text("我是檔案不是目錄", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), "--root", str(bad), "--now", NOW],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("exit 0＋自身失敗警告", p.returncode == 0 and "看守員自身失敗" in p.stdout, p.stdout + p.stderr)

print(f"\n結果：{ok} 過／{fail} 失敗")
sys.exit(1 if fail else 0)
