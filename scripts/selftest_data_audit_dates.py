"""先.四十：資料稽核「同日比對」自測（合成資料，不連網、不寫 audit_report.json）。

重現 2026-10-05／10-06 兩晚 23:00 稽核的假違規：各資料檔更新時點不同——
quotes_tw.json 已是當天收盤、官方 TWSE 還停在前一日；官方 TPEx 已是當天、
quotes_all_tw.json／sparklines.json 還停在前一日。修正後這些日期不同的比對一律「無法查核」，
同一天價格真的對不上仍要報違規。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_audit as D  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def loc_for(qtw_date, qall_date, spark_asof, ph_last):
    return {
        "quotes_tw": {"1721": {"price": 29.0, "date": qtw_date}},
        "quotes_all": {"1721": {"close": 29.0 if qall_date == "2026-10-06" else 27.55, "date": qall_date}},
        "price_hist": {"1721": [{"date": "2026-10-05", "close": 27.55}] +
                       ([{"date": "2026-10-06", "close": 29.0}] if ph_last == "2026-10-06" else [])},
        "sparks": {"1721": [26.0, 26.5, 27.0, 27.2, 27.55] + ([29.0] if spark_asof == "2026-10-06" else [])},
        "sparks_stale_dates": {},
        "sparks_asof": spark_asof,
    }


def run(ref_date, ref_close, loc):
    a = D.Audit()
    ref = {"1721": {"close": ref_close, "date": ref_date}}
    D.check_a_price_sources(a, ["1721"], ref, {"1721": "三晃"}, loc)
    D.check_c_range(a, ["1721"], ref, {"1721": "三晃"}, loc)
    return [v for v in a.violations if v["check"] in ("a_price_source", "c_range")]


# 情境 1（10/6 23:00 的 TWSE 股）：官方停在 10/5（27.55），quotes_tw 已是 10/6（29.0），其餘檔還在 10/5
v = run("2026-10-05", 27.55, loc_for("20261006", "2026-10-05", "2026-10-05", "2026-10-05"))
check("官方落後一天、quotes_tw 已是當天：不報違規（無法查核）", not v)

# 情境 2（10/6 23:00 的 TPEx 股）：官方已是 10/6（29.0），quotes_all／sparklines／price_history 還在 10/5
v = run("2026-10-06", 29.0, loc_for("20261006", "2026-10-05", "2026-10-05", "2026-10-05"))
check("官方已是當天、quotes_all／走勢線落後一天：不報違規（含 c_range 單日大漲 >5%）", not v)

# 情境 3：全部都在同一天且一致 → 無違規
v = run("2026-10-06", 29.0, loc_for("20261006", "2026-10-06", "2026-10-06", "2026-10-06"))
check("全部同一天且一致：無違規", not v)

# 情境 4（防線仍有效）：同一天但 quotes_tw 價格錯 → 必須報違規
loc = loc_for("20261006", "2026-10-06", "2026-10-06", "2026-10-06")
loc["quotes_tw"]["1721"]["price"] = 40.0
v = run("2026-10-06", 29.0, loc)
check("同一天價格真的對不上：仍報 a_price_source 違規", any(x["check"] == "a_price_source" and x["source"] == "quotes_tw.json" for x in v))

# 情境 5（防線仍有效）：同一天走勢線與官方差 >5% → c_range 仍報
loc = loc_for("20261006", "2026-10-06", "2026-10-06", "2026-10-06")
loc["sparks"]["1721"] = [20.0, 20.1, 20.2, 20.3, 20.4, 20.5]
v = run("2026-10-06", 29.0, loc)
check("同一天走勢線視窗外 >5%：仍報 c_range 違規", any(x["check"] == "c_range" for x in v))

print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
