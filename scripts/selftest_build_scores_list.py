"""自測：選股清單精簡檔 `scripts/build_scores_list.py`（先.一三五-1cv）。

`ROOT` 換成暫存目錄：零外部請求、不讀也不動真實 scores*.json。
選股頁清單讀它，這裡確認：因子只留 score／percentile、拿掉 raw／reason、列加 _lite、其他欄位與 meta 原樣保留、
不動原檔、內容沒變不重寫、來源讀不到／損壞／格式不對／是空的都不寫空清單、不拋未處理例外、其他榜照常產出。
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
_spec = importlib.util.spec_from_file_location("build_scores_list", ROOT / "scripts" / "build_scores_list.py")
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


def run(root: Path):
    B.ROOT = root
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def board(n: int = 2) -> dict:
    return {"meta": {"generated_at": "2026-10-29T17:30:00+08:00", "universe": n}, "weights": {"chips": 0.5},
            "stocks": [{"code": f"23{i:02d}", "name": f"測{i}", "rank": i + 1, "total_score": 9.0 - i,
                        "factors": {"chips": {"score": 9.1, "percentile": 0.91, "raw": {"net": 123}, "reason": "外資買超"},
                                    "value": {"score": None, "raw": None, "reason": "缺資料"},
                                    "weird": "不是 dict"}}
                       for i in range(n)]}


def write_all(root: Path, docs: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for b, d in docs.items():
        (root / f"{b}.json").write_text(d if isinstance(d, str) else json.dumps(d, ensure_ascii=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：三榜都正常")
    r1 = base / "ok"
    write_all(r1, {b: board() for b in B.BOARDS})
    src_before = (r1 / "scores.json").read_text(encoding="utf-8")
    rc, err = run(r1)
    check("沒有未處理例外", err is None, repr(err))
    check("exit 0", rc == 0, rc)
    check("三榜都產出 _list", all((r1 / f"{b}_list.json").exists() for b in B.BOARDS))
    out = json.loads((r1 / "scores_list.json").read_text(encoding="utf-8"))
    s0 = out["stocks"][0]
    check("chips 只留 score／percentile", s0["factors"]["chips"] == {"score": 9.1, "percentile": 0.91}, s0["factors"]["chips"])
    check("缺分數因子：score=None 照留、percentile 不補", s0["factors"]["value"] == {"score": None}, s0["factors"]["value"])
    check("非 dict 因子被略過", "weird" not in s0["factors"], s0["factors"])
    check("任何因子都沒有 raw／reason", all("raw" not in f and "reason" not in f for r in out["stocks"] for f in r["factors"].values()))
    check("每列 _lite:true", all(r.get("_lite") is True for r in out["stocks"]))
    check("列上其他欄位原樣保留", {k: s0[k] for k in ("code", "name", "rank", "total_score")} ==
          {"code": "2300", "name": "測0", "rank": 1, "total_score": 9.0}, s0)
    check("meta／weights 原樣保留、頂層加 _lite 說明", out["meta"] == board()["meta"] and out["weights"] == {"chips": 0.5}
          and "精簡" in str(out.get("_lite")), {k: out.get(k) for k in ("meta", "weights", "_lite")})
    check("列數不變", len(out["stocks"]) == 2)
    check("原檔 scores.json 沒被動", (r1 / "scores.json").read_text(encoding="utf-8") == src_before)

    print("情境二：內容沒變不重寫")
    lst = r1 / "scores_list.json"
    old_t = time.time() - 3600
    os.utime(lst, (old_t, old_t))
    rc, err = run(r1)
    check("再跑一次 exit 0", err is None and rc == 0, (rc, repr(err)))
    check("mtime 沒動（沒重寫）", abs(lst.stat().st_mtime - old_t) < 1, lst.stat().st_mtime - old_t)
    write_all(r1, {"scores": board(3)})
    run(r1)
    check("來源變了才重寫（3 列）", len(json.loads(lst.read_text(encoding="utf-8"))["stocks"]) == 3)
    good = {b: (r1 / f"{b}_list.json").read_text(encoding="utf-8") for b in B.BOARDS}

    print("情境三：單一榜來源讀不到／損壞／格式不對／是空的 → 該榜不寫、其他榜照常")
    for title, bad in (("不存在", None), ("JSON 損壞", '{"stocks": ['), ("頂層不是物件", "[1, 2]"),
                       ("stocks 是空的", {"meta": {}, "stocks": []}), ("沒有 stocks 欄", {"meta": {}})):
        r = base / title
        write_all(r, {b: board() for b in B.BOARDS if b != "scores_momentum"})
        if bad is not None:
            write_all(r, {"scores_momentum": bad})
        for b in B.BOARDS:
            (r / f"{b}_list.json").write_text(good[b], encoding="utf-8")
        rc, err = run(r)
        check(f"{title}：沒有未處理例外", err is None, repr(err))
        check(f"{title}：非零退出（排程 continue-on-error 只警告）", rc not in (0, None), rc)
        check(f"{title}：scores_momentum_list.json 維持原狀（不寫空清單）",
              (r / "scores_momentum_list.json").read_text(encoding="utf-8") == good["scores_momentum"])
        check(f"{title}：其他兩榜照常產出", all(json.loads((r / f"{b}_list.json").read_text(encoding="utf-8"))["stocks"][0].get("_lite")
                                       for b in ("scores", "scores_future")))

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
