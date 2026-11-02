"""先.一三五-1ic：前向判定的「隨機時點對照」要全宇宙每日價格，data/price_history 只留約 90 日；
探測能不能從 git 歷史（data/price_history/ 分檔，2026-10-13 起）串回完整日線。

唯讀、零外部請求、不寫 data/：只用 `git show <版本>:data/price_history/bN.json` 讀舊版，結果印到 stdout，
`--json PATH` 時另存一份摘要（建議放 research/data/，不進 repo）。

檢查三件事（取最早／中間／最新三版，兩兩比對重疊日）：
1. 原始收盤 close 在重疊日是否一致；
2. 同版內相鄰兩天 adj_close 比值（含息日報酬）跨版本是否一致——不一致的列出日期，多半是除權息資訊後到；
3. 串回整段要讀幾版、每版多大。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIR = "data/price_history"


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def versions() -> list[str]:
    return git("log", "--reverse", "--format=%h", "--", DIR + "/").decode().split()


def load_version(rev: str) -> tuple[dict, int]:
    names = [n for n in git("ls-tree", "--name-only", f"{rev}:{DIR}").decode().split() if n.startswith("b")]
    prices, size = {}, 0
    for n in names:
        raw = git("show", f"{rev}:{DIR}/{n}")
        size += len(raw)
        prices.update(json.loads(raw).get("prices") or {})
    return prices, size


def rets(rows: list) -> dict:
    out, prev = {}, None
    for r in rows:
        a = r.get("adj_close")
        if prev is not None and a and prev.get("adj_close"):
            out[r["date"]] = a / prev["adj_close"]
        prev = r
    return out


def compare(a: dict, b: dict, lo: str) -> dict:
    """a 舊版、b 新版；只比 b 視窗起點（lo）之後、兩版都有的日子。"""
    close_diff, ret_diff, days = [], [], 0
    for c, rows_a in a.items():
        rows_b = b.get(c)
        if not rows_b:
            continue
        ca = {r["date"]: r.get("close") for r in rows_a if r["date"] >= lo}
        cb = {r["date"]: r.get("close") for r in rows_b}
        for d in ca.keys() & cb.keys():
            days += 1
            if ca[d] is not None and cb[d] is not None and abs(ca[d] - cb[d]) > 1e-6:
                close_diff.append((c, d, ca[d], cb[d]))
        ra, rb = rets([r for r in rows_a if r["date"] >= lo]), rets(rows_b)
        for d in ra.keys() & rb.keys():
            if abs(ra[d] - rb[d]) > 1e-4:
                ret_diff.append((c, d, round(ra[d], 6), round(rb[d], 6)))
    return {"overlap_code_days": days, "close_diff_n": len(close_diff), "close_diff_sample": close_diff[:10],
            "ret_diff_n": len(ret_diff), "ret_diff_sample": sorted(ret_diff, key=lambda x: x[1])[:15]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()
    vs = versions()
    pick = [vs[0], vs[len(vs) // 2], vs[-1]]
    loaded = {}
    for v in pick:
        p, size = load_version(v)
        dates = sorted({r["date"] for rows in p.values() for r in rows if r["date"] >= "2026-01-01"})
        loaded[v] = p
        print(f"版本 {v}：{len(p)} 檔、{size / 1e6:.1f} MB、2026 年起日期 {dates[0] if dates else None}～{dates[-1] if dates else None}")
    rep = {"n_versions": len(vs), "picked": pick, "pairs": {}}
    for x, y in ((pick[0], pick[1]), (pick[1], pick[2]), (pick[0], pick[2])):
        lo = min((r["date"] for rows in loaded[y].values() for r in rows if r["date"] >= "2026-01-01"), default="")
        res = compare(loaded[x], loaded[y], lo)
        rep["pairs"][f"{x}->{y}"] = res
        print(f"{x}→{y}：重疊 {res['overlap_code_days']} 檔日；原始收盤不一致 {res['close_diff_n']}；相鄰日含息報酬不一致 {res['ret_diff_n']}")
        for t in res["close_diff_sample"][:5]:
            print("   close", t)
        for t in res["ret_diff_sample"][:8]:
            print("   ret", t)
    if args.json:
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 探測工具自己失敗只警告（十二節）
        print(f"[warn] 探測失敗：{type(e).__name__}: {e}")
        sys.exit(0)
