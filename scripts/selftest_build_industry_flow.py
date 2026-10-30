"""自測：產業資金流 `scripts/build_industry_flow.py`（先.一三五-1ct）。

`DATA`／`OUT` 換成暫存目錄：零外部請求、不讀也不動真實 data/。
選股頁「主流題材（資金流入中）」唯一 repo 來源，這裡確認：同產業成交值逐日加總、
資金流入％＝近 5 日均值÷近 20 日均值−1、漲跌＝同產業個股當日漲跌幅等權平均、
缺產業不歸類、成分 <5 檔不列、擁擠度 streak／累積漲幅、
輸入讀不到／損壞／是空的都不覆寫既有 industry_flow.json、也不拋未處理例外。
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
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("build_industry_flow", ROOT / "scripts" / "build_industry_flow.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
B.PHS._read.__defaults__ = (1,)  # 損壞情境不要重試 5 次空等

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def close(a, b, tol=0.01):
    return a is not None and abs(a - b) <= tol


def run(data_dir: Path):
    B.DATA = data_dir
    B.OUT = data_dir / "industry_flow.json"
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


DATES = [f"2026-10-{d:02d}" for d in range(1, 26)]  # 25 個交易日


def series(turn_fn, close_fn):
    return [{"date": d, "close": close_fn(i), "turnover": turn_fn(i)} for i, d in enumerate(DATES)]


with tempfile.TemporaryDirectory() as td:
    base = Path(td)
    main_dir = base / "main"
    main_dir.mkdir()

    prices, comp = {}, {}
    # 半導體 5 檔：前 20 天每檔每日成交 100，最後 5 天每檔 200 → 產業日成交 500 → 1000
    #   近5日均 1000；近20日均 (15×500＋5×1000)/20＝625 → 流入 +60%
    #   收盤每天 ×1.01（最後 5 天）→ 當日等權漲幅 1%；streak＝5、累積 1.01^5−1≈5.10% → 未擁擠
    for k in range(5):
        code = f"23{k:02d}"
        prices[code] = series(lambda i: 200.0 if i >= 20 else 100.0,
                              lambda i: 100.0 * (1.01 ** max(0, i - 19)))
        comp[code] = {"industry": "半導體業"}
    # 航運 5 檔：漲跌各不同 → 測等權平均（當日 +2%、+4%、0%、−1%、+5% → 平均 +2%）；最後 4 天量大＋大漲 → 擁擠
    last_rets = [0.02, 0.04, 0.0, -0.01, 0.05]
    for k in range(5):
        code = f"26{k:02d}"

        def cl(i, k=k):
            if i < 21:
                return 50.0
            if i < 24:
                return 50.0 * (1.05 ** (i - 20))  # 第 21～23 天每天 +5%
            return 50.0 * (1.05 ** 3) * (1 + last_rets[k])

        prices[code] = series(lambda i: 300.0 if i >= 21 else 100.0, cl)
        comp[code] = {"industry": "航運業"}
    # 小產業只 4 檔 → 不列
    for k in range(4):
        code = f"99{k:02d}"
        prices[code] = series(lambda i: 50.0, lambda i: 10.0)
        comp[code] = {"industry": "小產業"}
    # 沒有產業別（company_info 沒這檔／industry 空字串）→ 不歸類，不得混進任何產業
    prices["8888"] = series(lambda i: 1e9, lambda i: 10.0 * (2 ** i))
    prices["7777"] = series(lambda i: 1e9, lambda i: 10.0)
    comp["7777"] = {"industry": ""}

    (main_dir / "price_history.json").write_text(json.dumps({"meta": {}, "prices": prices}), encoding="utf-8")
    (main_dir / "company_info.json").write_text(json.dumps({"companies": comp}, ensure_ascii=False), encoding="utf-8")

    print("情境一：正常計算")
    rc, err = run(main_dir)
    check("沒有未處理例外", err is None, repr(err))
    check("exit 0", rc == 0, rc)
    doc = json.loads((main_dir / "industry_flow.json").read_text(encoding="utf-8"))
    rows = {r["industry"]: r for r in doc["industries"]}
    check("只列成分 ≥5 檔的兩個產業", set(rows) == {"半導體業", "航運業"}, list(rows))
    check("缺產業股票沒有變成一個產業（'' / None 不出現）", "" not in rows and None not in rows)
    semi = rows.get("半導體業", {})
    check("半導體 members＝5", semi.get("members") == 5, semi)
    check("半導體 資金流入＝+60%（同產業成交值加總、5日÷20日−1）", close(semi.get("inflow_pct"), 60.0), semi.get("inflow_pct"))
    check("半導體 當日漲跌＝+1%", close(semi.get("pct"), 1.0), semi.get("pct"))
    check("半導體 streak＝5", semi.get("streak") == 5, semi.get("streak"))
    check("半導體 累積≈5.10%、未擁擠", close(semi.get("cum_gain_pct"), 5.10) and semi.get("crowded") is False, semi)
    ship = rows.get("航運業", {})
    # 航運：產業日成交前 21 天 500、後 4 天 1500 → 近5日均 (500+4×1500)/5＝1300；近20日均 (16×500+4×1500)/20＝700
    check("航運 資金流入＝1300/700−1≈+85.71%", close(ship.get("inflow_pct"), 85.71), ship.get("inflow_pct"))
    check("航運 當日漲跌＝等權平均 +2%", close(ship.get("pct"), 2.0), ship.get("pct"))
    check("航運 streak＝4", ship.get("streak") == 4, ship.get("streak"))
    # 累積：1.05^3 × 1.02 − 1 ≈ 18.07%
    check("航運 累積≈18.07%、已擁擠", close(ship.get("cum_gain_pct"), 18.07) and ship.get("crowded") is True, ship)
    check("依資金流入由大到小排序", [r["industry"] for r in doc["industries"]] == ["航運業", "半導體業"])
    check("data_date＝最大日期", doc["meta"]["data_date"] == "2026-10-25", doc["meta"].get("data_date"))
    check("各產業 date＝最後一天", all(r["date"] == "2026-10-25" for r in doc["industries"]))
    good = (main_dir / "industry_flow.json").read_text(encoding="utf-8")

    def scenario(title, setup):
        d = base / title
        d.mkdir()
        (d / "industry_flow.json").write_text(good, encoding="utf-8")
        setup(d)
        rc, err = run(d)
        check(f"{title}：沒有未處理例外", err is None, repr(err))
        check(f"{title}：exit 0（不中斷 market.yml 後續步驟）", rc == 0, rc)
        check(f"{title}：既有 industry_flow.json 未被改", (d / "industry_flow.json").read_text(encoding="utf-8") == good)

    ph_ok = json.dumps({"meta": {}, "prices": prices})
    ci_ok = json.dumps({"companies": comp}, ensure_ascii=False)

    print("情境二：輸入讀不到／損壞 → 不覆寫")
    scenario("price_history 不存在", lambda d: (d / "company_info.json").write_text(ci_ok, encoding="utf-8"))
    scenario("company_info 不存在", lambda d: (d / "price_history.json").write_text(ph_ok, encoding="utf-8"))
    scenario("price_history 損壞", lambda d: ((d / "price_history.json").write_text('{"prices": {"2330": [', encoding="utf-8"),
                                            (d / "company_info.json").write_text(ci_ok, encoding="utf-8")))
    scenario("company_info 損壞", lambda d: ((d / "price_history.json").write_text(ph_ok, encoding="utf-8"),
                                           (d / "company_info.json").write_text('{"companies": {', encoding="utf-8")))

    print("情境三：輸入是空的／全部算不出產業 → 不寫空檔")
    scenario("prices 為空", lambda d: ((d / "price_history.json").write_text('{"meta": {}, "prices": {}}', encoding="utf-8"),
                                      (d / "company_info.json").write_text(ci_ok, encoding="utf-8")))
    scenario("companies 為空", lambda d: ((d / "price_history.json").write_text(ph_ok, encoding="utf-8"),
                                         (d / "company_info.json").write_text('{"companies": {}}', encoding="utf-8")))

print(f"\n合計 {ok} 過、{fail} 失敗")
sys.exit(1 if fail else 0)
