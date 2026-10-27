# -*- coding: utf-8 -*-
"""自測：模擬 O（paper_15 ML 產業輪動，先.一三六-B7）。

全部用合成資料或暫存檔，不碰真實帳本／摘要，**不印任何淨值或報酬**。
1. 季報股數 PIT：Q1～Q3 季末 +45 天、年報 +90 天才可用；可用日前沿用上一期、最早一期之前為 None。
2. 產業指數：前一日市值加權；有效成分股 <5 → 當日 None；缺市值或報酬的成分股不計。
3. to_frame：報酬 None 的日子水準為 NaN、之後重新起算（窗口跨不過缺口）。
4. training_rows：特徵取執行日前一交易日、標籤＝執行日→次月執行日水準比、持有期有缺口不出標籤、標籤終點 ≤2024-12-31。
5. step()：起跑（2027-01-04）前 NOT_STARTED、不寫帳本。
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import paper_15_ml_industry_tracker as O  # noqa: E402

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


# 1. PIT 股數
check(O._avail_date("2013-03-31") == "2013-05-15", "Q1 季報 +45 天可用")
check(O._avail_date("2012-12-31") == "2013-03-31", "年報 +90 天可用")
sched = [("2013-03-31", 100.0), ("2013-05-15", 110.0)]
check(O.shares_asof(sched, "2013-03-30") is None, "最早一期可用日前為 None（不回填）")
check(O.shares_asof(sched, "2013-03-31") == 100.0, "可用日當天起用")
check(O.shares_asof(sched, "2013-05-14") == 100.0 and O.shares_asof(sched, "2013-06-01") == 110.0, "下一期可用後切換")

# 2. 產業指數
d1 = "2020-01-02"
five = {f"S{i}": {d1: (0.01 * (i + 1), 100.0 * (i + 1), 1e6)} for i in range(5)}
idx = O.industry_index({"X": five})["X"]
exp = sum(100.0 * (i + 1) * 0.01 * (i + 1) for i in range(5)) / sum(100.0 * (i + 1) for i in range(5))
check(abs(idx["r"][0] - exp) < 1e-12 and idx["n"][0] == 5, "市值加權日報酬正確、成分股數 5")
four = dict(five)
four["S4"] = {d1: (0.05, None, 1e6)}   # 缺市值 → 不計
check(O.industry_index({"X": four})["X"]["r"][0] is None, "有效成分股 <5 → 當日 None")
check(abs(O.industry_index({"X": four})["X"]["tm"][0] - 5e6) < 1e-6, "成交金額合計含缺市值成分股")

# 3. to_frame
fr = O.to_frame({"d": ["a", "b", "c", "e"], "r": [0.1, None, 0.1, 0.1], "tm": [1, 1, 1, 1]})
lv = fr["adj_close"].tolist()
check(abs(lv[0] - 1.1) < 1e-12 and math.isnan(lv[1]) and abs(lv[2] - 1.1) < 1e-12 and abs(lv[3] - 1.21) < 1e-12,
      "缺口日 NaN、之後從 1 重新起算")

# 4. training_rows（合成：2 個產業各 5 檔，2024-06～2024-12 交易日）
days, d = [], date(2024, 6, 3)
while d <= date(2024, 12, 31):
    if d.weekday() < 5:
        days.append(d.isoformat())
    d += timedelta(days=1)
mkt = {x: 100.0 * (1.0005 ** i) for i, x in enumerate(days)}
members = {}
for k, ind in enumerate(("A", "B")):
    members[ind] = {}
    for i in range(5):
        members[ind][f"{ind}{i}"] = {x: (0.001 * (k + 1) * (1 if j % 3 else -1), 1e9, 1e8) for j, x in enumerate(days)}
# B 產業在 2024-11 中間有一天成分股不足 → 2024-11 那一期不出標籤
gap = [x for x in days if x.startswith("2024-11")][5]
for s in members["B"].values():
    s[gap] = (None, None, 1e8)
old = (O.TRAIN_FIRST_MONTH, O.TRAIN_LAST_MONTH)
O.TRAIN_FIRST_MONTH = "2024-09"
rows = O.training_rows(members, mkt, days)
O.TRAIN_FIRST_MONTH, O.TRAIN_LAST_MONTH = old
check(len(rows) > 0, "合成資料產生訓練列")
check(all(r["label_end"] <= O.LABEL_END_CAP for r in rows), "標籤終點 ≤ 2024-12-31")
check(all(r["feature_date"] < r["exec_date"] for r in rows), "特徵日早於執行日（PIT）")
check(not any(r["industry"] == "B" and r["exec_date"].startswith("2024-11") for r in rows), "持有期有缺口 → 不出標籤")
check(any(r["industry"] == "A" and r["exec_date"].startswith("2024-11") for r in rows), "無缺口產業照常出標籤")
check(all(set(O.FEATURES) <= set(r) for r in rows), "每列含 8 個特徵欄")

# 5. step() 起跑前 NOT_STARTED、不寫帳本
with tempfile.TemporaryDirectory() as td:
    O.OUT, O.LOG = Path(td) / "paper_15.json", Path(td) / "paper_15_log.jsonl"
    r = O.step()
    doc = json.loads(O.OUT.read_text(encoding="utf-8"))
    check(r["state"] == "NOT_STARTED" and not doc["started"], "起跑前 NOT_STARTED")
    check(not O.LOG.exists(), "起跑前不寫帳本")
    check("nav" not in doc and "return" not in json.dumps(doc), "摘要不含任何淨值／報酬")

# 6. 共用框架 weighted 模式：70／30 目標權重、扣成本後淨值、出場
import paper_forward_common as C  # noqa: E402
cal6 = ["2027-01-04", "2027-02-01"]
rows6 = {c: [{"date": d, "close": p, "adj_close": p, "turnover": 1e9} for d, p in zip(cal6, ps)]
         for c, ps in {"1101": (10.0, 11.0), "2330": (100.0, 100.0), "1216": (50.0, 50.0)}.items()}
px6 = C.Px(rows6)
tw = {"2027-01-04": [{"code": "1101", "weight": 0.35}, {"code": "2330", "weight": 0.35}],
      "2027-02-01": [{"code": "2330", "weight": 0.35}, {"code": "1216", "weight": 0.35}]}
sp6 = C.Spec(key="t", label="t", note="", prereg="", trial_no=None, start_not_before="2027-01-04", judge_after="2029-01-02",
             mode="weighted", top_n=0, signal=lambda ctx, day, uni: tw[day])
st = {"positions": {}, "cash": C.INITIAL, "started": False, "last_rebalance_month": None}
r1 = C._day_weighted(sp6, px6, "2027-01-04", st, {}, set(rows6))
inv = sum(p["units"] * px6.close_on(c, "2027-01-04") for c, p in r1["positions"].items())
check(abs(inv / r1["nav"] - 0.70) < 1e-6, "weighted：持股占調倉後淨值 70%")
check(r1["nav"] < C.INITIAL and abs(r1["nav"] - (inv + r1["cash"])) < 0.05, "weighted：淨值＝持股＋現金，且已扣買進成本")
st2 = {"positions": r1["positions"], "cash": r1["cash"], "started": True, "last_rebalance_month": "2027-01"}
r2 = C._day_weighted(sp6, px6, "2027-02-01", st2, {}, set(rows6))
check(r2["exited"] == ["1101"] and r2["entered"] == ["1216"] and len(r2["closed_trades"]) == 1, "weighted：不在目標的持股出場")
check(r2["positions"]["2330"]["entry_date"] == "2027-01-04", "weighted：續抱保留原進場日")

print("ALL PASS" if not fails else f"{len(fails)} FAIL")
raise SystemExit(1 if fails else 0)
