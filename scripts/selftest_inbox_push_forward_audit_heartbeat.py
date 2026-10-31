# -*- coding: utf-8 -*-
"""先.一三五-1ev／1ew／1ex（2026-10-31 DevQueue 空轉補件）：三支無自測腳本的合成自測（零請求、不推播、不碰 git、不寫正式檔）。

1ev scripts/inbox_done_push.py：.done 狀態判斷（完成／部分完成／卡住／空檔）、編號找檔、同一份只推一次、
    推播或狀態檔失敗只降級 exit 0（十二節）。
1ew scripts/audit_forward_reserved_reads.py：起跑日常數解析、本檔起跑守門偵測、帳本日期（壞行／缺日期欄）、
    帳本有起跑前日期 → needs_proposal。
1ex scripts/long_job_progress_heartbeat.py：計數（目錄／指令／壞輸出）、--once 寫一列心跳、git 失敗只降級不拋例外。
跑法：python scripts/selftest_inbox_push_forward_audit_heartbeat.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_forward_reserved_reads as AF  # noqa: E402
import inbox_done_push as IP  # noqa: E402
import long_job_progress_heartbeat as HBM  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


# ───────────────────────── 1ev 收件匣推播 ─────────────────────────
def test_inbox(tmp: Path) -> None:
    inbox = tmp / "cowork_inbox"
    inbox.mkdir()
    IP.INBOX = inbox
    IP.STATE = tmp / "state.json"

    def mk(name: str, text: str) -> Path:
        p = inbox / name
        p.write_text(text, encoding="utf-8")
        return p

    d1 = mk("031_test.done", "完成\n" + "摘要" * 30 + "\n第三行\n")
    t, body, kind = IP.build(d1)
    check("1ev 完成→cc_done、摘要截 40 字", kind == "cc_done" and t.startswith("✅ 收件匣 031 完成：") and
          len(t.split("：", 1)[1]) == 40, t)
    t, _, kind = IP.build(mk("032_p.done", "部分完成（2/3）\n還差一項\n"))
    check("1ev 部分完成→cc_done 🟡", kind == "cc_done" and t.startswith("🟡 收件匣 032 部分完成"), t)
    t, _, kind = IP.build(mk("033_s.done", "卡住：等總司令\n缺金鑰\n"))
    check("1ev 卡住→cc_stuck", kind == "cc_stuck" and "卡住：缺金鑰" in t, t)
    t, _, kind = IP.build(mk("034_e.done", "\n\n"))
    check("1ev 空檔→當卡住、不拋例外", kind == "cc_stuck" and "沒有第二行" in t, t)

    check("1ev 編號 31 找到 031_*.done", IP.find_done("31") == d1)
    check("1ev 找不到的編號回 None", IP.find_done("999") is None)
    check("1ev 不是 .done 的路徑回 None", IP.find_done(str(tmp / "x.txt")) is None)

    sent: list[tuple] = []
    fake = types.ModuleType("cc_push")
    fake._send = lambda title, body, kind: sent.append((title, kind)) or "ok"
    sys.modules["cc_push"] = fake
    r1, _ = quiet(IP.main, ["x", str(d1)])
    r2, out2 = quiet(IP.main, ["x", str(d1)])
    check("1ev 同一份只推一次", r1 == 0 and r2 == 0 and len(sent) == 1 and "已推過" in out2, f"sent={len(sent)}")
    os.utime(d1, ns=(d1.stat().st_atime_ns, d1.stat().st_mtime_ns + 10**9))
    quiet(IP.main, ["x", str(d1)])
    check("1ev .done 改寫（修改時間變）會再推", len(sent) == 2, f"sent={len(sent)}")

    IP.STATE.write_text("{壞掉的 json", encoding="utf-8")
    d5 = mk("035_ok.done", "完成\nA\n")
    r, _ = quiet(IP.main, ["x", str(d5)])
    check("1ev 狀態檔壞掉 fail open 照推", r == 0 and len(sent) == 3)

    def boom(*a, **k):
        raise RuntimeError("推播伺服器掛了")
    fake._send = boom
    r, out = quiet(IP.main, ["x", str(mk("036_b.done", "完成\nB\n"))])
    check("1ev 推播丟例外只降級、exit 0", r == 0 and "已降級" in out, out.strip()[:80])
    r, out = quiet(IP.main, ["x"])
    check("1ev 沒給參數印用法、exit 0", r == 0 and "用法" in out)
    del sys.modules["cc_push"]


# ───────────────────── 1ew 前向模擬保留期讀取稽核 ─────────────────────
def test_forward_audit(tmp: Path) -> None:
    check("1ew START_NOT_BEFORE 優先於 START",
          AF.start_const('START = "2026-01-01"\nSTART_NOT_BEFORE = "2027-01-04"\n') == "2027-01-04")
    check("1ew 只有 START 也認", AF.start_const('START = "2026-11-02"\n') == "2026-11-02")
    check("1ew 縮排／非字串的 START 不認", AF.start_const('  START = "2026-11-02"\nSTART = date(2026,1,1)\n') is None)

    guarded = ('START = "2027-01-04"\n'
               'def step(day):\n    if day < START:\n        return "NOT_STARTED"\n    return "OK"\n')
    no_ret = ('START = "2027-01-04"\n'
              'def step(day):\n    if day < START:\n        return "SKIP"\n    return "OK"\n')
    split_fn = ('START = "2027-01-04"\n'
                'def a(day):\n    return day < START\n'
                'def b():\n    return "NOT_STARTED"\n')
    check("1ew 同函式「< START」＋NOT_STARTED → 有守門", AF.own_guard(guarded))
    check("1ew 有比較但不回 NOT_STARTED → 無守門", not AF.own_guard(no_ret))
    check("1ew 比較與 NOT_STARTED 分在兩個函式 → 無守門", not AF.own_guard(split_fn))

    AF.R = tmp / "research"
    (AF.R / "data").mkdir(parents=True)
    check("1ew 帳本不存在", AF.log_dates("99") == {"exists": False, "rows": 0, "min_date": None})
    (AF.R / "data" / "paper_99_log.jsonl").write_text(
        '{"date":"2027-01-05","nav":1}\n\n{壞行\n{"day":"2027-01-04T13:30"}\n{"nav":2}\n', encoding="utf-8")
    lg = AF.log_dates("99")
    check("1ew 帳本壞行計數、day 欄截日期、缺日期欄不算列",
          lg == {"exists": True, "rows": 2, "unparsable": 1, "min_date": "2027-01-04"}, str(lg))

    # 整支 main()：一支有守門且帳本乾淨、一支帳本有起跑前日期
    src_ok = guarded
    src_bad = guarded.replace("2027-01-04", "2027-01-04")
    (AF.R / "validation").mkdir()
    (AF.R / "validation" / "holdout.py").write_text(
        'ALLOWED_HOLDOUT_READERS = frozenset({"x.py"})\n', encoding="utf-8")
    (AF.R / "paper_forward_common.py").write_text("start_not_before NOT_STARTED\n", encoding="utf-8")
    AF.TRACKERS = {"5": "p5.py", "98": "p98.py"}
    (AF.R / "p5.py").write_text(src_ok, encoding="utf-8")
    (AF.R / "p98.py").write_text(src_bad, encoding="utf-8")
    (AF.R / "data" / "paper_98_log.jsonl").write_text('{"date":"2026-12-31"}\n{"date":"2027-01-05"}\n',
                                                      encoding="utf-8")
    r, out = quiet(AF.main)
    doc = json.loads((AF.R / "data" / "forward_holdout_read_audit.json").read_text(encoding="utf-8"))
    check("1ew 帳本乾淨→only_signal_input", doc["trackers"]["paper_5"]["verdict"] == "only_signal_input")
    check("1ew 帳本有起跑前日期→needs_proposal",
          doc["trackers"]["paper_98"]["verdict"] == "needs_proposal" and doc["summary"]["needs_proposal"] == ["98"],
          str(doc["summary"]))
    check("1ew 白名單解析", doc["allowed_holdout_readers"] == ["x.py"] and r == 0)


# ───────────────────────── 1ex 長工作進度心跳 ─────────────────────────
def test_heartbeat(tmp: Path) -> None:
    HBM.ROOT = tmp
    (tmp / "d").mkdir()
    for i in range(3):
        (tmp / "d" / f"{i}.json").write_text("{}", encoding="utf-8")
    ns = types.SimpleNamespace
    check("1ex 目錄計數", HBM._count(ns(dir="d", count_cmd=None)) == 3)
    check("1ex 目錄不存在→0", HBM._count(ns(dir="nope", count_cmd=None)) == 0)
    py = f'"{sys.executable}" -c "print(\'42 files\')"'
    check("1ex 指令計數取第一個數字", HBM._count(ns(dir=None, count_cmd=py)) == 42)
    bad = f'"{sys.executable}" -c "print(\'abc\')"'
    r, out = quiet(HBM._count, ns(dir=None, count_cmd=bad))
    check("1ex 指令輸出壞掉→None＋警告", r is None and "計數失敗" in out)
    empty = f'"{sys.executable}" -c "pass"'
    r, _ = quiet(HBM._count, ns(dir=None, count_cmd=empty))
    check("1ex 指令沒輸出→None 不拋例外", r is None)

    # --once：心跳寫到暫存檔、git 一律失敗，主程式仍 exit 0
    HBM.HB = tmp / "hb.jsonl"
    HBM.LOCK_PY = tmp / "no_such_lock.py"   # 拿鎖必失敗 → 不會去 release

    def git_boom(*a, **k):
        raise OSError("git 不在")
    HBM._git = git_boom
    old_argv = sys.argv
    sys.argv = ["x", "--label", "測試", "--dir", "d", "--total", "3", "--once"]
    try:
        r, out = quiet(HBM.main)
    finally:
        sys.argv = old_argv
    rows = [json.loads(l) for l in HBM.HB.read_text(encoding="utf-8").splitlines() if l.strip()]
    check("1ex --once 寫一列心跳、git 例外只降級", r == 0 and len(rows) == 1 and "已降級" in out, out.strip()[:100])
    check("1ex 心跳內容（3/3、100.0%、已完成）",
          rows and rows[0]["status"] == "RUNNING" and "測試 進度 3/3（100.0%）" in rows[0]["item"]
          and rows[0]["item"].endswith("已完成"), rows[0]["item"] if rows else "")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, fn in (("1ev", test_inbox), ("1ew", test_forward_audit), ("1ex", test_heartbeat)):
            sub = tmp / name
            sub.mkdir()
            try:
                fn(sub)
            except Exception as e:  # noqa: BLE001
                check(f"{name} 測試本身丟例外", False, f"{type(e).__name__}: {e}")
    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"｜{detail}" if detail and not ok else ""))
    print(f"\n合計 {len(RESULTS)} 項：PASS {len(RESULTS) - len(fails)}、FAIL {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
