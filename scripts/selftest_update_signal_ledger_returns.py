"""自測：前瞻訊號台帳回填 `.github/scripts/update_signal_ledger_returns.py`（先.一三五-1cj）。

台帳／price_history（暫存單檔）換暫存路徑，`upl._fetch_taiex_history` 換假函式、yfinance 換會報錯的假模組：
零外部請求、不讀也不動真實 data/。確認：
進場＝寫入日之後第一個交易日收盤（寫入日當天不算）、只填 null 欄、已填欄位位元組不變、未到期留 null、
進場日停牌標 entry_skip_reason 且不回填、無價不補、過期價不猜、重跑冪等、沒有到期的就不抓大盤、
大盤失敗時超額留 null 且下輪只補超額、台帳讀不出來／沒有訊號不寫檔、price_history 讀不出來不拋未處理例外、
缺 meta／缺 returns 鍵不拖垮整輪。
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
_spec = importlib.util.spec_from_file_location("update_signal_ledger_returns",
                                               ROOT / ".github" / "scripts" / "update_signal_ledger_returns.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)
upl = S.upl

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
while len(CAL) < 70:
    s = d.isoformat()
    if d.weekday() < 5 and s != "2026-01-07":
        CAL.append(s)
    d += timedelta(days=1)
TAIEX = {day: 20000.0 + 10 * i for i, day in enumerate(CAL)}
TAIEX_CALLS: list[str] = []


def fake_taiex(start):
    TAIEX_CALLS.append(start)
    return dict(TAIEX)


def rows(price_fn, days):
    return [{"date": day, "close": price_fn(i)} for i, day in enumerate(CAL) if day in days]


def price_history():
    allday = set(CAL)
    return {"meta": {}, "prices": {
        "2330": rows(lambda i: 500.0 + i, allday),
        "1101": rows(lambda i: 100.0 + i, allday),
        "1102": rows(lambda i: 100.0 + i, allday - {CAL[21]}),   # 進場 CAL[1] 的 T+20 目標日停牌
        "1104": rows(lambda i: 50.0, allday - {CAL[1]}),         # 進場日停牌、之後有列
        "1107": rows(lambda i: 80.0, set(CAL[:2])),              # 只有到進場日；之後全無 → 過期
    }}


def sig(sid, code, rec_day, **extra):
    d = {"id": sid, "code": code, "recorded_at": f"{rec_day}T17:13:00+08:00",
         "returns": {"t5": None, "t20": None, "t60": None}}
    d.update(extra)
    return d


PRE_T5 = {"return_pct": 99.0, "excess_vs_taiex_pct": 1.0, "exit_date": "1999-01-01", "filled_at": "x"}


def ledger_doc(meta=True):
    sigs = [
        sig("s1", "1101", CAL[0]),
        sig("s2", "1101", CAL[68]),
        sig("s3", "1101", CAL[69]),
        sig("s4", "1101", CAL[0], entry_close=101.0, entry_date=CAL[1],
            returns={"t5": dict(PRE_T5), "t20": None, "t60": None}),
        sig("s5", "1104", CAL[0]),
        sig("s6", "1103", CAL[0]),
        sig("s7", "1102", CAL[0]),
        sig("s8", "1107", CAL[0]),
        {"id": "s9", "code": "1101", "recorded_at": f"{CAL[0]}T17:13:00+08:00", "entry_close": 101.0, "entry_date": CAL[1]},
    ]
    out = {"signals": sigs}
    if meta:
        out = {"meta": {"spec": "test"}, **out}
    return out


def setup(base: Path, led=None, ph=None, led_raw=None, ph_raw=None):
    (base / "data").mkdir(parents=True, exist_ok=True)
    lp, pp = base / "data" / "signal_ledger.json", base / "data" / "price_history.json"
    if led_raw is not None:
        lp.write_text(led_raw, encoding="utf-8")
    else:
        lp.write_text(json.dumps(led if led is not None else ledger_doc(), ensure_ascii=False), encoding="utf-8")
    if ph_raw is not None:
        pp.write_text(ph_raw, encoding="utf-8")
    else:
        pp.write_text(json.dumps(ph if ph is not None else price_history()), encoding="utf-8")
    S.LEDGER_PATH, upl.PRICE_HISTORY_PATH = lp, pp
    upl._fetch_taiex_history = fake_taiex
    TAIEX_CALLS.clear()
    return lp


def run():
    try:
        S.main()
        return 0, None
    except SystemExit as e:
        return (e.code if e.code is not None else 0), None
    except Exception as e:  # noqa: BLE001
        return None, e


def load(lp):
    return json.loads(lp.read_text(encoding="utf-8"))


def G(doc, sid):
    return next(x for x in doc["signals"] if x["id"] == sid)


def pct(a, b):
    return (b - a) / a * 100.0


with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    print("[1] 正常回填")
    lp = setup(base)
    code, err = run()
    check("正常執行不拋例外", err is None and code == 0, (code, err))
    doc = load(lp)
    s1 = G(doc, "s1")
    check("進場＝寫入日之後第一個交易日（寫入日當天不算）", s1.get("entry_date") == CAL[1] and s1.get("entry_close") == 101.0,
          (s1.get("entry_date"), s1.get("entry_close")))
    t5 = s1["returns"]["t5"] or {}
    check("T+5 跳過假休市、從進場日起數第 5 個交易日", t5.get("exit_date") == CAL[6], t5)
    check("T+5 報酬", abs(t5.get("return_pct", 0) - round(pct(101.0, 106.0), 4)) < 1e-9, t5)
    check("T+5 超額＝個股 − 大盤（同進出場日）",
          abs(t5.get("excess_vs_taiex_pct", 0) - round(pct(101.0, 106.0) - pct(TAIEX[CAL[1]], TAIEX[CAL[6]]), 4)) < 1e-9, t5)
    check("T+60 已到期照填", (s1["returns"]["t60"] or {}).get("exit_date") == CAL[61], s1["returns"]["t60"])
    s2 = G(doc, "s2")
    check("進場已填但未到 T+5 → 報酬全留 null", s2.get("entry_date") == CAL[69]
          and all(v is None for v in s2["returns"].values()), s2)
    s3 = G(doc, "s3")
    check("寫入日之後還沒有交易日 → 進場留 null", s3.get("entry_close") is None and "entry_skip_reason" not in s3)
    s4 = G(doc, "s4")
    check("已填 t5 位元組不變", s4["returns"]["t5"] == PRE_T5, s4["returns"]["t5"])
    check("同筆 null 的 t20 照填", s4["returns"]["t20"] is not None and s4["returns"]["t20"]["exit_date"] == CAL[21])
    check("已填進場價不改", s4["entry_close"] == 101.0 and s4["entry_date"] == CAL[1])
    s5 = G(doc, "s5")
    check("進場日停牌、之後有列 → 標 entry_skip_reason", s5.get("entry_skip_reason") == S.ENTRY_SKIP_REASON
          and s5.get("entry_close") is None, s5)
    check("停牌訊號不回填報酬", all(v is None for v in s5["returns"].values()))
    check("meta.entry_skipped 計數＝1", doc["meta"]["entry_skipped"]["count"] == 1, doc["meta"].get("entry_skipped"))
    s6 = G(doc, "s6")
    check("找不到價（無列）→ 不進場、不標停牌", s6.get("entry_close") is None and "entry_skip_reason" not in s6, s6)
    s7 = G(doc, "s7")
    w = s7["returns"]["t20"] or {}
    check("既有行為（疑慮已記錄）：出場日停牌時用 ≤10 天內前一筆收盤、exit_date 早於目標日",
          w.get("exit_date") == CAL[20], w)
    s8 = G(doc, "s8")
    check("過期價（>10 天）不猜 → 留 null", s8["returns"]["t20"] is None and s8["returns"]["t60"] is None, s8["returns"])
    s9 = G(doc, "s9")
    check("缺 returns 鍵 → 補齊並回填、不拖垮整輪", isinstance(s9.get("returns"), dict)
          and s9["returns"].get("t5") is not None, s9.get("returns"))
    check("大盤只抓一次", len(TAIEX_CALLS) == 1, TAIEX_CALLS)

    print("[2] 重跑冪等")
    snap = json.dumps(doc["signals"], sort_keys=True)
    code, err = run()
    doc2 = load(lp)
    check("第二輪不拋例外", err is None and code == 0, (code, err))
    check("第二輪所有訊號位元組不變（含 filled_at／停牌標記時間）", json.dumps(doc2["signals"], sort_keys=True) == snap)

    print("[3] 沒有到期 → 不抓大盤、無新進場就不寫檔")
    led = {"meta": {}, "signals": [sig("x", "1101", CAL[69])]}
    lp = setup(base, led=led)
    raw = lp.read_bytes()
    code, err = run()
    check("不抓大盤", TAIEX_CALLS == [], TAIEX_CALLS)
    check("無變動不寫檔", err is None and lp.read_bytes() == raw, (code, err))

    print("[4] 台帳讀不出來／沒有訊號")
    lp = setup(base, led_raw='{"signals": [ broken')
    raw = lp.read_bytes()
    code, err = run()
    check("台帳損壞不拋未處理例外、不覆寫", err is None and lp.read_bytes() == raw, (code, err))
    lp = setup(base, led={"meta": {}, "signals": []})
    raw = lp.read_bytes()
    code, err = run()
    check("沒有訊號不寫檔", err is None and lp.read_bytes() == raw, (code, err))

    print("[5] price_history 讀不出來")
    upl.PHS.time.sleep = lambda s: None  # 略過 _read 的重試等待（只影響本行程）
    lp = setup(base, ph_raw="{broken")
    raw = lp.read_bytes()
    code, err = run()
    check("價格檔損壞不拋未處理例外", err is None, err)
    check("價格檔損壞以非零結束", code not in (0, None), code)
    check("價格檔損壞不寫台帳", lp.read_bytes() == raw)

    print("[6] 台帳缺 meta")
    lp = setup(base, led=ledger_doc(meta=False))
    code, err = run()
    check("缺 meta 不拋例外、照常回填", err is None and code == 0
          and G(load(lp), "s1")["returns"]["t5"] is not None, (code, err))

    print("[7] 大盤抓取失敗 → 報酬照填、超額留 null，下輪只補超額")
    lp = setup(base)
    upl._fetch_taiex_history = lambda start: {}
    run()
    a = G(load(lp), "s1")["returns"]["t5"]
    check("超額留 null、報酬照填", a["excess_vs_taiex_pct"] is None and a["return_pct"] is not None, a)
    upl._fetch_taiex_history = fake_taiex
    run()
    b = G(load(lp), "s1")["returns"]["t5"]
    check("下輪補超額、報酬與 filled_at 不變", b["excess_vs_taiex_pct"] is not None
          and b["return_pct"] == a["return_pct"] and b["filled_at"] == a["filled_at"], b)

print(f"\n合計 {ok} 過 / {fail} 失敗")
sys.exit(1 if fail else 0)
