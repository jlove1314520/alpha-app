"""自測：「策略 vs 0050」曲線 `.github/scripts/build_strategy_curves.py`（先.一三五-1ck）。

DATA／RDATA／OUT 全部換成暫存目錄（假 picks_ledger、price_history 單檔、rf_monthly、紙上帳本）：零外部請求、
不讀也不動真實 data/ 與 research/data/。確認：
各線起始歸一 100、0050 灰線用還原權息（adj_close）、選股榜重疊組合法數字（進場費／出場費稅只扣一次、每批 1/5）、
紙上帳本建倉費從隔天反映、現金按定存利率計息、未開始的線只出佔位、缺價日沿用前一筆真實收盤（記錄既有行為）、
輸出內容未變不重寫、price_history／picks_ledger 讀不出來不覆寫既有 strategy_curves.json。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_strategy_curves", ROOT / ".github" / "scripts" / "build_strategy_curves.py")
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


CAL: list[str] = []
d = date(2026, 1, 5)
while len(CAL) < 12:
    if d.weekday() < 5:
        CAL.append(d.isoformat())
    d += timedelta(days=1)


def ph():
    return {"meta": {}, "prices": {
        # 0050：原始收盤固定 100，還原收盤逐日上升 → 灰線若用 close 會是平的
        "0050": [{"date": x, "close": 100.0, "adj_close": 90.0 + i} for i, x in enumerate(CAL)],
        "1101": [{"date": x, "close": 10.0 + i} for i, x in enumerate(CAL)],
        "1102": [{"date": x, "close": 20.0 + i} for i, x in enumerate(CAL) if i != 2],  # CAL[2] 缺價
    }}


def ledger():
    def snap(i, board="value"):
        return {"board": board, "snapshot_date": CAL[i], "taken_at": f"{CAL[i]}T00:10:00+08:00",
                "picks": [{"code": "1101", "entry_date": CAL[i], "entry_price": 10.0 + i}]}
    return {"meta": {}, "snapshots": [
        snap(0),
        {"board": "momentum", "snapshot_date": CAL[0], "taken_at": f"{CAL[0]}T00:10:00+08:00",
         "picks": [{"code": "1102", "entry_date": CAL[0], "entry_price": 20.0}]},
    ]}


RF = {"monthly": [{"date": "2026-01-01", "rf_rate_pct": 3.65}]}


def setup(base: Path, led=None, ph_raw=None, led_raw=None, old_out=None):
    data, rdata = base / "data", base / "research" / "data"
    data.mkdir(parents=True, exist_ok=True)
    rdata.mkdir(parents=True, exist_ok=True)
    (data / "price_history.json").write_text(ph_raw if ph_raw is not None else json.dumps(ph()), encoding="utf-8")
    (data / "picks_ledger.json").write_text(led_raw if led_raw is not None else json.dumps(led or ledger()), encoding="utf-8")
    (data / "rf_monthly.json").write_text(json.dumps(RF), encoding="utf-8")
    (data / "strategies.json").write_text(json.dumps({"strategies": []}), encoding="utf-8")
    (rdata / "paper_1b_log.jsonl").write_text(json.dumps(
        {"date": CAL[0], "event": "inception", "values_post": {"1101": 50.0, "CASH": 50.0}, "nav": 100.0,
         "rebalance_cost": 0.0}) + "\n", encoding="utf-8")
    out = data / "strategy_curves.json"
    if old_out is not None:
        out.write_text(old_out, encoding="utf-8")
    elif out.exists():
        out.unlink()
    B.DATA, B.RDATA, B.OUT = data, rdata, out
    return out


def run():
    try:
        return B.main(), None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def line(doc, id_):
    return next(x for x in doc["lines"] if x["id"] == id_)


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("[1] 正常產出")
    out = setup(base)
    code, err = run()
    check("正常執行不拋例外", err is None and code == 0, (code, err))
    doc = json.loads(out.read_text(encoding="utf-8"))
    v = line(doc, "board_value")
    check("估值榜起始歸一 100", v["nav"][0] == 100.0 and v["bench"][0] == 100.0, (v["nav"][:2], v["bench"][:2]))
    check("灰線用還原權息（adj 90→101）", abs(v["bench"][-1] - round(100 * 101.0 / 90.0, 4)) < 1e-9, v["bench"][-1])
    exp = [1.0]
    for j in range(1, len(CAL)):
        r = 0.0
        if 0 < j <= B.HOLD:
            r = (10.0 + j) / (10.0 + j - 1) - 1
            if j == 1:
                r = (1 + r) / (1 + B.FEE) - 1
            if j == B.HOLD:
                r = (1 + r) * (1 - B.FEE - B.STOCK_TAX) - 1
        exp.append(exp[-1] * (1 + r / B.HOLD))
    expn = [round(100 * x / exp[0], 4) for x in exp]
    check("重疊組合法：單批佔 1/5、進場費與出場費稅各一次", v["nav"] == expn, (v["nav"], expn))
    check("批次到期後曲線持平（現金不計息）", v["nav"][B.HOLD + 1] == v["nav"][-1])
    check("dates 與 0050 日曆對齊", v["dates"] == CAL)
    m = line(doc, "board_momentum")
    check("缺價日（1102 CAL[2]）不拋例外、曲線長度完整", len(m["nav"]) == len(CAL), len(m["nav"]))
    check("既有行為（記錄）：缺價日沿用前一筆真實收盤 → 該日報酬 0、隔日補上兩天漲幅",
          m["nav"][2] == m["nav"][1] and m["nav"][3] > m["nav"][2], m["nav"][:4])
    f = line(doc, "board_future")
    check("沒有快照的榜 → 佔位「還沒有資料」", f["started"] is False and f["nav"] == [] and f["note"] == "還沒有資料", f)
    p = line(doc, "paper_1b")
    check("紙上帳本起始歸一 100", p["nav"][0] == 100.0, p["nav"][:2])
    rf_d = (1 + 3.65 / 100) ** (1 / 365) - 1
    days1 = (date.fromisoformat(CAL[1]) - date.fromisoformat(CAL[0])).days
    exp1 = 50.0 * (1 - B.FEE) * (11.0 / 10.0) + 50.0 * (1 + rf_d) ** days1
    check("建倉費從隔天反映＋現金按定存利率計息", abs(p["nav"][1] - round(100 * exp1 / 100.0, 4)) < 1e-9, (p["nav"][1], exp1))
    p2 = line(doc, "paper_2")
    check("沒有帳本的紙上線 → 佔位、寫起始日", p2["started"] is False and p2["start_date"] == "2026-11-16", p2)
    lv = line(doc, "live_bb90")
    check("真錢線排程輸出只放佔位", lv["started"] is False and lv["nav"] == [])
    check("<60 日 verdict＝尚不足以判斷", v["metrics"]["verdict"] == "尚不足以判斷" and v["metrics"]["ci90_pp"] is None)
    check("meta.price_asof＝0050 最後一日", doc["meta"]["price_asof"] == CAL[-1])

    print("[2] 內容未變不重寫")
    before = out.read_bytes()
    code, err = run()
    check("第二輪不拋例外、檔案位元組不變（含 generated_at）", err is None and out.read_bytes() == before, (code, err))

    print("[3] price_history 讀不出來")
    B.PHS.time.sleep = lambda s: None  # 略過 _read 的重試等待（只影響本行程）
    out = setup(base, ph_raw="{broken", old_out='{"keep": 1}')
    code, err = run()
    check("不拋未處理例外", err is None, err)
    check("非零結束", code not in (0, None), code)
    check("既有曲線檔不被覆寫", out.read_text(encoding="utf-8") == '{"keep": 1}')

    print("[4] 0050 日線缺")
    p0 = ph()
    del p0["prices"]["0050"]
    out = setup(base, ph_raw=json.dumps(p0), old_out='{"keep": 2}')
    code, err = run()
    check("缺 0050 → 非零結束、不覆寫", err is None and code not in (0, None)
          and out.read_text(encoding="utf-8") == '{"keep": 2}', (code, err))

    print("[5] picks_ledger 讀不出來")
    out = setup(base, led_raw='{"snapshots": [ broken', old_out='{"keep": 3}')
    code, err = run()
    check("台帳損壞不拋未處理例外", err is None, err)
    check("台帳損壞非零結束、既有曲線檔不被覆寫（不把三榜改成「還沒有資料」）",
          code not in (0, None) and out.read_text(encoding="utf-8") == '{"keep": 3}', (code, out.read_text(encoding="utf-8")[:80]))
    out = setup(base, led_raw='[1, 2]', old_out='{"keep": 4}')
    code, err = run()
    check("台帳結構不對（陣列）→ 不覆寫", err is None and out.read_text(encoding="utf-8") == '{"keep": 4}', (code, err))

    print("[6] 台帳不存在（新環境）→ 照常產出佔位")
    out = setup(base)
    (B.DATA / "picks_ledger.json").unlink()
    code, err = run()
    doc = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    check("台帳不存在 → 三榜佔位、紙上線照算", err is None and code == 0
          and line(doc, "board_value")["started"] is False and line(doc, "paper_1b")["started"] is True, (code, err))

    print("[7] 紙上帳本有壞行")
    out = setup(base)
    with (B.RDATA / "paper_1b_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{broken\n")
    code, err = run()
    check("帳本壞行不拋例外、不拖垮其他線", err is None and code == 0
          and line(json.loads(out.read_text(encoding="utf-8")), "board_value")["started"] is True, (code, err))

print(f"\n合計 {ok} 過 / {fail} 失敗")
sys.exit(1 if fail else 0)
