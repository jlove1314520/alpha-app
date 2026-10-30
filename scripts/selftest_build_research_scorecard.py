"""自測：研究成績單 `scripts/build_research_scorecard.py`（先.一三五-1cu）。

`ROOT`／`OUT` 換成暫存目錄：零外部請求、不讀也不動真實 data/ 與 research/。
App「研究成績單」頁唯一來源，這裡確認：總數與判定分類照 trials_index、墓園 A／B／C 統計與逐條表、
對照 0050 照 strategy_curves（≥60 天才判輸贏、天數不足照實標）、任一輸入讀不到只該段標 error 不編數字、
三個輸入全部讀不到不覆寫既有 research_scorecard.json、也不拋未處理例外。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_research_scorecard", ROOT / "scripts" / "build_research_scorecard.py")
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
    B.OUT = root / "data" / "research_scorecard.json"
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


TRIALS = {"count": 6, "count_rule": "測試用：含重號",
          "rows": [{"id": 1, "name": "甲", "verdict": "FAIL：沒優勢", "track": "台股"},
                   {"id": 2, "name": "乙", "verdict": "FAIL", "track": "台股"},
                   {"id": 3, "name": "丙", "verdict": "VIOLATES_SURVIVAL MDD 56%", "track": "美股"},
                   {"id": 4, "name": "丁", "verdict": "PASS（Bb-90）", "track": "台股"},
                   {"id": 5, "name": "戊", "verdict": "CHEAP_PASS", "track": None},
                   {"id": 6, "name": "己", "verdict": None, "track": "期貨"}]}

AUTOPSY = """# 墓園驗屍（測試用）

## 2. 說明
文字

## 3. 逐條表
| # | 名稱 | 日期 | 分類 | 死因 | 備註 |
|---|---|---|---|---|---|
| 1 | f_a | 2026-09-01 | A | 程式錯 | - |
| 2 | f_b | 2026-09-02 | C（邊界） | 沒優勢 | - |
| 3 | f_c | 2026-09-03 | B | 樣本短 | - |
| x | 表外列 | - | A | - | - |

## 4. 統計
```json
{"total": 3, "counts": {"A": 1, "B": 1, "C": 1}, "borderline": 1}
```
"""

CURVES = {"lines": [
    {"id": "w", "label": "長跑贏", "group": "g", "status": "live", "start_date": "2026-06-01", "as_of": "2026-10-29",
     "metrics": {"days": 100, "cum_pct": 12.0, "bench_cum_pct": 8.0, "cum_gap_pp": 4.0, "mdd_pct": -5, "bench_mdd_pct": -7}},
    {"id": "l", "label": "長跑輸", "group": "g", "status": "live",
     "metrics": {"days": 80, "cum_pct": 1.0, "bench_cum_pct": 8.0, "cum_gap_pp": -7.0}},
    {"id": "s", "label": "短暫領先", "group": "g", "status": "live",
     "metrics": {"days": 20, "cum_pct": 5.0, "bench_cum_pct": 1.0, "cum_gap_pp": 4.0}},
    {"id": "z", "label": "未開始", "group": "g", "status": "pending", "metrics": {}},
]}


def build(root: Path, trials=True, autopsy=True, curves=True, curves_obj=None):
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir(parents=True, exist_ok=True)
    if trials is True:
        (root / "data" / "trials_index.json").write_text(json.dumps(TRIALS, ensure_ascii=False), encoding="utf-8")
    elif trials == "bad":
        (root / "data" / "trials_index.json").write_text('{"rows": [', encoding="utf-8")
    if autopsy is True:
        (root / "research" / "GRAVEYARD_AUTOPSY.md").write_text(AUTOPSY, encoding="utf-8")
    elif autopsy == "bad":
        (root / "research" / "GRAVEYARD_AUTOPSY.md").write_text("# 沒有表也沒有 json\n", encoding="utf-8")
    if curves is True:
        (root / "data" / "strategy_curves.json").write_text(
            json.dumps(curves_obj or CURVES, ensure_ascii=False), encoding="utf-8")
    elif curves == "bad":
        (root / "data" / "strategy_curves.json").write_text("{", encoding="utf-8")


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：三個輸入都正常")
    r1 = base / "ok"
    build(r1)
    rc, err = run(r1)
    check("沒有未處理例外", err is None, repr(err))
    check("exit 0", rc == 0, rc)
    doc = json.loads((r1 / "data" / "research_scorecard.json").read_text(encoding="utf-8"))
    t = doc.get("trials") or {}
    check("總數照 trials_index.count", t.get("count") == 6, t.get("count"))
    bv = dict(map(tuple, t.get("by_verdict") or []))
    check("判定分類：未通過 2、違反天條一 1、通過 1、初篩 1、其他 1",
          bv == {"未通過": 2, "違反天條一（最大回撤超過 50%）": 1, "通過判準": 1,
                 "初篩通過（未完成全部關卡）": 1, "其他（描述性研究、資料不可用、無法重現等）": 1}, bv)
    bt = dict(map(tuple, t.get("by_track") or []))
    check("各軌：台股 3、美股 1、期貨 1、缺軌記『其他』1", bt == {"台股": 3, "美股": 1, "期貨": 1, "其他": 1}, bt)
    check("通過清單只有 #4", [p["id"] for p in t.get("passed") or []] == [4], t.get("passed"))
    a = doc.get("autopsy") or {}
    check("墓園 total／counts／borderline 照 json 區塊", a.get("total") == 3 and a.get("counts") == {"A": 1, "B": 1, "C": 1}
          and a.get("borderline") == 1, a)
    rows = a.get("rows") or []
    check("逐條表 3 列（非數字列不算）", [x["name"] for x in rows] == ["f_a", "f_b", "f_c"], rows)
    check("『C（邊界）』→ class C＋borderline", rows[1]["class"] == "C" and rows[1]["borderline"] is True if len(rows) > 1 else False, rows)
    check("A 類 borderline=False", rows and rows[0]["class"] == "A" and rows[0]["borderline"] is False, rows[:1])
    o = doc.get("oos") or {}
    by = {x["id"]: x for x in o.get("lines") or []}
    check("≥60 天且領先 → 贏 0050", by.get("w", {}).get("judge") == "贏 0050", by.get("w"))
    check("≥60 天且落後 → 輸 0050", by.get("l", {}).get("judge") == "輸 0050", by.get("l"))
    check("<60 天領先 → 天數不足、暫時領先、不能判斷", "天數不足（20 天 < 60）" in str(by.get("s", {}).get("judge"))
          and "暫時領先" in str(by.get("s", {}).get("judge")), by.get("s"))
    check("無 days → 尚未開始、days=0、沒有編報酬", by.get("z", {}).get("days") == 0 and "ret_pct" not in by.get("z", {}), by.get("z"))
    check("winners 只有長跑贏", o.get("winners") == ["長跑贏"], o.get("winners"))
    check("結論句由資料算出（點名長跑贏）", "長跑贏" in str(o.get("conclusion")) and "短暫領先" not in str(o.get("conclusion")), o.get("conclusion"))
    check("notes 有內容、meta 標非投資建議", len(doc.get("notes") or []) >= 1 and "非投資建議" in doc["meta"]["note"])
    check("沒有留下 .tmp", not (r1 / "data" / "research_scorecard.json.tmp").exists())

    print("情境二：沒有任何策略滿 60 天 → 結論說沒有贏")
    r2 = base / "nowin"
    build(r2, curves_obj={"lines": [CURVES["lines"][2], CURVES["lines"][3]]})
    run(r2)
    o2 = json.loads((r2 / "data" / "research_scorecard.json").read_text(encoding="utf-8"))["oos"]
    check("winners 空", o2.get("winners") == [], o2.get("winners"))
    check("結論『目前沒有任何策略在樣本外贏過 0050』且寫最長 20 天", "目前沒有任何策略" in o2["conclusion"] and "20 個交易日" in o2["conclusion"], o2["conclusion"])

    good = (r1 / "data" / "research_scorecard.json").read_text(encoding="utf-8")

    print("情境三：單一輸入讀不到／損壞 → 只該段標 error、其他段照常、不編數字")
    for title, kw, key in (("trials_index 不存在", {"trials": False}, "trials"),
                           ("trials_index 損壞", {"trials": "bad"}, "trials"),
                           ("墓園不存在", {"autopsy": False}, "autopsy"),
                           ("墓園格式不對", {"autopsy": "bad"}, "autopsy"),
                           ("strategy_curves 不存在", {"curves": False}, "oos"),
                           ("strategy_curves 損壞", {"curves": "bad"}, "oos")):
        r = base / title
        build(r, **kw)
        rc, err = run(r)
        d = json.loads((r / "data" / "research_scorecard.json").read_text(encoding="utf-8")) if err is None else {}
        others = [k for k in ("trials", "autopsy", "oos") if k != key]
        check(f"{title}：沒有未處理例外、exit 0", err is None and rc == 0, (rc, repr(err)))
        check(f"{title}：{key} 只有 error 欄（不編數字）", list((d.get(key) or {}).keys()) == ["error"], d.get(key))
        check(f"{title}：其他兩段照常", all("error" not in (d.get(k) or {"error": 1}) for k in others), [d.get(k, {}).keys() for k in others])

    print("情境四：三個輸入全部讀不到 → 不覆寫既有輸出")
    for title, kw in (("全部不存在", {"trials": False, "autopsy": False, "curves": False}),
                      ("全部損壞", {"trials": "bad", "autopsy": "bad", "curves": "bad"})):
        r = base / title
        build(r, **kw)
        (r / "data" / "research_scorecard.json").write_text(good, encoding="utf-8")
        rc, err = run(r)
        check(f"{title}：沒有未處理例外", err is None, repr(err))
        check(f"{title}：exit 0（不中斷排程）", rc == 0, rc)
        check(f"{title}：既有 research_scorecard.json 未被改",
              (r / "data" / "research_scorecard.json").read_text(encoding="utf-8") == good)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
