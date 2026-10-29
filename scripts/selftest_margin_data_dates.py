# -*- coding: utf-8 -*-
"""自測：融資個股歷史累積檔記「資料日」（先.一三六-B7a）。全在暫存目錄、零外部請求。
1. infer_twse_margin_data_date：openapi 與同班 rwd 逐股餘額 ≥98% 相同才推定資料日；不足 100 檔或不夠相同 → None。
2. fresh_data_dates：recorded_at 超過 6 小時當舊值不用；日期轉 YYYYMMDD。
3. accumulate main()：新鍵記 data_dates／tpex_codes；舊鍵與 series 不改寫；本班沒有可信資料日 → 該執行日鍵不留 data_dates。
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import accumulate_margin_by_stock as A  # noqa: E402
import update_margin_maintenance as U  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


# 1.
api = {f"{1000 + i}": float(i) for i in range(200)}
rwd = dict(api)
d, why = U.infer_twse_margin_data_date(api, "2026-10-27", rwd)
check(d == "2026-10-27", f"上市：200/200 相同 → 推定 2026-10-27（{why}）")
rwd_bad = {k: v + 1 for k, v in api.items()}
check(U.infer_twse_margin_data_date(api, "2026-10-27", rwd_bad)[0] is None, "上市：逐股都不同（openapi 未更新）→ None")
check(U.infer_twse_margin_data_date(dict(list(api.items())[:50]), "2026-10-27", rwd)[0] is None, "上市：重疊 <100 檔 → None")
check(U.infer_twse_margin_data_date(api, None, {})[0] is None, "上市：rwd 失敗 → None")

# 2.
now = datetime.now(A.TW_TZ)
m_ok = {"margin_data_dates": {"twse": "2026-10-27", "tpex": "2026-10-27", "recorded_at": now.isoformat()}}
check(A.fresh_data_dates(m_ok) == {"twse": "20261027", "tpex": "20261027"}, "新鮮的 margin_data_dates → YYYYMMDD")
m_old = {"margin_data_dates": {"twse": "2026-10-27", "tpex": None, "recorded_at": (now - timedelta(hours=7)).isoformat()}}
check(A.fresh_data_dates(m_old) is None, "recorded_at 超過 6 小時 → 不採用")
check(A.fresh_data_dates({}) is None, "沒有 margin_data_dates → None")

# 3.
td = Path(tempfile.mkdtemp(prefix="margin_data_dates_selftest_"))
A.SNAPSHOT, A.OUT = td / "stock_detail.json", td / "margin_by_stock_history.json"
prior = {"meta": {}, "dates": ["20261027"], "series": {"1101": {"20261027": [1.0, 2.0, 3.0]}}}
A.OUT.write_text(json.dumps(prior), encoding="utf-8")
snap = {"meta": {"generated_at": "2026-10-28T00:03:08+08:00",
                 "margin_data_dates": {"twse": "2026-10-27", "tpex": "2026-10-27", "tpex_codes": ["6488"],
                                       "recorded_at": now.isoformat()}},
        "stocks": {"1101": {"margin": {"margin_balance_today": 5.0, "margin_balance_prev": 1.0, "short_balance_today": 0.0}},
                   "6488": {"margin": {"margin_balance_today": 7.0, "margin_balance_prev": 6.0, "short_balance_today": 1.0}}}}
A.SNAPSHOT.write_text(json.dumps(snap), encoding="utf-8")
check(A.main() == 0, "accumulate main() 正常結束")
out = json.loads(A.OUT.read_text(encoding="utf-8"))
check(out["series"]["1101"]["20261027"] == [1.0, 2.0, 3.0], "舊鍵 20261027 不改寫（保留稽核）")
check(out["series"]["1101"]["20261028"] == [5.0, 1.0, 0.0], "新執行日鍵 20261028 照舊寫入")
check(out["data_dates"] == {"20261028": {"twse": "20261027", "tpex": "20261027"}} and out["tpex_codes"] == ["6488"],
      "新鍵記 data_dates（資料日 20261027）與 tpex_codes")
snap["meta"]["margin_data_dates"]["recorded_at"] = (now - timedelta(hours=8)).isoformat()
A.SNAPSHOT.write_text(json.dumps(snap), encoding="utf-8")
A.main()
out = json.loads(A.OUT.read_text(encoding="utf-8"))
check("20261028" not in out["data_dates"] and out["tpex_codes"] == ["6488"], "本班資料日太舊 → 同執行日鍵不留 data_dates（tpex_codes 保留）")

# 4. 先.一三五-1bj：晚班推不出上市資料日，數值與同日早班相同 → 沿用；數值有變 → 不沿用
A.OUT.write_text(json.dumps({"meta": {}, "dates": [], "series": {}}), encoding="utf-8")
stk = {f"{2000 + i}": {"margin": {"margin_balance_today": float(i), "margin_balance_prev": 1.0, "short_balance_today": 0.0}}
       for i in range(60)}
stk["6488"] = {"margin": {"margin_balance_today": 7.0, "margin_balance_prev": 6.0, "short_balance_today": 1.0}}
early = {"meta": {"generated_at": "2026-10-29T09:16:00+08:00",
                  "margin_data_dates": {"twse": "2026-10-28", "tpex": "2026-10-28", "tpex_codes": ["6488"],
                                        "recorded_at": now.isoformat()}}, "stocks": stk}
A.SNAPSHOT.write_text(json.dumps(early), encoding="utf-8")
A.main()
late = json.loads(json.dumps(early))
late["meta"]["generated_at"] = "2026-10-29T21:25:00+08:00"
late["meta"]["margin_data_dates"]["twse"] = None
A.SNAPSHOT.write_text(json.dumps(late), encoding="utf-8")
A.main()
out = json.loads(A.OUT.read_text(encoding="utf-8"))
check(out["data_dates"].get("20261029") == {"twse": "20261028", "tpex": "20261028"},
      "晚班上市資料日推不出、上市 60 檔數值與早班相同 → 沿用早班 20261028")
late["stocks"] = {c: {"margin": {**v["margin"], "margin_balance_today": v["margin"]["margin_balance_today"] + 1}}
                  for c, v in stk.items()}
A.SNAPSHOT.write_text(json.dumps(late), encoding="utf-8")
A.main()
out = json.loads(A.OUT.read_text(encoding="utf-8"))
check(out["data_dates"].get("20261029") == {"twse": None, "tpex": "20261028"},
      "晚班上市數值已變 → 不沿用（上市 null，上櫃照本班）")
check(A.inherit_same_day_dates(None, None, {}, {}, set()) is None, "沒有本班也沒有早班資料日 → None")

print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL'}（暫存目錄 {td}）")
sys.exit(1 if fails else 0)
