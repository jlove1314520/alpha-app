"""自測：前瞻選股台帳快照 `.github/scripts/build_picks_ledger.py`（先.一三五-1ch）。

`REPO_ROOT`／三榜分數檔／報價／大盤／輸出全部換成暫存目錄：零外部請求、不讀也不動真實 data/ 與 scores*.json。
鐵律「只能事前快照、嚴禁事後補建、寫入後不可回頭修改」目前沒有任何自測守門，這裡確認：
Top20 只取有 rank 的、同一（榜, 日）不重複快照、既有快照內容位元組不變、休市日不快照、缺 data_asof 不快照、
過期（>10 天）收盤價記 null 不頂替、查不到價記 null、既有台帳讀不出來時不覆寫歷史。
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
_spec = importlib.util.spec_from_file_location("build_picks_ledger", ROOT / ".github" / "scripts" / "build_picks_ledger.py")
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


def scores(asof, n=25, meta_extra=None):
    stocks = [{"code": f"{1000 + i}", "name": f"股{i}", "rank": i + 1, "total_score": 100 - i} for i in range(n)]
    stocks.insert(3, {"code": "9998", "name": "流動性不足", "rank": None, "total_score": 999})
    meta = {"data_asof": asof, "engine_version": "v-test"}
    meta.update(meta_extra or {})
    return {"meta": meta, "stocks": stocks}


def setup(base: Path, asof="2026-10-29", boards=("value", "momentum", "future")):
    (base / "data").mkdir(parents=True, exist_ok=True)
    files = {}
    for b in ("value", "momentum", "future"):
        f = base / f"scores_{b}.json"
        if b in boards:
            f.write_text(json.dumps(scores(asof)), encoding="utf-8")
        elif f.exists():
            f.unlink()
        files[b] = f
    quotes = {f"{1000 + i}": {"close": 50.0 + i, "date": asof} for i in range(25)}
    quotes["1001"] = {"close": 99.0, "date": "2020-08-17"}  # 極度過期
    del quotes["1002"]  # 查不到價
    (base / "data" / "quotes_all_tw.json").write_text(json.dumps({"quotes": quotes}), encoding="utf-8")
    (base / "data" / "market_tw.json").write_text(json.dumps({"taiex": {"close": 28000.0}}), encoding="utf-8")
    (base / "data" / "trading_calendar.json").write_text(
        json.dumps({"tw": {"2026": {"closed": ["2026-10-26"], "unscheduled_closed": []}}}), encoding="utf-8")
    P.REPO_ROOT = base
    P.BOARD_SCORE_FILES = files
    P.QUOTES_ALL_TW_PATH = base / "data" / "quotes_all_tw.json"
    P.MARKET_TW_PATH = base / "data" / "market_tw.json"
    P.OUT_PATH = base / "data" / "picks_ledger.json"


def run():
    try:
        P.main()
        return 0, None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def ledger(base):
    return json.loads((base / "data" / "picks_ledger.json").read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("情境一：三榜首次快照")
    setup(base)
    rc, err = run()
    check("沒有例外", err is None and rc == 0, (rc, err))
    L = ledger(base)
    check("三個快照", len(L["snapshots"]) == 3 and L["meta"]["total_snapshots"] == 3, len(L["snapshots"]))
    v = next(s for s in L["snapshots"] if s["board"] == "value")
    check("快照日＝分數檔 data_asof", v["snapshot_date"] == "2026-10-29")
    check("Top20、排除 rank=null", len(v["picks"]) == 20 and all(p["code"] != "9998" for p in v["picks"]))
    check("依 rank 由小到大", [p["rank"] for p in v["picks"]] == list(range(1, 21)))
    p0, p1, p2 = v["picks"][0], v["picks"][1], v["picks"][2]
    check("正常價照記", p0["close_price"] == 50.0 and p0["price_date"] == "2026-10-29" and not p0["price_stale"], p0)
    check("過期 >10 天的價記 null、標 stale（不頂替）", p1["close_price"] is None and p1["price_date"] is None
          and p1["price_stale"] is True, p1)
    check("查不到價記 null", p2["close_price"] is None and p2["price_stale"] is False, p2)
    check("報酬欄全 null（等回填）", all(all(x is None for x in p["returns"].values()) for p in v["picks"]))
    check("大盤收盤照記", v["taiex_close_at_snapshot"] == 28000.0)
    before = json.dumps(L["snapshots"], ensure_ascii=False, sort_keys=True)

    print("情境二：同一天重跑（分數檔內容換了）→ 不重複、不改寫既有快照")
    (base / "scores_value.json").write_text(json.dumps(scores("2026-10-29", n=30)).replace('"total_score": 100', '"total_score": 1'),
                                            encoding="utf-8")
    rc, err = run()
    L2 = ledger(base)
    check("沒有例外", err is None and rc == 0, (rc, err))
    check("仍是 3 個快照", len(L2["snapshots"]) == 3, len(L2["snapshots"]))
    check("既有快照內容不變", json.dumps(L2["snapshots"], ensure_ascii=False, sort_keys=True) == before)

    print("情境三：休市日（日曆 closed）與週末不快照")
    setup(base, asof="2026-10-26", boards=("value",))
    run()
    check("10-26 休市日沒有新快照", len(ledger(base)["snapshots"]) == 3)
    setup(base, asof="2026-10-31", boards=("value",))
    run()
    check("10-31 週六沒有新快照", len(ledger(base)["snapshots"]) == 3)

    print("情境四：缺 data_asof／分數檔不存在 → 不快照、不猜日期")
    setup(base, boards=())
    (base / "scores_value.json").write_text(json.dumps({"meta": {}, "stocks": scores("x")["stocks"]}), encoding="utf-8")
    rc, err = run()
    check("沒有例外", err is None and rc == 0, (rc, err))
    check("沒有新快照", len(ledger(base)["snapshots"]) == 3)

    print("情境五：下一個交易日 → 只追加，舊快照不變")
    setup(base, asof="2026-10-30", boards=("momentum",))
    run()
    L5 = ledger(base)
    check("追加 1 個", len(L5["snapshots"]) == 4 and L5["snapshots"][-1]["snapshot_date"] == "2026-10-30")
    check("前 3 個不變", json.dumps(L5["snapshots"][:3], ensure_ascii=False, sort_keys=True) == before)
    good = (base / "data" / "picks_ledger.json").read_text(encoding="utf-8")

    print("情境六：既有台帳損壞／結構不對 → 不覆寫歷史")
    for name, text in (("JSON 損壞", good[: len(good) // 2]), ("snapshots 不是陣列", '{"snapshots": {}}')):
        (base / "data" / "picks_ledger.json").write_text(text, encoding="utf-8")
        setup(base, asof="2026-10-30", boards=("value",))
        rc, err = run()
        check(f"{name}：沒有未處理例外、非零退出", err is None and rc not in (0, None), (rc, err))
        check(f"{name}：台帳檔維持原樣（沒被今天的快照蓋掉）",
              (base / "data" / "picks_ledger.json").read_text(encoding="utf-8") == text)

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
