# -*- coding: utf-8 -*-
"""先.八十一-57（2026-10-13）：在市名冊「疑似停止交易／官方終止上市」自測（假的官方回應，不打網路、不寫真檔）。
① 名冊還在、連續 ≥5 個交易日不在收盤快照 → suspected_halt  ② 只缺 2 個交易日 → 不標
③ 近 365 天終止上市且今天沒有收盤價 → DELISTED_OFFICIAL  ④ 很久以前終止上市（代號被沿用）→ 不標
⑤ 上櫃歷史最後一筆是暫停 → SUSPENDED_OFFICIAL；最後一筆是恢復 → 不標
⑥ 任一收盤快照抓失敗 → last_quoted 不更新、不判疑似（免得整個市場被誤判）
用法：python scripts/selftest_listed_universe_suspect.py
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import build_listed_universe as B  # noqa: E402

TW = timezone(timedelta(hours=8))
today = datetime.now(TW).date()
roc = lambda d: f"{d.year - 1911}{d:%m%d}"  # noqa: E731
long_ago = (today - timedelta(days=30)).isoformat()   # 約 20 個交易日前
two_days = None


def prev_trading(n):
    d, k = today, 0
    while k < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            k += 1
    return d.isoformat()


two_days = prev_trading(2)


class R:
    def __init__(self, data, fail=False):
        self.data, self.fail = data, fail

    def json(self):
        if self.fail:
            raise ValueError("boom")
        return self.data


def fake_session(quotes_fail=False):
    resp = {
        B.TWSE_STOCK_DAY_ALL: R([{"Code": "1101", "ClosingPrice": "30"}], fail=quotes_fail),
        B.TPEX_QUOTES: R([{"SecuritiesCompanyCode": "6488", "Close": "500"}]),
        B.TWSE_COMPANY: R([{"公司代號": c} for c in ("1101", "8183", "2222", "2867", "1107")]),
        B.TPEX_ROSTER: R([{"SecuritiesCompanyCode": c} for c in ("6488", "7777", "7778")]),
        B.TPEX_CMODE: R([]),
        B.TWSE_TWTAWU: R([]),
        B.TWSE_DELISTED: R([{"Code": "2867", "DelistingDate": f"{today.year - 1911}/{(today - timedelta(days=40)):%m/%d}"},
                            {"Code": "1107", "DelistingDate": "96/10/20"}]),
        B.TPEX_SPENDI_HIST: R([{"SecuritiesCompanyCode": "7777", "DateOfSuspendedTrading": roc(today - timedelta(days=10)), "DateOfResumedTrading": ""},
                               {"SecuritiesCompanyCode": "7778", "DateOfSuspendedTrading": roc(today - timedelta(days=10)), "DateOfResumedTrading": ""},
                               {"SecuritiesCompanyCode": "7778", "DateOfSuspendedTrading": "", "DateOfResumedTrading": roc(today - timedelta(days=5))}]),
    }

    class S:
        def get(self, url, timeout=None):
            return resp[url]
    return S()


tmp = Path(tempfile.mkdtemp()) / "lu.json"
prev = {"last_seen": {c: today.isoformat() for c in ("1101", "8183", "2222", "6488", "7777", "7778", "1107", "2867")},
        "suspended": {}, "last_quoted": {"1101": two_days, "8183": long_ago, "2222": two_days, "6488": two_days,
                                          "7777": long_ago, "7778": two_days, "1107": two_days, "2867": long_ago}}
tmp.write_text(json.dumps(prev), encoding="utf-8")
B.OUT = tmp
B.make_session = lambda: fake_session()
B.main()
d = json.loads(tmp.read_text(encoding="utf-8"))
sh, su = d["suspected_halt"], d["suspended"]
res = [("①8183 名冊在、約 20 個交易日不在快照 → 疑似停止交易", "8183" in sh and sh["8183"]["trading_days_absent"] >= 5),
       ("②2222 只缺 2 個交易日 → 不標", "2222" not in sh),
       ("③2867 近期終止上市、今天沒收盤價 → DELISTED_OFFICIAL", su.get("2867", {}).get("trading_status") == "DELISTED_OFFICIAL" and "2867" not in sh),
       ("④1107 很久以前終止上市 → 不標官方", "1107" not in su),
       ("⑤7777 最後是暫停 → 官方停止交易；7778 已恢復 → 不標", su.get("7777", {}).get("source") == "TPEx tpex_spendi_history" and "7778" not in su),
       ("今天有收盤價的 1101 不標", "1101" not in sh and "1101" not in su)]
tmp.write_text(json.dumps(prev), encoding="utf-8")
B.make_session = lambda: fake_session(quotes_fail=True)
B.main()
d2 = json.loads(tmp.read_text(encoding="utf-8"))
res.append(("⑥上市收盤快照抓失敗 → 不判疑似、last_quoted 不動", d2["suspected_halt"] == {} and d2["last_quoted"]["1101"] == two_days))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
