# -*- coding: utf-8 -*-
"""維護「目前真的還在市」的股票清單 data/listed_universe.json（2026-09-06 稽核.一）。

**為什麼需要這支**
全市場稽核跑出來的第一份報告發現：本地資料檔裡有 401 個代號今天完全不在官方
全市場快照裡，其中 **69 檔還出現在 App 的選股排行榜上**，帶著 2010～2024 年的
舊價格——例如矽品 2325（2018 年被日月光合併下市）、勝華 2384（2014 年下市）、
神達 2315（2013 年改組）。App 因此會把早就不存在的股票排進推薦名單，而且顯示
一個十幾年前的價格當「現價」。這是「光聖 6442 顯示 32」的同一類錯誤：一個不該
出現的數字，沒有任何一道關卡攔它。

**做法**
每天取四個官方端點的聯集當「今天看得到的代號」：
  1. 今天有成交的：TWSE STOCK_DAY_ALL、TPEx 主板報價
  2. 掛牌名冊（涵蓋今天完全沒成交的）：TWSE t187ap03_L、TPEx mopsfin_t187ap03_O
然後**累積維護** last_seen（不是每天砍掉重來）——停牌、全天無成交、暫停交易都會
讓一檔股票某幾天不在快照裡，如果只看當天就會把正常的股票誤判成下市。只有連續
`INACTIVE_DAYS` 天沒被看到才標成 inactive。

輸出 `data/listed_universe.json`：
  {meta:{...}, active:[代號], inactive:[代號], last_seen:{代號:日期}}

用法：`python scripts/build_listed_universe.py`
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from data_audit import (  # noqa: E402  共用同一套 TLS 設定與逗號安全解析
    TPEX_QUOTES, TWSE_COMPANY, TWSE_STOCK_DAY_ALL,
    is_stock_code, make_session, num,
)

# 上櫃公司掛牌名冊。只靠「今天有成交」會漏掉當天完全沒成交的上櫃股，
# 名冊補上這一塊，跟上市的 t187ap03_L 是對稱的。
TPEX_ROSTER = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
# 2026-10-09（先.五十六-A1）：官方停止交易清單。TPEx「上櫃股票變更交易、分盤交易、管理股票與停止交易資訊」
# （SuspensionOfTrading=Ｙ）；TWSE「集中市場暫停交易證券」（TradingHaltDate／TradingResumptionDate）。
TPEX_CMODE = "https://www.tpex.org.tw/openapi/v1/tpex_cmode"
TWSE_TWTAWU = "https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU"

OUT = ROOT / "data" / "listed_universe.json"
TZ = timezone(timedelta(hours=8))
INACTIVE_DAYS = 30  # 連續 30 天沒在任何官方名冊/快照出現才判定為不在市


def collect_today(sess) -> tuple[set[str], dict]:
    seen: set[str] = set()
    meta: dict = {}

    def add(codes, key, extra=None):
        n = 0
        for c in codes:
            if is_stock_code(c):
                seen.add(c)
                n += 1
        meta[key] = {"ok": True, "usable": n, **(extra or {})}

    try:
        rows = sess.get(TWSE_STOCK_DAY_ALL, timeout=90).json()
        add([str(r.get("Code", "")).strip() for r in rows
             if num(r.get("ClosingPrice")) is not None], "twse_quotes", {"rows": len(rows)})
    except Exception as e:
        meta["twse_quotes"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        rows = sess.get(TPEX_QUOTES, timeout=90).json()
        add([str(r.get("SecuritiesCompanyCode", "")).strip() for r in rows
             if num(r.get("Close")) is not None], "tpex_quotes", {"rows": len(rows)})
    except Exception as e:
        meta["tpex_quotes"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        rows = sess.get(TWSE_COMPANY, timeout=90).json()
        add([str(r.get("公司代號", "")).strip() for r in rows], "twse_roster", {"rows": len(rows)})
    except Exception as e:
        meta["twse_roster"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    try:
        rows = sess.get(TPEX_ROSTER, timeout=90).json()
        add([str(r.get("SecuritiesCompanyCode", "")).strip() for r in rows], "tpex_roster",
            {"rows": len(rows)})
    except Exception as e:
        meta["tpex_roster"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return seen, meta


def _roc(d) -> str | None:
    """民國日期字串（1151008）→ 2026-10-08；轉不出來回 None，不猜。"""
    t = str(d or "").strip()
    if len(t) == 7 and t.isdigit():
        return f"{int(t[:3]) + 1911:04d}-{t[3:5]}-{t[5:]}"
    return None


def collect_suspended(sess, today: str) -> tuple[dict, dict]:
    """官方停止交易中的代號 → {trading_status, source, since}；以及各來源 meta。"""
    out: dict = {}
    meta: dict = {}
    try:
        rows = sess.get(TPEX_CMODE, timeout=90).json()
        n = 0
        for r in rows:
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            flag = str(r.get("SuspensionOfTrading", "")).strip()
            if is_stock_code(code) and flag in ("Ｙ", "Y"):
                # tpex_cmode 的 Date 是資料日期，不是停止交易起日，存成 as_of
                out[code] = {"trading_status": "SUSPENDED_OFFICIAL", "source": "TPEx tpex_cmode",
                             "as_of": _roc(r.get("Date"))}
                n += 1
        meta["tpex_cmode"] = {"ok": True, "rows": len(rows), "suspended": n}
    except Exception as e:
        meta["tpex_cmode"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    try:
        rows = sess.get(TWSE_TWTAWU, timeout=90).json()
        n = 0
        for r in rows:
            code = str(r.get("Code", "")).strip()
            halt, resume = _roc(r.get("TradingHaltDate")), _roc(r.get("TradingResumptionDate"))
            if is_stock_code(code) and halt and halt <= today and (not resume or resume > today):
                out[code] = {"trading_status": "SUSPENDED_OFFICIAL", "source": "TWSE TWTAWU", "since": halt}
                n += 1
        meta["twse_twtawu"] = {"ok": True, "rows": len(rows), "suspended": n}
    except Exception as e:
        meta["twse_twtawu"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return out, meta


def main() -> int:
    today = datetime.now(TZ).date().isoformat()
    sess = make_session()
    seen, meta = collect_today(sess)

    ok_sources = [k for k, v in meta.items() if v.get("ok")]
    if not seen or not ok_sources:
        # 一份都沒抓到就直接放棄，不要寫出一份「今天全世界都下市了」的檔案
        print("！所有官方來源都失敗，不更新 listed_universe.json（保留既有檔案）")
        for k, v in meta.items():
            print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
        return 2

    prev = {}
    prev_susp = {}
    if OUT.exists():
        try:
            _old = json.loads(OUT.read_text(encoding="utf-8"))
            prev = _old.get("last_seen", {})
            prev_susp = _old.get("suspended", {}) or {}
        except Exception as e:
            print(f"  ! 舊檔讀不到，重新開始累積：{type(e).__name__} {e}")
    suspended, susp_meta = collect_suspended(sess, today)
    # 某個來源抓不到時沿用該來源上一份標記（標 stale），不把停止交易股誤判成「恢復」
    for src_key, src_name in (("tpex_cmode", "TPEx tpex_cmode"), ("twse_twtawu", "TWSE TWTAWU")):
        if not susp_meta.get(src_key, {}).get("ok"):
            for c, v in prev_susp.items():
                if v.get("source") == src_name and c not in suspended:
                    suspended[c] = {**v, "stale": True}
    meta.update(susp_meta)

    last_seen = dict(prev)
    for c in seen:
        last_seen[c] = today

    cutoff = (datetime.now(TZ).date() - timedelta(days=INACTIVE_DAYS)).isoformat()
    active = sorted(c for c, d in last_seen.items() if d >= cutoff)
    inactive = sorted(c for c, d in last_seen.items() if d < cutoff)

    OUT.write_text(json.dumps({
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "sources": meta,
            "inactive_after_days": INACTIVE_DAYS,
            "note": "active＝近 30 天內曾出現在官方快照或掛牌名冊；inactive＝超過 30 天沒出現，"
                    "視為已下市/暫停交易，不得進入選股排行或顯示現價",
        },
        "active": active,
        "inactive": inactive,
        "last_seen": last_seen,
        "suspended": dict(sorted(suspended.items())),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"今日官方可見代號 {len(seen)} 檔（來源：{'、'.join(ok_sources)}）")
    print(f"active {len(active)} 檔、inactive {len(inactive)} 檔、官方停止交易 {len(suspended)} 檔 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
