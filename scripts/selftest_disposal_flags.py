"""先.五十一-3 自測：build_disposal_flags.py 的上櫃落後交叉補、備援、過期剔除、日期解析。

全部用替身函式，不連網、不登入。跑法：python scripts/selftest_disposal_flags.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_disposal_flags as b  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{('  ' + detail) if detail and not cond else ''}")
    if not cond:
        FAILS.append(name)


NOW = datetime(2026, 10, 8, 18, 30, tzinfo=b.TW_TZ)


def sj(p_rows, n_rows, exch):
    def cols(rows, keys):
        return {k: [r.get(k) for r in rows] for k in keys}
    pk = ["code", "start_date", "end_date", "updated_at", "interval", "unit_limit", "total_limit",
          "description", "announced_date"]
    nk = ["code", "updated_at", "close", "reason", "announced_date"]
    return lambda: (cols(p_rows, pk), cols(n_rows, nk), exch)


def P(code, ann, s, e):
    return {"code": code, "announced_date": ann, "start_date": s, "end_date": e, "interval": "2分鐘",
            "unit_limit": 10.0, "total_limit": 30.0,
            "description": "１處置原因：連續三個營業日達標準。\r\n２處置期間：…"}


def N(code, ann):
    return {"code": code, "announced_date": ann, "close": 10.0, "reason": "漲幅達標"}


TPEX_D = {"5475": {"start": "2026-10-12", "end": "2026-10-16", "announced": "2026-10-08", "exchange": "OTC",
                   "source": "tpex_openapi"},
          "3441": {"start": "2026-01-01", "end": "2026-12-31", "announced": "2026-10-08", "exchange": "OTC",
                   "source": "tpex_openapi"}}
TPEX_N = {"3147": {"announced": "2026-10-08", "exchange": "OTC", "source": "tpex_openapi"}}


def boom():
    raise RuntimeError("down")


# 1. 日期解析
check("民國年 1151008 解析", b._roc_to_date("1151008") == date(2026, 10, 8))
check("民國年 115/10/08 解析", b._roc_to_date("115/10/08") == date(2026, 10, 8))
check("處置期間～分隔", b._period("115/10/08～115/10/15") == (date(2026, 10, 8), date(2026, 10, 15)))
check("處置期間~分隔", b._period("1151012~1151016") == (date(2026, 10, 12), date(2026, 10, 16)))
check("壞字串回 None", b._roc_to_date("N/A") is None and b._period("") == (None, None))
check("處置原因擷取", b._short_reason("１處置原因：連續三個營業日。\r\n２…") == "連續三個營業日。")
# 2. 交易日數（10/9 為國定假日、10/10-11 週末）
check("10/8→10/12 只算 1 個交易日（扣假日週末）", b.trading_days_between(date(2026, 10, 8), date(2026, 10, 12)) == 1)
check("10/5→10/8 算 3 個交易日", b.trading_days_between(date(2026, 10, 5), date(2026, 10, 8)) == 3)

# 3. 上櫃落後 ≤1 交易日：不補
out = b.build(NOW, sj([P("2330", date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 15)),
                       P("6708", date(2026, 10, 6), date(2026, 10, 6), date(2026, 10, 13))],
                      [N("2330", date(2026, 10, 8)), N("6708", date(2026, 10, 8))],
                      {"2330": "TSE", "6708": "OTC"}),
              tpex_d=lambda: dict(TPEX_D), tpex_n=lambda: dict(TPEX_N), twse_d=boom, twse_n=boom)
check("落後 1 交易日不補（5475 不應出現）", "5475" not in out["disposal"] and out["meta"]["supplemented"] == {},
      str(out["meta"]))
check("落後日數記錄為 1", out["meta"]["disposal_latest_announced"]["otc_lag_trading_days"] == 1)
check("每筆帶 source", all(v.get("source") for v in out["disposal"].values()))

# 4. 上櫃落後 >1 交易日：以 TPEx 補（只補缺，不蓋 Shioaji 已有的）
out = b.build(NOW, sj([P("2330", date(2026, 10, 8), date(2026, 10, 8), date(2026, 10, 15)),
                       P("3441", date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 19))],
                      [], {"2330": "TSE", "3441": "OTC"}),
              tpex_d=lambda: dict(TPEX_D), tpex_n=lambda: dict(TPEX_N), twse_d=boom, twse_n=boom)
check("落後 3 交易日 → 補入 5475", out["disposal"].get("5475", {}).get("source") == "tpex_openapi", str(out["meta"]))
check("已有的 3441 不被 TPEx 覆蓋", out["disposal"]["3441"]["source"] == "shioaji_punish")
check("補入原因寫進 meta", "落後" in out["meta"].get("disposal_supplement_reason", ""))
check("注意股上櫃無資料 → 補入 3147", "3147" in out["notice"] and out["meta"]["notice_supplement_reason"] == "Shioaji 上櫃無資料")

# 5. 過期剔除
out = b.build(NOW, sj([P("2030", date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 7)),
                       P("2033", date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 8))], [],
                      {"2030": "TSE", "2033": "TSE"}),
              tpex_d=lambda: {}, tpex_n=lambda: {}, twse_d=boom, twse_n=boom)
check("迄日已過剔除、迄日=今天保留", "2030" not in out["disposal"] and "2033" in out["disposal"])

# 6. Shioaji 失敗 → TWSE＋TPEx 備援
out = b.build(NOW, boom, tpex_d=lambda: dict(TPEX_D), tpex_n=lambda: dict(TPEX_N),
              twse_d=lambda: {"1709": {"start": "2026-10-08", "end": "2026-10-15", "announced": "2026-10-07",
                                       "exchange": "TSE", "source": "twse_openapi"}},
              twse_n=lambda: {})
check("備援：主來源標 fallback", out["meta"]["primary"] == "fallback_official_openapi")
check("備援：TWSE＋TPEx 都進來", {"1709", "5475"} <= set(out["disposal"]))
check("備援：失敗原因不靜默", any("Shioaji" in e for e in out["meta"]["errors"]))

# 7. 全部失敗 → None（不覆蓋舊檔）
check("全部來源失敗回 None", b.build(NOW, boom, tpex_d=boom, tpex_n=boom, twse_d=boom, twse_n=boom) is None)

# 8. TPEx 交叉補自己失敗只記錯誤、不中斷
out = b.build(NOW, sj([P("2330", date(2026, 10, 8), date(2026, 10, 8), date(2026, 10, 15))], [], {"2330": "TSE"}),
              tpex_d=boom, tpex_n=boom, twse_d=boom, twse_n=boom)
check("TPEx 失敗只降級成警告", out is not None and "2330" in out["disposal"] and out["meta"]["errors"])

print(f"\n{'全部通過' if not FAILS else f'{len(FAILS)} 項 FAIL'}")
sys.exit(1 if FAILS else 0)
