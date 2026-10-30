"""自測：下市股從榜單剔除 `scripts/prune_delisted.py`（先.一三五-1cq）。

`ROOT`／`UNIVERSE` 換成暫存目錄、`price_history_store` 換成假物件，零外部請求、不讀也不動真實 scores*.json 與 data/。
確認：只剔不在 active 或價格落後全市場最新日超過 30 天的代號、rank 重編連續 1..N（null 維持 null）、重跑 0 筆變更、
名冊不存在／讀不出來／active 不足 1000 檔時不改寫榜單、某份榜單損壞只略過那一份不拖垮其他份。
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
_spec = importlib.util.spec_from_file_location("prune_delisted", ROOT / "scripts" / "prune_delisted.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


class FakePHS:
    def __init__(self, prices: dict | None) -> None:
        self.prices = prices

    def exists(self, path) -> bool:  # noqa: ARG002
        return self.prices is not None

    def load(self, path):  # noqa: ARG002
        return {"prices": self.prices}


ACTIVE = [f"{9000 + i}" for i in range(1000)] + ["2330", "2454", "1538", "3008"]


def setup(d: Path, active=ACTIVE, universe=True) -> None:
    d.mkdir(parents=True, exist_ok=True)
    if universe:
        (d / "data").mkdir(exist_ok=True)
        (d / "data" / "listed_universe.json").write_text(json.dumps({"active": active}), encoding="utf-8")
    scores = {"meta": {"x": 1}, "stocks": [
        {"code": "2330", "rank": 1}, {"code": "2325", "rank": 2, "name": "矽品"},  # 2325 不在名冊
        {"code": "2454", "rank": 3}, {"code": "1538", "rank": 4, "name": "正峰"},  # 1538 價格停很久
        {"code": "6666", "rank": None},  # 不在名冊、本來就沒排名
        {"code": "3008", "rank": None},  # 在名冊、流動性不足維持 null
    ]}
    for name in P.TARGETS:
        (d / name).write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")


PRICES = {
    "2330": [{"date": "2026-10-29", "close": 1}], "2454": [{"date": "2026-10-20", "close": 1}],
    "1538": [{"date": "2024-12-31", "close": 1}], "3008": [{"date": "2026-10-29", "close": 1}],
}


def run(d: Path, prices=PRICES):
    P.ROOT = d
    P.UNIVERSE = d / "data" / "listed_universe.json"
    P.PHS = FakePHS(prices)
    try:
        return P.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：正常過濾")
    d1 = base / "d1"
    setup(d1)
    rc, err = run(d1)
    check("rc=0 不拋例外", rc == 0 and err is None, (rc, err))
    for name in P.TARGETS:
        doc = json.loads((d1 / name).read_text(encoding="utf-8"))
        codes = [r["code"] for r in doc["stocks"]]
        check(f"{name}：只留在名冊且價格不過期的 2330／2454／3008", codes == ["2330", "2454", "3008"], codes)
        check(f"{name}：rank 重編 1、2，null 維持 null", [r["rank"] for r in doc["stocks"]] == [1, 2, None], [r["rank"] for r in doc["stocks"]])
        f = doc["meta"].get("delisted_filter", {})
        check(f"{name}：meta 記移除 3 筆（有排名 2 筆）、最新價格日、原 meta 保留",
              f.get("removed") == 3 and f.get("removed_ranked") == 2 and f.get("market_latest_date") == "2026-10-29" and doc["meta"].get("x") == 1, f)
    print("情境一之二：重跑 0 筆變更")
    rc, err = run(d1)
    doc = json.loads((d1 / P.TARGETS[0]).read_text(encoding="utf-8"))
    check("重跑 rc=0、移除 0 筆、名單不變", rc == 0 and doc["meta"]["delisted_filter"]["removed"] == 0
          and [r["code"] for r in doc["stocks"]] == ["2330", "2454", "3008"], doc["meta"]["delisted_filter"])

    print("情境二：沒有價格歷史 → 只做名冊過濾")
    d2 = base / "d2"
    setup(d2)
    rc, err = run(d2, prices=None)
    codes = [r["code"] for r in json.loads((d2 / P.TARGETS[0]).read_text(encoding="utf-8"))["stocks"]]
    check("無價格歷史：1538 在名冊照留、2325／6666 剔除", rc == 0 and codes == ["2330", "2454", "1538", "3008"], (rc, codes))

    def snapshot(d: Path) -> list[str]:
        return [(d / n).read_text(encoding="utf-8") for n in P.TARGETS]

    print("情境三：名冊不存在 → 不改寫榜單")
    d3 = base / "d3"
    setup(d3, universe=False)
    before = snapshot(d3)
    rc, err = run(d3)
    check("名冊不存在 rc≠0、沒拋例外、榜單不動", rc not in (0, None) and err is None and snapshot(d3) == before, (rc, err))

    print("情境四：active 不足 1000 檔 → 不改寫榜單")
    d4 = base / "d4"
    setup(d4, active=["2330", "2454"])
    before = snapshot(d4)
    rc, err = run(d4)
    check("active 不足 rc≠0、沒拋例外、榜單不動", rc not in (0, None) and err is None and snapshot(d4) == before, (rc, err))

    print("情境五：active 為空 → 不改寫榜單")
    d5 = base / "d5"
    setup(d5, active=[])
    before = snapshot(d5)
    rc, err = run(d5)
    check("active 空 rc≠0、沒拋例外、榜單不動", rc not in (0, None) and err is None and snapshot(d5) == before, (rc, err))

    print("情境六：名冊檔損壞 → 不拋未處理例外、不改寫榜單")
    d6 = base / "d6"
    setup(d6)
    (d6 / "data" / "listed_universe.json").write_text("<<<<<<< HEAD", encoding="utf-8")
    before = snapshot(d6)
    rc, err = run(d6)
    check("名冊損壞 rc≠0、沒拋未處理例外", rc not in (0, None) and err is None, (rc, err))
    check("名冊損壞時榜單不動", snapshot(d6) == before)

    print("情境七：其中一份榜單損壞 → 只略過那一份，其他照常過濾")
    d7 = base / "d7"
    setup(d7)
    (d7 / P.TARGETS[1]).write_text("{壞掉", encoding="utf-8")
    rc, err = run(d7)
    check("單份損壞沒拋未處理例外", err is None, err)
    check("損壞那份原樣不動", (d7 / P.TARGETS[1]).read_text(encoding="utf-8") == "{壞掉")
    other = [r["code"] for r in json.loads((d7 / P.TARGETS[2]).read_text(encoding="utf-8"))["stocks"]]
    check("後面那份照常過濾", other == ["2330", "2454", "3008"], other)

print(f"\n結果：{ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
