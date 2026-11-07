"""先.一三五-1mt 自測：a_price_source 無法查核拆解（市場｜檔案｜原因）加總＝unverifiable，checked／violations 不受影響。零外部請求。"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_audit as da  # noqa: E402

ref = {
    "1111": {"close": 10.0, "date": "1151105", "board": "TWSE"},   # 官方舊一天、快照新一天
    "2222": {"close": 20.0, "date": "2026-11-06", "board": "TPEx"}, # 同一天、不在 quotes_tw
    "3333": {"close": 30.0, "date": "2026-11-06", "board": "TPEx"}, # 同一天、quotes_all 過期
}
loc = {
    "price_hist": {"1111": [{"date": "2026-11-05", "close": 10.0}, {"date": "2026-11-06", "close": 11.0}],
                   "2222": [{"date": "2026-11-06", "close": 20.0}],
                   "3333": [{"date": "2026-11-05", "close": 29.0}]},
    "quotes_tw": {"1111": {"price": 11.0, "date": "20261106"}, "3333": {"price": 30.0, "date": "20261106"}},
    "quotes_all": {"1111": {"close": 11.0, "date": "2026-11-06"}, "2222": {"close": 20.0, "date": "2026-11-06"},
                   "3333": {"close": 29.0, "date": "2026-11-05", "is_stale": True}},
    "sparks": {"1111": [11.0], "2222": [20.0], "3333": [30.0]},
    "sparks_stale_dates": {}, "sparks_asof": "2026-11-06",
}
a = da.Audit()
fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


da.A_PRICE_SOURCE_UNVERIFIABLE.clear()
da.check_a_price_sources(a, sorted(ref), ref, {}, loc)
bc = a.stats.get("a_price_source")
bd = da.A_PRICE_SOURCE_UNVERIFIABLE
print(bc); [print("  ", k, v) for k, v in bd.items()]
check("拆解加總＝unverifiable", bc is not None and sum(bd.values()) == bc["unverifiable"])
check("TWSE 三個快照檔標快照日期≠官方參考日", sum(v for k, v in bd.items() if k.startswith("TWSE｜") and "快照日期≠官方參考日" in k) == 3)
check("TPEx quotes_tw 沒有這檔", bd.get("TPEx｜quotes_tw.json｜quotes_tw 沒有這檔（只含自選／觀察清單）") == 1)
check("price_history 沒有官方參考日那天（3333 只有 11/05）", bd.get("TPEx｜price_history.json｜price_history 沒有官方參考日那天") == 1)
check("checked 數正確（1111 歷史1＋2222 三檔＋3333 quotes_tw／sparklines 2）", bc["checked"] == 6)
print("全部通過" if not fails else f"{fails} 項失敗")
sys.exit(1 if fails else 0)
