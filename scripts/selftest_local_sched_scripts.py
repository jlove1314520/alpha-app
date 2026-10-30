# -*- coding: utf-8 -*-
"""先.一三五-1ds～1dv：本機排程呼叫、原本沒有自測的四組腳本合成自測（零外部請求、不讀真實價格、不算報酬）。

1ds scripts/snapshot_moea_pit.py      （AlphaMoeaPitSnapshot）
1dt scripts/export_rf_monthly.py＋research/cbc_rf_rate_client.py（AlphaRfMonthly）
1du research/warrant_snapshot_daily.py （AlphaWarrantSnapshot）
1dv scripts/build_weekly_report.py     （AlphaWeeklyReport）

所有輸出路徑都換成暫存資料夾；requests／subprocess／時間都換假的。
用法：python scripts/selftest_local_sched_scripts.py   （全過 exit 0，任一失敗 exit 1）
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "research"))
TPE = timezone(timedelta(hours=8))
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Resp:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# ───────────────────────── 1ds 經濟部 PIT 快照 ─────────────────────────
def test_moea(tmp: Path) -> None:
    m = load(REPO / "scripts" / "snapshot_moea_pit.py", "snapshot_moea_pit_t")
    m.OUT = tmp / "moea_pit"
    m.MANIFEST = m.OUT / "manifest.jsonl"
    m.STATUS = tmp / "moea_status.json"
    m.SOURCES = [("A", "存貨率", "a.csv"), ("C", "外銷訂單_電子產品", "c.csv")]
    m.time.sleep = lambda s: None
    csv_a = "﻿資料期,數值\n2026M08,1\n2026M09,2\n".encode("utf-8")
    csv_c = "資料期,金額\n2026M07,10\n".encode("utf-8")
    plan = {"a.csv": Resp(200, csv_a), "c.csv": Resp(200, csv_c)}
    def fake_get(url, **k):
        r = plan[url.rsplit("/", 1)[-1]]
        if isinstance(r, Exception):
            raise r
        return r

    m.requests.get = fake_get

    def files():
        return sorted(p.relative_to(m.OUT).as_posix() for p in m.OUT.rglob("*.csv"))

    def manifest_lines():
        return m.MANIFEST.read_text(encoding="utf-8").splitlines() if m.MANIFEST.exists() else []

    rc = m.main()
    st = json.loads(m.STATUS.read_text(encoding="utf-8"))
    res = {r["name"]: r["result"] for r in st["results"]}
    check("1ds 首次：兩檔都存 baseline、manifest 2 行", rc == 0 and res == {"存貨率": "baseline", "外銷訂單_電子產品": "baseline"}
          and len(files()) == 2 and len(manifest_lines()) == 2, f"{res} {files()}")
    rec = json.loads(manifest_lines()[0])
    check("1ds manifest 記錄期間範圍與 baseline 旗標", rec["first_period"] == "2026M08" and rec["last_period"] == "2026M09"
          and rec["rows"] == 2 and rec["baseline"] is True, str(rec))

    m.main()
    res = {r["name"]: r["result"] for r in json.loads(m.STATUS.read_text(encoding="utf-8"))["results"]}
    check("1ds 內容雜湊相同：不新增快照、manifest 不變", set(res.values()) == {"unchanged"} and len(files()) == 2
          and len(manifest_lines()) == 2, f"{res}")

    before = {p: (m.OUT / p).read_bytes() for p in files()}
    plan["a.csv"] = Resp(200, csv_a + "2026M10,3\n".encode("utf-8"))
    plan["c.csv"] = Resp(500)
    m.main()
    res = {r["name"]: r["result"] for r in json.loads(m.STATUS.read_text(encoding="utf-8"))["results"]}
    still = all((m.OUT / p).read_bytes() == b for p, b in before.items())
    check("1ds 一檔更新、另一檔 HTTP 500：只新增更新那檔，舊快照全保留", res == {"存貨率": "new_snapshot", "外銷訂單_電子產品": "http_500"}
          and len(files()) == 3 and still and len(manifest_lines()) == 3, f"{res} {files()}")

    plan["a.csv"] = Resp(200, b"<html><body>maintenance</body></html>")
    plan["c.csv"] = Resp(200, "資料期,x\n".encode("big5") + "\xa4\xa4".encode("latin-1") + b"\xff\xfe")
    m.main()
    res = {r["name"]: r["result"] for r in json.loads(m.STATUS.read_text(encoding="utf-8"))["results"]}
    check("1ds 回 HTML 判格式變更、非 UTF-8 判錯誤，不寫檔", res["存貨率"] == "not_csv_or_changed_format"
          and res["外銷訂單_電子產品"].startswith("error:") and len(files()) == 3, f"{res}")

    plan["a.csv"] = ConnectionError("down")
    plan["c.csv"] = TimeoutError("slow")
    rc = m.main()
    res = {r["name"]: r["result"] for r in json.loads(m.STATUS.read_text(encoding="utf-8"))["results"]}
    check("1ds 全失敗：仍 exit 0、既有快照與 manifest 不動", rc == 0 and all(v.startswith("error:") for v in res.values())
          and len(files()) == 3 and len(manifest_lines()) == 3, f"rc={rc} {res}")


# ───────────────────────── 1dt 無風險利率月檔 ─────────────────────────
def test_rf(tmp: Path) -> None:
    import cbc_rf_rate_client as cbc
    exp = load(REPO / "scripts" / "export_rf_monthly.py", "export_rf_monthly_t")
    cbc.CACHE_PATH = tmp / "rf_cache.parquet"
    exp.OUT = tmp / "rf_monthly.json"
    old_doc = '{"old": true}\n'
    exp.OUT.write_text(old_doc, encoding="utf-8")

    def make_csv(months: int, bad_col=False) -> bytes:
        col = "定存利率-一個月-機動" if bad_col else cbc.RATE_COL
        lines = [f"年月,銀行,{col}"]
        for i in range(months):
            y, mo = 114 + (i // 12), 1 + i % 12
            ym = f"{y}{mo:02d}"
            lines.append(f"{ym},第一銀行,{1.0 + i / 100:.2f}")
            lines.append(f"{ym},臺灣銀行,{1.2 + i / 100:.2f}" if i != 3 else f"{ym},臺灣銀行,-")
        return ("﻿" + "\n".join(lines) + "\n").encode("utf-8")

    state = {"resp": Resp(200, make_csv(14))}

    class FakeSession:
        def mount(self, *a, **k):
            pass

        def get(self, url, **k):
            r = state["resp"]
            if isinstance(r, Exception):
                raise r
            return r

    cbc.requests.Session = FakeSession

    rc = exp.main()
    doc = json.loads(exp.OUT.read_text(encoding="utf-8"))
    by = {r["date"]: r["rf_rate_pct"] for r in doc["monthly"]}
    check("1dt 正常：14 個月寫出、最新月 2026-02（民國 11502）", rc == 0 and doc["n"] == 14 and doc["last_month"] == "2026-02",
          f"rc={rc} n={doc.get('n')} last={doc.get('last_month')}")
    check("1dt 月平均＝兩家算術平均；缺值銀行忽略不當 0", abs(by["2025-01-01"] - 1.1) < 1e-9 and abs(by["2025-04-01"] - 1.03) < 1e-9,
          f"{by.get('2025-01-01')} {by.get('2025-04-01')}")
    check("1dt 寫檔後沒有 .tmp 殘留", not list(tmp.glob("*.tmp")), str(list(tmp.glob("*.tmp"))))

    good = exp.OUT.read_text(encoding="utf-8")
    state["resp"] = Resp(200, make_csv(5))
    rc = exp.main()
    check("1dt 筆數 <12：exit 1、不覆蓋舊檔", rc == 1 and exp.OUT.read_text(encoding="utf-8") == good, f"rc={rc}")

    for label, resp in (("HTTP 503", Resp(503)), ("連線失敗", ConnectionError("x")), ("欄位改名", Resp(200, make_csv(14, bad_col=True)))):
        state["resp"] = resp
        raised = False
        try:
            exp.main()
        except Exception:
            raised = True
        check(f"1dt {label}：中止（非 0）、不覆蓋舊檔、無 .tmp", raised and exp.OUT.read_text(encoding="utf-8") == good
              and not list(tmp.glob("*.tmp")))


# ───────────────────────── 1du 權證每日排程本體 ─────────────────────────
def test_warrant(tmp: Path) -> None:
    w = load(REPO / "research" / "warrant_snapshot_daily.py", "warrant_snapshot_daily_t")
    w.SNAP_ROOT = tmp / "snaps"
    w.BACKUP_DIR = tmp / "backup"
    w.MANIFEST = w.BACKUP_DIR / "backup_manifest.json"
    w.STATUS = tmp / "warrant_backup_status.json"
    w.CAL = tmp / "trading_calendar.json"
    w.CAL.write_text(json.dumps({"tw": {"2026": {"published": True, "closed": ["2026-10-09"],
                                                 "unscheduled_closed": ["2026-07-24"]}}}), encoding="utf-8")
    d = lambda s: datetime.fromisoformat(s + "T17:30:00+08:00")  # noqa: E731
    check("1du 週末不是交易日", w.is_trading_day(d("2026-10-31"))[0] is False)
    check("1du 行事曆休市日不是交易日", w.is_trading_day(d("2026-10-09"))[0] is False)
    check("1du 臨時休市（unscheduled_closed）不是交易日", w.is_trading_day(d("2026-07-24"))[0] is False)
    check("1du 平日交易日", w.is_trading_day(d("2026-10-30"))[0] is True)
    check("1du 該年行事曆未公布照平日", w.is_trading_day(d("2027-01-04"))[0] is True)
    w.CAL.write_text("{壞檔", encoding="utf-8")
    check("1du 行事曆壞檔降級照平日（不崩潰）", w.is_trading_day(d("2026-10-30"))[0] is True)
    w.CAL.write_text(json.dumps({"tw": {"2026": {"published": True, "closed": ["2026-10-09"]}}}), encoding="utf-8")

    # main：休市日不呼叫快照
    calls = []
    real_run_snapshot = w.run_snapshot
    w.run_snapshot = lambda day: (calls.append(day), (0, ""))[1]
    w.run_paper_12 = lambda: False

    class FakeDT(datetime):
        fixed = d("2026-10-09")

        @classmethod
        def now(cls, tz=None):
            return cls.fixed

    w.datetime = FakeDT
    argv = sys.argv
    sys.argv = ["x", "--no-commit"]
    try:
        w.main()
        check("1du main 休市日不呼叫快照（零請求）", calls == [], str(calls))
        FakeDT.fixed = d("2026-10-30")
        w.main()
        check("1du main 交易日呼叫一次快照", calls == ["2026-10-30"], str(calls))
    finally:
        sys.argv = argv
    w.run_snapshot = real_run_snapshot

    # run_snapshot：已存在且完整不重跑；partial 才重跑
    sub_calls = []
    w.subprocess.run = lambda *a, **k: (sub_calls.append(a[0]), types.SimpleNamespace(returncode=0, stdout="ok\n", stderr=""))[1]
    day_dir = w.SNAP_ROOT / "2026-10-28"
    day_dir.mkdir(parents=True)
    (day_dir / "meta.json").write_text(json.dumps({"partial": False}), encoding="utf-8")
    (day_dir / "a.json").write_text("[1,2,3]", encoding="utf-8")
    rc, _ = w.run_snapshot("2026-10-28")
    check("1du 快照已存在且完整：不重跑", rc == 0 and sub_calls == [])
    (day_dir / "meta.json").write_text(json.dumps({"partial": True}), encoding="utf-8")
    rc, _ = w.run_snapshot("2026-10-28")
    check("1du 快照只有部分來源：重跑一次", rc == 0 and len(sub_calls) == 1)
    (day_dir / "meta.json").write_text(json.dumps({"partial": False}), encoding="utf-8")

    # weekly_backup
    d2 = w.SNAP_ROOT / "2026-10-29"
    d2.mkdir()
    (d2 / "meta.json").write_text("{}", encoding="utf-8")
    FakeDT.fixed = d("2026-10-30")
    man = w.weekly_backup(False)
    zips = list(w.BACKUP_DIR.glob("*.zip"))
    ok_zip = len(zips) == 1 and zipfile.ZipFile(zips[0]).testzip() is None
    check("1du 從未備份：壓成一個 zip、testzip 通過、清單記兩天", ok_zip and man["backed_up_days"] == ["2026-10-28", "2026-10-29"],
          f"{zips} {man.get('backed_up_days')}")
    d3 = w.SNAP_ROOT / "2026-10-30"
    d3.mkdir()
    (d3 / "meta.json").write_text("{}", encoding="utf-8")
    FakeDT.fixed = d("2026-11-02")
    man = w.weekly_backup(False)
    check("1du 距上次備份未滿 7 天：不備份", len(list(w.BACKUP_DIR.glob("*.zip"))) == 1 and "2026-10-30" not in man["backed_up_days"])

    real_testzip = zipfile.ZipFile.testzip
    zipfile.ZipFile.testzip = lambda self: "2026-10-30/meta.json"
    try:
        man = w.weekly_backup(True)
    finally:
        zipfile.ZipFile.testzip = real_testzip
    check("1du zip 驗不過：刪掉該 zip、清單不記", len(list(w.BACKUP_DIR.glob("*.zip"))) == 1 and "2026-10-30" not in man["backed_up_days"],
          str(list(w.BACKUP_DIR.glob("*.zip"))))
    man = w.weekly_backup(True)
    check("1du 強制備份：只補未備份的那天", len(list(w.BACKUP_DIR.glob("*.zip"))) == 2 and man["backups"][-1]["days"] == ["2026-10-30"])

    # write_status
    changed1 = w.write_status(man)
    changed2 = w.write_status(man)
    st = json.loads(w.STATUS.read_text(encoding="utf-8"))
    check("1du 狀態檔：第一次寫、內容沒變第二次不寫", changed1 is True and changed2 is False and st["last_snapshot_date"] == "2026-10-30"
          and st["snapshot_days"] == 3, f"{changed1} {changed2} {st.get('last_snapshot_date')}")
    w.write_status(man, {"date": "2026-10-30", "exit": 2, "reason": "x", "at": "t"})
    w.write_status(man)
    st = json.loads(w.STATUS.read_text(encoding="utf-8"))
    check("1du 失敗紀錄寫入後，下次無失敗時沿用（設定頁看得到漏抓）", (st.get("last_failure") or {}).get("exit") == 2)


# ───────────────────────── 1dv 系統週報 ─────────────────────────
def test_weekly(tmp: Path) -> None:
    root = tmp / "wk"
    (root / "data").mkdir(parents=True)
    (root / "research").mkdir()
    now = datetime(2026, 11, 1, 20, 0, tzinfo=TPE)
    iso = lambda dt: dt.isoformat(timespec="seconds")  # noqa: E731
    wj = lambda p, o: (root / p).write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")  # noqa: E731
    wj("data/audit_report.json", {"generated_at": iso(now - timedelta(hours=3)), "gate_pass": True,
                                  "self_check": {"ok": True, "checks": [{"label": "a", "ok": True}]},
                                  "local_task_health": {"stalled": []}})
    for f in ("paper_1b", "paper_3", "paper_7030"):
        wj(f"data/{f}.json", {"as_of_date": "2026-10-30", "total_return_pct": 1.5})
    wj("data/paper_4.json", {"books": {"A": {"as_of_date": "2026-10-30", "total_return_pct": 0.3, "bench_0050_return_pct": 0.2}}})
    wj("data/paper_tracking_watch.json", {"status": "OK", "items": []})
    evs = [{"ts": iso(now - timedelta(days=8)), "task": "run", "code": "ERROR"},
           {"ts": iso(now - timedelta(days=2)), "task": "run", "code": "OK"},
           {"ts": iso(now - timedelta(days=1)), "task": "settle", "code": "NOTHING_TO_SETTLE"}]
    wj("data/auto_heartbeat.json", {"updated_at": iso(now - timedelta(hours=5)), "events": evs})
    (root / "research" / "TRIALS_REGISTRY.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in [
            {"date": "2026-10-20", "name": "舊", "verdict": "FAIL"},
            {"date": "2026-10-26", "name": "`新一`", "verdict": "FAIL（理由）"},
            {"date": "2026-10-31", "name": "新二", "verdict": "PASS"}]) + "\n壞行\n", encoding="utf-8")
    (root / "research" / "PROGRESS_HEARTBEAT.jsonl").write_text(
        json.dumps({"ts": iso(now - timedelta(days=1)), "track": "dev"}) + "\n"
        + json.dumps({"ts": iso(now - timedelta(days=9)), "track": "dev"}) + "\n", encoding="utf-8")

    fake_pf = types.ModuleType("pipeline_freshness")
    fake_pf.evaluate = lambda n: ([{"task": "t1", "artifact": "a", "status": "ok"},
                                   {"task": "t2", "artifact": "b", "status": "stalled", "age_min": 99, "missed_shifts": 2}], [])
    sys.modules["pipeline_freshness"] = fake_pf
    wr = load(REPO / "scripts" / "build_weekly_report.py", "build_weekly_report_t")
    wr.ROOT = root

    rep = wr.build(now)
    check("1dv 正常：五區塊都在、沒有 error", all(k in rep and "error" not in rep[k] for k, _ in wr.SECTIONS),
          str({k: rep.get(k, {}).get("error") for k, _ in wr.SECTIONS}))
    check("1dv 研究區塊：7 日視窗（since＝10/25）、壞行略過、名稱去反引號", rep["research"]["trials_week"] == 2
          and rep["research"]["trials_total"] == 3 and rep["research"]["trials_week_names"] == ["新一", "新二"]
          and rep["research"]["verdicts_week"] == {"FAIL": 1, "PASS": 1} and rep["research"]["heartbeats_week"] == 1,
          str(rep["research"]))
    lv = rep["live_execution"]
    check("1dv 真錢區塊：只算 7 日內事件，8 天前的 ERROR 不算", lv["events_week"] == 2 and lv["errors_week"] == 0 and lv["level"] == "ok",
          str(lv))
    banned = ("qty", "quantity", "price", "amount", "pnl", "avg", "shares", "金額", "股數", "損益", "均價")
    flat = json.dumps(lv, ensure_ascii=False).lower()
    leaked = [b for b in banned if f'"{b}' in flat]
    check("1dv 真錢區塊沒有金額／股數／損益欄位（公開 repo 去識別化）", not leaked, str(leaked))
    check("1dv 新鮮度：1 條停擺 → warn", rep["freshness"]["level"] == "warn" and len(rep["freshness"]["stalled"]) == 1)

    (root / "data" / "audit_report.json").unlink()
    (root / "data" / "auto_heartbeat.json").write_text("{壞", encoding="utf-8")
    fake_pf.evaluate = lambda n: (_ for _ in ()).throw(RuntimeError("boom"))
    rep = wr.build(now)
    errs = sorted(k for k, _ in wr.SECTIONS if "error" in rep[k])
    check("1dv 三個來源壞掉：只那三區標 error、其餘照常、摘要仍產出", errs == ["freshness", "live_execution", "system_health"]
          and rep["research"]["trials_week"] == 2 and len(rep["summary"]) == 2, f"{errs} {rep['summary']}")

    out = tmp / "weekly_report.json"
    argv = sys.argv
    sys.argv = ["x", "--no-push", "--now", "2026-11-01T20:00:00+08:00", "--out", str(out)]
    try:
        rc = wr.main()
    finally:
        sys.argv = argv
    doc = json.loads(out.read_text(encoding="utf-8"))
    check("1dv main：--out 寫出合法 JSON、無 .tmp 殘留、--no-push 不推播", rc == 0 and doc["week_start"] == "2026-10-25"
          and not out.with_suffix(".json.tmp").exists(), f"rc={rc} {doc.get('week_start')}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for fn, sub in ((test_moea, "moea"), (test_rf, "rf"), (test_warrant, "warrant"), (test_weekly, "weekly")):
            p = tmp / sub
            p.mkdir()
            try:
                fn(p)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} 未預期例外", False, f"{type(e).__name__}: {e}")
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n合計 {len(RESULTS)} 項，失敗 {n_fail} 項")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
