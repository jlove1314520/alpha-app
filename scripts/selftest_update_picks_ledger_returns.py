"""自測：前瞻選股台帳回填 `.github/scripts/update_picks_ledger_returns.py`（先.一三五-1ci）。

台帳／price_history（暫存單檔）全部換成暫存路徑，`^TWII` 抓取換成假函式、yfinance 換成會報錯的假模組：
零外部請求、不讀也不動真實 data/。確認：
T+N 用交易日數（跳過休市）、進場＝taken_at 之後第一個收盤、未到期留 null、已填欄位不改（只補 excess null）、
出場日缺價不拿前一天頂替、過期（>10 天）價不猜、找不到價不補、重跑冪等、
台帳讀不出來不寫檔、price_history 讀不出來不寫檔（不拋未處理例外）、pick 缺 returns 鍵不拖垮整輪。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


class _NoNet:
    def __init__(self, *a, **k):
        raise RuntimeError("自測禁止外部請求（yfinance）")


sys.modules["yfinance"] = types.SimpleNamespace(Ticker=_NoNet)
_spec = importlib.util.spec_from_file_location("update_picks_ledger_returns",
                                               ROOT / ".github" / "scripts" / "update_picks_ledger_returns.py")
U = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(U)

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


# 交易日曆：2026-01-05 起的平日，跳過 2026-01-07（假休市），共 70 個交易日 → T+60 到得了、T+120 未到期
CAL: list[str] = []
d = date(2026, 1, 5)
while len(CAL) < 70:
    s = d.isoformat()
    if d.weekday() < 5 and s != "2026-01-07":
        CAL.append(s)
    d += timedelta(days=1)
TAIEX = {day: 20000.0 + 10 * i for i, day in enumerate(CAL)}


def rows(price_fn, days):
    return [{"date": day, "close": price_fn(i)} for i, day in enumerate(CAL) if day in days]


def price_history():
    allday = set(CAL)
    return {"meta": {}, "prices": {
        "2330": rows(lambda i: 500.0 + i, allday),
        "1101": rows(lambda i: 100.0 + i, allday),
        "1102": rows(lambda i: 100.0 + i, allday - {CAL[20]}),     # T+20 出場日停牌
        "1104": rows(lambda i: 50.0, allday - {CAL[0]}),           # 進場日沒有收盤
        "1105": rows(lambda i: 100.0 + i, allday),
        "1106": rows(lambda i: 80.0, set(CAL[:4])),                # 第 3 個交易日後就沒價
        "1107": rows(lambda i: 80.0, {CAL[0]}),                    # 只有進場日；T+20 起的最近價 >10 天
        "1108": rows(lambda i: 10.0 + i, allday),
    }}


def pick(code, returns=None):
    return {"code": code, "name": code, "close_price": 1.0, "price_date": "2026-01-02",
            "returns": returns if returns is not None else {"t5": None, "t20": None, "t60": None, "t120": None}}


PRE_T5 = {"return_pct": 99.0, "excess_vs_taiex_pct": 1.0, "exit_date": "1999-01-01", "filled_at": "x"}


def ledger_doc(rule=True):
    meta = {"returns_anchor_rule": U.ANCHOR_RULE} if rule else {}
    p1105 = pick("1105", {"t5": dict(PRE_T5),
                          "t20": {"return_pct": 3.0, "excess_vs_taiex_pct": None, "exit_date": CAL[20]},
                          "t60": None, "t120": None})
    p1108 = {"code": "1108", "name": "缺returns鍵"}
    return {"meta": meta, "snapshots": [
        {"snapshot_date": "2026-01-05", "taken_at": "2026-01-05T00:10:00+08:00", "board": "value",
         "picks": [pick("1101"), pick("1102"), pick("1103"), pick("1104"), p1105, pick("1106"), pick("1107"), p1108]},
        {"snapshot_date": "2026-01-05", "taken_at": "2026-01-05T14:00:00+08:00", "board": "momentum",
         "picks": [pick("1101")]},
        {"snapshot_date": "2026-12-31", "taken_at": "2026-12-31T00:10:00+08:00", "board": "future",
         "picks": [pick("1101")]},
    ]}


def setup(base: Path, led=None, ph=None, led_raw=None, ph_raw=None):
    (base / "data").mkdir(parents=True, exist_ok=True)
    lp, pp = base / "data" / "picks_ledger.json", base / "data" / "price_history.json"
    if led_raw is not None:
        lp.write_text(led_raw, encoding="utf-8")
    else:
        lp.write_text(json.dumps(led if led is not None else ledger_doc(), ensure_ascii=False), encoding="utf-8")
    if ph_raw is not None:
        pp.write_text(ph_raw, encoding="utf-8")
    else:
        pp.write_text(json.dumps(ph if ph is not None else price_history()), encoding="utf-8")
    U.LEDGER_PATH, U.PRICE_HISTORY_PATH = lp, pp
    U._fetch_taiex_history = lambda start: dict(TAIEX)
    return lp


def run():
    try:
        U.main()
        return 0, None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def load(lp):
    return json.loads(lp.read_text(encoding="utf-8"))


def P(doc, si, code):
    return next(p for p in doc["snapshots"][si]["picks"] if p["code"] == code)


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("[1] 正常回填")
    lp = setup(base)
    code, err = run()
    check("正常執行不拋例外", err is None and code == 0, (code, err))
    doc = load(lp)
    a = P(doc, 0, "1101")
    check("進場＝taken_at 00:10 當天收盤", a.get("entry_date") == CAL[0] and a.get("entry_price") == 100.0, a.get("entry_date"))
    check("T+5 用交易日數、跳過 01-07 休市 → 01-13", (a["returns"]["t5"] or {}).get("exit_date") == "2026-01-13",
          a["returns"]["t5"])
    check("T+5 報酬＝5%", abs(a["returns"]["t5"]["return_pct"] - 5.0) < 1e-9, a["returns"]["t5"])
    check("T+5 超額＝5 − 0.25", abs(a["returns"]["t5"]["excess_vs_taiex_pct"] - 4.75) < 1e-9, a["returns"]["t5"])
    check("T+20／T+60 出場日＝第 20／60 個交易日",
          a["returns"]["t20"]["exit_date"] == CAL[20] and a["returns"]["t60"]["exit_date"] == CAL[60])
    check("持有天數欄位＝N", a["returns"]["t60"]["holding_trading_days"] == 60)
    check("T+120 未到期留 null", a["returns"]["t120"] is None)
    b = P(doc, 1, "1101")
    check("taken_at 14:00（收盤後）→ 進場改下一個交易日", b.get("entry_date") == CAL[1], b.get("entry_date"))
    check("下午快照 T+5 從進場日起算", b["returns"]["t5"]["exit_date"] == CAL[6], b["returns"]["t5"])
    c = P(doc, 2, "1101")
    check("快照之後還沒收盤 → 不進場、全 null", "entry_price" not in c and all(v is None for v in c["returns"].values()))
    check("未進場的快照不標 data_status", "data_status" not in doc["snapshots"][2])
    p2 = P(doc, 0, "1102")
    check("T+20 出場日停牌 → 留 null（不拿前一天頂替）", p2["returns"]["t20"] is None, p2["returns"]["t20"])
    check("同檔其他期別照填", p2["returns"]["t5"] is not None and p2["returns"]["t60"] is not None)
    p3 = P(doc, 0, "1103")
    check("找不到價（無列）→ 不進場、全 null", "entry_price" not in p3 and all(v is None for v in p3["returns"].values()))
    p4 = P(doc, 0, "1104")
    check("進場日沒收盤 → 不用別天價格進場", "entry_price" not in p4 and all(v is None for v in p4["returns"].values()))
    p5 = P(doc, 0, "1105")
    check("已填 t5 位元組不變", p5["returns"]["t5"] == PRE_T5, p5["returns"]["t5"])
    check("已填 t20 只補 excess null（3.0 − 1.0）", p5["returns"]["t20"].get("excess_vs_taiex_pct") == 2.0
          and p5["returns"]["t20"]["return_pct"] == 3.0, p5["returns"]["t20"])
    p6 = P(doc, 0, "1106")
    check("出場日附近沒價（最近價在幾天前）→ 不猜", p6["returns"]["t5"] is None, p6["returns"]["t5"])
    p7 = P(doc, 0, "1107")
    check("價格過期 >10 天 → 不猜", p7["returns"]["t20"] is None and p7["returns"]["t60"] is None)
    check("過期價查詢函式回 stale", U._lookup_price_on("1107", CAL[20], price_history()["prices"]) == (None, None, True))
    p8 = P(doc, 0, "1108")
    check("pick 缺 returns 鍵 → 補齊並回填、不拖垮整輪", isinstance(p8.get("returns"), dict)
          and p8["returns"].get("t5") is not None, p8.get("returns"))
    ds = doc["snapshots"][0]["data_status"]
    check("缺價批次標 complete=false", ds["complete"] is False and ds["missing_entry"] >= 2, ds)
    check("沒有觸發一次性重算（規則已是 v2）", doc["meta"]["returns_anchor_rule"] == U.ANCHOR_RULE
          and "returns_recomputed_at" not in doc["meta"])

    print("[2] 重跑冪等")
    before = {(si, p["code"]): json.dumps(p.get("returns"), sort_keys=True)
              for si, s in enumerate(doc["snapshots"]) for p in s["picks"]}
    code, err = run()
    doc2 = load(lp)
    after = {(si, p["code"]): json.dumps(p.get("returns"), sort_keys=True)
             for si, s in enumerate(doc2["snapshots"]) for p in s["picks"]}
    check("第二輪不拋例外", err is None and code == 0, (code, err))
    check("第二輪所有 returns 位元組不變（含 filled_at）", before == after)

    print("[3] T+N 函式邊界")
    check("anchor 不在日曆 → None", U._trading_days_after("2026-01-07", 5, CAL) is None)
    check("超出日曆 → None", U._trading_days_after(CAL[0], 120, CAL) is None)
    check("taken_at 缺 → None", U._entry_day_after(None, CAL) is None)
    check("taken_at 格式壞 → None", U._entry_day_after("not-a-date", CAL) is None)

    print("[4] 台帳讀不出來")
    lp = setup(base, led_raw='{"snapshots": [ broken')
    raw = lp.read_bytes()
    code, err = run()
    check("台帳損壞不拋未處理例外", err is None, err)
    check("台帳損壞不覆寫（位元組不變）", lp.read_bytes() == raw)

    print("[5] price_history 讀不出來")
    U.PHS.time.sleep = lambda s: None  # 略過 _read 的重試等待（只影響本行程）
    lp = setup(base, ph_raw="{broken")
    raw = lp.read_bytes()
    code, err = run()
    check("價格檔損壞不拋未處理例外", err is None, err)
    check("價格檔損壞以非零結束", code not in (0, None), code)
    check("價格檔損壞不寫台帳", lp.read_bytes() == raw)

    print("[6] price_history 空 → 不回填不寫檔")
    lp = setup(base, ph={"meta": {}, "prices": {}})
    raw = lp.read_bytes()
    code, err = run()
    check("空價格檔不拋例外、台帳不變", err is None and lp.read_bytes() == raw, (code, err))

    print("[7] 大盤抓取失敗 → 報酬照填、超額留 null")
    lp = setup(base)
    U._fetch_taiex_history = lambda start: {}
    code, err = run()
    a = P(load(lp), 0, "1101")
    check("超額留 null、報酬照填", a["returns"]["t5"]["return_pct"] == 5.0
          and a["returns"]["t5"]["excess_vs_taiex_pct"] is None, a["returns"]["t5"])
    U._fetch_taiex_history = lambda start: dict(TAIEX)
    code, err = run()
    a2 = P(load(lp), 0, "1101")
    check("下一輪大盤恢復 → 只補 excess、報酬與 filled_at 不變",
          a2["returns"]["t5"]["excess_vs_taiex_pct"] == 4.75
          and a2["returns"]["t5"]["filled_at"] == a["returns"]["t5"]["filled_at"], a2["returns"]["t5"])

    print("[8] 舊規則台帳（meta 無 anchor_rule）→ 一次性重算（既有設計，記錄行為）")
    led = ledger_doc(rule=False)
    lp = setup(base, led=led)
    code, err = run()
    doc = load(lp)
    p5 = P(doc, 0, "1105")
    check("舊規則：已填欄位被清空後依新規則重填", p5["returns"]["t5"] != PRE_T5
          and p5["returns"]["t5"]["exit_date"] == "2026-01-13", p5["returns"]["t5"])
    check("重算後寫入 anchor_rule", doc["meta"].get("returns_anchor_rule") == U.ANCHOR_RULE)

print(f"\n合計 {ok} 過 / {fail} 失敗")
sys.exit(1 if fail else 0)
