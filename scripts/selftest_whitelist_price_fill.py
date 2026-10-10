# -*- coding: utf-8 -*-
"""先.五十八-A2 自測：update_price_history.py 的白名單三檔（0050、00646、00697B）補缺。

檢查：①全市場端點漏當日 → 用單股端點補上並標 source ②單股端點也查不到 → 狀態 ok=False 且有警告文字
③不覆蓋既有列 ④單股端點拋例外 → 不往外拋、記進 errors ⑤上市前的日子不當缺漏 ⑥全部齊全 → 不發請求。
用假的 fetcher，不呼叫任何網路 API。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location("uph", ROOT / ".github" / "scripts" / "update_price_history.py")
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def row(d, c, src=None):
    r = {"date": d, "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1.0, "turnover": c}
    if src:
        r["source"] = src
    return r


DAYS = ["2026-10-02", "2026-10-03", "2026-10-06", "2026-10-07", "2026-10-08"]
TARGET = {"twse": "2026-10-08", "tpex": "2026-10-08"}


def base_prices():
    return {"0050": [row(d, 100.0) for d in DAYS],
            "00646": [row(d, 50.0) for d in DAYS[:-1]],          # 漏當日
            "00697B": [row(d, 30.0) for d in DAYS if d != "2026-10-06"]}   # 漏中間一天＋…


calls = []


def fake_twse(code, ym):
    calls.append(("twse", code, ym))
    return [row(d, 51.0, "twse_stock_day") for d in DAYS]


def fake_tpex(code, ym):
    calls.append(("tpex", code, ym))
    return [row(d, 31.0, "tpex_trading_stock") for d in DAYS]


# ① 補上當日與中間缺日，標 source
px = base_prices()
st = U.fill_whitelist_gaps(px, TARGET, DAYS, {"twse": fake_twse, "tpex": fake_tpex}, sleep_sec=0)
check("00646 補上當日 2026-10-08", st["codes"]["00646"]["filled"] == ["2026-10-08"])
check("00646 補上的列標 source=twse_stock_day", px["00646"][-1].get("source") == "twse_stock_day")
check("00697B 補上中間缺日 2026-10-06", st["codes"]["00697B"]["filled"] == ["2026-10-06"])
check("全部 ok、無警告", st["all_ok"] and st["warning"] is None)
check("0050 齊全 → 不發請求", not any(c[1] == "0050" for c in calls))

# ③ 不覆蓋既有列（00646 既有 10-07 收盤 50，假端點回 51）
check("既有列不被覆蓋（00646 10-07 仍為 50）",
      next(r for r in px["00646"] if r["date"] == "2026-10-07")["close"] == 50.0)

# ② 單股端點也查不到 → 警告
px = base_prices()
st = U.fill_whitelist_gaps(px, TARGET, DAYS, {"twse": lambda c, ym: [], "tpex": lambda c, ym: []}, sleep_sec=0)
check("補不到 → 00646 ok=False 並列出缺日", (not st["codes"]["00646"]["ok"]) and st["codes"]["00646"]["missing"] == ["2026-10-08"])
check("補不到 → all_ok=False 且警告文字含代號", (not st["all_ok"]) and "00646" in (st["warning"] or ""))


# ④ 單股端點拋例外 → 不往外拋
def boom(code, ym):
    raise RuntimeError("HTTP 500")


px = base_prices()
try:
    st = U.fill_whitelist_gaps(px, TARGET, DAYS, {"twse": boom, "tpex": boom}, sleep_sec=0)
    check("端點例外不往外拋、記進 errors", bool(st["codes"]["00646"]["errors"]) and not st["all_ok"])
except Exception as e:  # noqa: BLE001
    check(f"端點例外不往外拋（實際拋了 {type(e).__name__}）", False)

# ⑤ 上市前的日子不當缺漏：00697B 只有 10-07 起的資料
px = {"0050": [row(d, 100.0) for d in DAYS], "00646": [row(d, 50.0) for d in DAYS],
      "00697B": [row("2026-10-07", 30.0), row("2026-10-08", 30.0)]}
st = U.fill_whitelist_gaps(px, TARGET, DAYS, {"twse": lambda c, ym: [], "tpex": lambda c, ym: []}, sleep_sec=0)
check("上市前的日子不當缺漏（00697B ok）", st["codes"]["00697B"]["ok"] and not st["codes"]["00697B"]["missing"])

# ⑥ target 為 None（本輪全市場端點失敗）→ 只檢查最近交易日，不因 None 誤判
px = base_prices()
st = U.fill_whitelist_gaps(px, {"twse": None, "tpex": None}, DAYS[:3], {"twse": fake_twse, "tpex": fake_tpex}, sleep_sec=0)
check("target=None 不拋例外、只補最近交易日缺漏（00697B 補 10-06，00646 不追當日）",
      st["codes"]["00697B"]["filled"] == ["2026-10-06"] and st["codes"]["00646"]["ok"] and not st["codes"]["00646"]["filled"])

# ⑦ 內部壞資料（列缺 date）→ 不往外拋
try:
    st = U.fill_whitelist_gaps({"0050": [{"close": 1}]}, TARGET, DAYS, {"twse": boom, "tpex": boom}, sleep_sec=0)
    check("壞資料不往外拋、判 ok=False", not st["all_ok"])
except Exception as e:  # noqa: BLE001
    check(f"壞資料不往外拋（實際拋了 {type(e).__name__}）", False)

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
