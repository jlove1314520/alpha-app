# -*- coding: utf-8 -*-
"""研究室.六（2026-10-15）：深度研究每週自動更新的接收端。

Cowork 每週日晚上把新的 research/lab/config/<代號>.json、research/lab/guidance/<代號>.jsonl
直接寫進工作目錄。本程式在 commit 前把關：
  1. 用 git status 找出 research/lab/config、research/lab/guidance 底下有變動（含新檔）的代號；
  2. 跑 build_research.py＋selftest_research.py，輸出寫到暫存目錄（RESEARCH_OUT），不動 data/；
  3. 逐檔套 selftest 第 10 項同一套規則（情境 EPS 公式、說法 asof ≤ recorded_at、說法格式錯誤）；
  4. 通過的代號各自一個 commit「研究室.六 週更新 <代號>」；不通過的不 commit，原因寫進
     research/lab/INTAKE_FAILURES.md（附時間），由 DevQueue／互動視窗抄進 PENDING_QUEUE。

用法：python scripts/lab_weekly_intake.py [--dry-run]（--dry-run 只判定、不 commit、不寫失敗紀錄）
[自行裁量] 不直接改 PENDING_QUEUE.md：該檔同時有互動視窗與排程在寫，程式自動插行容易互相覆蓋。
本程式自身出錯只印警告、exit 0（十二節：守門員失敗不得中斷主流程）；push 由呼叫端決定。
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB_DIRS = ("research/lab/config", "research/lab/guidance")
FAIL_LOG = ROOT / "research" / "lab" / "INTAKE_FAILURES.md"
TW = timezone(timedelta(hours=8))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def changed_files():
    """回傳 {代號: [相對路徑...]}，只看 config/*.json 與 guidance/*.jsonl。"""
    out = git("status", "--porcelain", "-uall", "--", *LAB_DIRS).stdout
    by = {}
    for line in out.splitlines():
        p = line[3:].strip().strip('"')
        f = Path(p)
        if (f.parent.as_posix(), f.suffix) not in (("research/lab/config", ".json"), ("research/lab/guidance", ".jsonl")):
            continue
        by.setdefault(f.stem, []).append(p)
    return by


def problems_for(stock):
    """與 selftest_research.py 第 10 項同一套規則，但逐檔回傳原因。"""
    d = (stock or {}).get("deep")
    if not d:
        return ["build_research 沒建出 deep（設定檔讀不進或格式錯）"]
    bad = []
    sc = d["scenario"]
    for row in sc["rows"]:
        if row.get("eps") is None:
            continue
        eps = sc["base_revenue"] * (1 + row["growth"]) * (row["gm"] - row["opex"]) * (1 - sc["tax"]) / sc["shares"]
        if not math.isclose(eps, row["eps"], abs_tol=0.011):
            bad.append(f"情境 {row['name']} EPS 公式不符")
    for g in d["guidance"]["records"]:
        if g["asof"] > g["recorded_at"]:
            bad.append(f"說法 PIT：asof {g['asof']} 晚於 recorded_at {g['recorded_at']}")
    for e in d["guidance"]["errors"]:
        bad.append(f"說法格式：{e}")
    return bad


def _safe_problems(code, stock):
    """先.一三五-1fi：某一檔缺欄位（例如情境少 growth）時只判這一檔 FAIL，不讓例外拖垮其他代號的判定與 commit。"""
    try:
        return problems_for(stock)
    except Exception as e:
        print(f"[warn] {code} 檢查時出錯：{e!r}")
        return [f"檢查時出錯（設定缺欄位或格式不符）：{e!r}"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    by = changed_files()
    if not by:
        print("研究室.六：research/lab 沒有新變動，無事可做")
        return 0
    print(f"研究室.六：有變動的代號 {sorted(by)}")
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, RESEARCH_OUT=tmp, PYTHONIOENCODING="utf-8")
        b = subprocess.run([sys.executable, "scripts/build_research.py"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        if b.returncode != 0:
            print(f"[warn] build_research 失敗，全部不 commit：{(b.stderr or b.stdout)[-400:]}")
            results = {c: ["build_research 執行失敗"] for c in by}
        else:
            st = subprocess.run([sys.executable, "scripts/selftest_research.py"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
            summ = [ln for ln in st.stdout.splitlines() if ln.startswith("FAIL ") or ln.strip() == "全部 PASS" or ln.strip().endswith(" FAIL")]
            print("selftest_research（全市場，僅供參考，逐檔判定見下）：" + ("；".join(summ) or "(無摘要行)"))
            stocks = json.loads((Path(tmp) / "research.json").read_text(encoding="utf-8"))["stocks"]
            results = {c: _safe_problems(c, stocks.get(c)) for c in by}
    now = datetime.now(TW).strftime("%Y-%m-%d %H:%M")
    for c in sorted(by):
        bad = results[c]
        if bad:
            print(f"FAIL {c}：{'；'.join(bad)} → 不 commit")
            if not a.dry_run:
                with FAIL_LOG.open("a", encoding="utf-8") as fh:
                    fh.write(f"- {now} {c} 未 commit：{'；'.join(bad)}（檔案：{', '.join(by[c])}）\n")
            continue
        if a.dry_run:
            print(f"PASS {c}（--dry-run，不 commit）")
            continue
        git("add", "--", *by[c])
        r = git("commit", "-m", f"研究室.六 週更新 {c}\n\n自動接收：build_research＋第 10 項（情境公式／說法 PIT／格式）通過。", "--", *by[c])
        print(f"PASS {c} → " + ("已 commit" if r.returncode == 0 else f"[warn] commit 失敗：{(r.stderr or r.stdout)[-200:]}"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:  # 十二節：守門員自身錯誤只降級成警告
        print(f"[warn] lab_weekly_intake 自身出錯：{e!r}")
        raise SystemExit(0)
