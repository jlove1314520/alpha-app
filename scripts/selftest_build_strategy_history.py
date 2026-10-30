"""自測：「跟 0050 比」歷史段 `.github/scripts/build_strategy_history.py`（先.一三五-1cm）。

RD／MONTHLY／OUT 全部換成暫存目錄（假結果檔＋假逐月序列）：零外部請求、不讀也不動真實 research/data 與 data/。確認：
年化與最大跌幅都一致→「可重現」並附序列、只有最大跌幅不一致→「月頻近似」仍附序列、年化不一致→「無法重現」不附序列、
沒有序列→NO_SERIES、來源路徑與試驗編號照實、樣本外段原樣搬逐月、單一結果檔缺只少那一段、內容未變不重寫、
結果檔全讀不到不覆寫既有輸出。
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
_spec = importlib.util.spec_from_file_location("build_strategy_history", ROOT / ".github" / "scripts" / "build_strategy_history.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


MONTHS = [f"2020-{m:02d}" for m in range(1, 13)]
R_A = [0.01, -0.02, 0.03, 0.01, -0.01, 0.02, 0.0, 0.01, -0.03, 0.02, 0.01, 0.01]
CAGR_A, MDD_A = H._series_stats(R_A)
P = {"start": "2003-07-01", "end": "2024-12-31"}


def write_all(rd: Path, skip=()):
    files = {
        "core_allocation_result_unioncal.json": {"period": P, "grid": {"Bb-90": {"cagr": CAGR_A, "mdd": MDD_A},
                                                                      "Aa-70": {"cagr": 0.05, "mdd": -0.2}}},
        "bb90_oos_2025_result.json": {"period": ["2025-01", "2026-09"], "results": {
            "Bb-90": {"cagr": 0.1, "mdd": -0.05, "monthly": {"2025-01": 0.01}, "cum_return": 0.2},
            "paper1_70_30": {"cagr": 0.06, "mdd": -0.03, "monthly": {"2025-01": 0.005}, "cum_return": 0.1},
            "0050_hold": {"cagr": 0.2, "mdd": -0.1, "monthly": {"2025-01": 0.02}, "cum_return": 0.3}}},
        # S3-C6：年化一致、最大跌幅故意差 1pp → 月頻近似；本檔沒期間 → 沿用第 5 欄的檔
        "crisis_gate_timing_sensitivity_unioncal.json": {"trials": {"S3-C6": {"cagr": CAGR_A, "mdd": MDD_A - 0.01}}},
        "crisis_gate_leveraged_bb90_result_unioncal.json": {"period": {"start": "2003-07-01", "end": "2024-12-31"}},
        "s3c6_oos_2025_result.json": {"period": ["2025-01", "2026-09"], "results": {"S3-C6_real": {"cagr": 0.07, "mdd": -0.04, "monthly": {}}}},
        # R1-C：年化故意差 1pp → 無法重現
        "r1_0050_credit_gate_result_unioncal.json": {"period": P, "trials": {"R1-C": {"stats": {"cagr": CAGR_A + 0.01, "mdd": MDD_A}}},
                                                     "benchmark_0050_buy_hold": {"cagr": 0.09, "mdd": -0.5}},
    }
    rd.mkdir(parents=True, exist_ok=True)
    for f, doc in files.items():
        p = rd / f
        if f in skip:
            if p.exists():
                p.unlink()
            continue
        p.write_text(json.dumps(doc), encoding="utf-8")


MDOC = {"months": MONTHS, "returns": {"Bb-90": R_A, "S3-C6": R_A, "R1-C": R_A}}  # 沒有 0050 → NO_SERIES


def setup(base: Path, skip=(), mdoc=MDOC, old_out=None):
    rd, data = base / "research" / "data", base / "data"
    data.mkdir(parents=True, exist_ok=True)
    write_all(rd, skip)
    (data / "strategy_monthly_returns.json").write_text(json.dumps(mdoc), encoding="utf-8")
    out = data / "strategy_history.json"
    if old_out is not None:
        out.write_text(old_out, encoding="utf-8")
    elif out.exists():
        out.unlink()
    H.RD, H.MONTHLY, H.OUT = rd, data / "strategy_monthly_returns.json", out
    return out


def run():
    try:
        return H.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("[1] 正常產出")
    out = setup(base)
    code, err = run()
    check("正常執行不拋例外", err is None and code == 0, (code, err))
    doc = json.loads(out.read_text(encoding="utf-8"))
    bb = doc["lines"]["live_bb90"]["backtest"]
    check("年化與最大跌幅一致 → 可重現、附序列", bb["repro"]["status"] == "OK" and bb["monthly"] == dict(zip(MONTHS, R_A)), bb["repro"])
    check("來源路徑與試驗編號照實", bb["source"] == "research/data/core_allocation_result_unioncal.json"
          and bb["path"] == ["grid", "Bb-90"] and bb["trials"] == "#417／#418")
    s3 = doc["lines"]["paper_3"]["backtest"]
    check("只有最大跌幅不一致 → 月頻近似、仍附序列", s3["repro"]["status"] == "MONTHLY_APPROX" and s3["repro"]["draw_curve"] is True
          and "monthly" in s3, s3["repro"])
    check("本檔沒期間 → 沿用第 5 欄檔的期間", s3["period"] == ["2003-07-01", "2024-12-31"], s3["period"])
    r1 = doc["lines"]["paper_4"]["backtest"]
    check("年化不一致 → 無法重現、不附序列", r1["repro"]["status"] == "IRREPRODUCIBLE" and "monthly" not in r1
          and r1["repro"]["draw_curve"] is False, r1["repro"])
    a70 = doc["lines"]["paper_1"]["backtest"]
    check("沒有逐月序列 → NO_SERIES", a70["repro"]["status"] == "NO_SERIES", a70["repro"])
    check("0050 回測段沒序列 → NO_SERIES", doc["bench_0050"]["backtest"]["repro"]["status"] == "NO_SERIES")
    oos = doc["lines"]["live_bb90"]["oos"]
    check("樣本外段逐月原樣搬", oos["monthly"] == {"2025-01": 0.01} and oos["cum_return"] == 0.2, oos)
    check("paper_4 只有回測段", list(doc["lines"]["paper_4"]) == ["backtest"])

    print("[2] 內容未變不重寫")
    before = out.read_bytes()
    code, err = run()
    check("第二輪不拋例外、檔案位元組不變（含 generated_at）", err is None and out.read_bytes() == before, (code, err))

    print("[3] 單一結果檔缺 → 只少那一段")
    out = setup(base, skip=("s3c6_oos_2025_result.json",))
    code, err = run()
    doc = json.loads(out.read_text(encoding="utf-8"))
    check("paper_3 少樣本外段、回測段照常、其他線不受影響", err is None and "oos" not in doc["lines"]["paper_3"]
          and "backtest" in doc["lines"]["paper_3"] and "oos" in doc["lines"]["live_bb90"], list(doc["lines"]["paper_3"]))

    print("[4] 逐月序列檔讀不到 → 全部 NO_SERIES、摘要照出")
    out = setup(base, mdoc=None)
    H.MONTHLY.write_text("{broken", encoding="utf-8")
    code, err = run()
    doc = json.loads(out.read_text(encoding="utf-8"))
    check("序列檔損壞不拋例外、回測段標 NO_SERIES", err is None
          and doc["lines"]["live_bb90"]["backtest"]["repro"]["status"] == "NO_SERIES", (code, err))

    print("[5] 結果檔全讀不到 → 不覆寫既有輸出")
    allf = ("core_allocation_result_unioncal.json", "bb90_oos_2025_result.json", "crisis_gate_timing_sensitivity_unioncal.json",
            "crisis_gate_leveraged_bb90_result_unioncal.json", "s3c6_oos_2025_result.json", "r1_0050_credit_gate_result_unioncal.json")
    out = setup(base, skip=allf, old_out='{"keep": 1}')
    code, err = run()
    check("不拋例外、exit 0（十二節只降級）", err is None and code == 0, (code, err))
    check("既有輸出不被全空內容覆寫", out.read_text(encoding="utf-8") == '{"keep": 1}', out.read_text(encoding="utf-8")[:80])

print(f"\n合計 {ok} 過 / {fail} 失敗")
sys.exit(1 if fail else 0)
