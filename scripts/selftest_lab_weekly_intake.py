# -*- coding: utf-8 -*-
"""先.一三五-1fi 自測：研究室週更新守門員（lab_weekly_intake.main）。

全部用假的：git 換紀錄器（不碰真 repo、不 commit）、subprocess.run 換假 build_research／selftest_research
（把合成 research.json 寫進 RESEARCH_OUT 暫存目錄）、失敗紀錄換暫存；零外部請求。
用法：python scripts/selftest_lab_weekly_intake.py
"""
import contextlib
import copy
import io
import json
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import lab_weekly_intake as L  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


GOOD = {"deep": {
    "scenario": {"base_revenue": 100, "tax": 0.2, "shares": 10,
                 "rows": [{"name": "基本", "growth": 0.1, "gm": 0.5, "opex": 0.2, "eps": 2.64},
                          {"name": "未填", "growth": 0.0, "gm": 0.5, "opex": 0.2, "eps": None}]},
    "guidance": {"records": [{"asof": "2026-10-01", "recorded_at": "2026-10-02"}], "errors": []}}}

state = {}


def fake_git(*args):
    state["git"].append(args)
    if args[0] == "status":
        return types.SimpleNamespace(stdout=state["porcelain"], stderr="", returncode=0)
    return types.SimpleNamespace(stdout="", stderr="", returncode=0)


def fake_run(cmd, cwd=None, env=None, **kw):
    script = Path(cmd[1]).name
    if script == "build_research.py":
        if state["build_rc"] != 0:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="假的 build 失敗")
        (Path(env["RESEARCH_OUT"]) / "research.json").write_text(json.dumps({"stocks": state["stocks"]}), encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    return types.SimpleNamespace(returncode=0, stdout="全部 PASS\n", stderr="")


L.git = fake_git
L.subprocess = types.SimpleNamespace(run=fake_run)


def commits():
    return [a for a in state["git"] if a[0] == "commit"]


def run(porcelain, stocks, build_rc=0, dry=False):
    state.update(git=[], porcelain=porcelain, stocks=stocks, build_rc=build_rc)
    sys.argv = ["lab_weekly_intake.py"] + (["--dry-run"] if dry else [])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = L.main()
    return rc, buf.getvalue()


def bad(mutate):
    s = copy.deepcopy(GOOD)
    mutate(s["deep"])
    return s


P2330 = " M research/lab/config/2330.json\n?? research/lab/guidance/2330.jsonl\n"
P2317 = " M research/lab/config/2317.json\n"

with tempfile.TemporaryDirectory() as d:
    L.FAIL_LOG = Path(d) / "INTAKE_FAILURES.md"

    rc, out = run("", {})
    check("沒有變動 → 無事 exit 0、不 commit", rc == 0 and not commits() and "無事可做" in out)

    rc, out = run(P2330 + " M research/lab/README.md\n?? research/lab/config/x.txt\n", {"2330": GOOD})
    c = commits()
    check("公式對、PIT 對 → PASS 並 commit 一次", rc == 0 and len(c) == 1 and "2330" in c[0][2])
    check("只 add／commit 該代號的 config＋guidance，不帶其他檔", set(c[0][4:]) == {"research/lab/config/2330.json", "research/lab/guidance/2330.jsonl"})

    def wrong_eps(dd): dd["scenario"]["rows"][0]["eps"] = 3.0
    rc, out = run(P2330, {"2330": bad(wrong_eps)})
    check("情境 EPS 公式不符 → FAIL 不 commit、寫失敗紀錄",
          not commits() and "EPS 公式不符" in out and "2330" in L.FAIL_LOG.read_text(encoding="utf-8"))

    def late(dd): dd["guidance"]["records"][0]["asof"] = "2026-10-05"
    rc, out = run(P2330, {"2330": bad(late)})
    check("說法 asof 晚於 recorded_at → FAIL 不 commit", not commits() and "PIT" in out)

    def fmt(dd): dd["guidance"]["errors"].append("第 3 行不是 JSON")
    rc, out = run(P2330, {"2330": bad(fmt)})
    check("說法格式錯 → FAIL 不 commit", not commits() and "說法格式" in out)

    rc, out = run(P2330, {})
    check("build 沒建出該檔 deep → FAIL 不 commit", not commits() and "沒建出 deep" in out)

    rc, out = run(P2330 + P2317, {"2330": GOOD, "2317": GOOD}, build_rc=1)
    check("build_research 執行失敗 → 全部不 commit、exit 0", rc == 0 and not commits() and out.count("FAIL ") == 2)

    before = L.FAIL_LOG.read_text(encoding="utf-8")
    rc, out = run(P2330 + P2317, {"2330": GOOD, "2317": bad(wrong_eps)}, dry=True)
    check("--dry-run → 不 commit、不寫失敗紀錄", not commits() and L.FAIL_LOG.read_text(encoding="utf-8") == before
          and "PASS 2330（--dry-run" in out and "FAIL 2317" in out)

    def missing(dd): del dd["scenario"]["rows"][0]["growth"]
    rc, out = run(P2330 + P2317, {"2330": GOOD, "2317": bad(missing)})
    c = commits()
    check("一檔缺欄位 → 只判該檔 FAIL，另一檔照常 commit",
          rc == 0 and len(c) == 1 and "2330" in c[0][2] and "FAIL 2317" in out and "檢查時出錯" in out)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(1 if False in results else 0)
