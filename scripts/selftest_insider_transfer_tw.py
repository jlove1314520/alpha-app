# -*- coding: utf-8 -*-
"""fetch_insider_transfer_tw.py 自測（不連網，先.九十四-5d）。

夾具是合成資料（欄位名照 2026-10-14 實測回應，姓名／受讓人是假的），
驗：民國轉西元、兩邊欄位統一、缺欄位照實警告、非陣列拒收、去重、
既有紀錄保留、meta 日期清單。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fit", ROOT / ".github" / "scripts" / "fetch_insider_transfer_tw.py")
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)

COMMON = {
    "姓名": "測試甲", "預定轉讓方式及股數-轉讓方式": "贈與", "預定轉讓方式及股數-轉讓股數": "",
    "每日於盤中交易最大得轉讓股數": "", "受讓人": "測試乙",
    "目前持有股數-自有持股": "1000", "目前持有股數-保留運用決定權信託股數": "0",
    "預定轉讓總股數-自有持股": "100", "預定轉讓總股數-保留運用決定權信託股數": "0",
    "預定轉讓後持股-自有持股": "900", "預定轉讓後持股-保留運用決定權信託股數": "0",
    "有效轉讓期間": "1151013~1151015",
}
TWSE_ROW = {"出表日期": "1151013", "公司代號": "9999", "公司名稱": "測試上市", "申報人身分": "董事本人", **COMMON}
TPEX_ROW = {"Date": "1151013", "SecuritiesCompanyCode": "8888", "CompanyName": "測試上櫃", "申請人身分": "經理人本人", **COMMON}

fails: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)


check(fit.roc_to_compact("1151013") == "20261013", "民國 1151013 → 20261013")
check(fit.roc_to_compact("991231") == "20101231", "民國 991231 → 20101231")
check(fit.roc_to_compact("abc") is None and fit.roc_to_compact("") is None, "格式不符回 None 不猜")

tw, w1 = fit.normalize_rows([TWSE_ROW], "TWSE")
tp, w2 = fit.normalize_rows([TPEX_ROW], "TPEX")
check(len(tw) == 1 and not w1, "TWSE 一列正常解析、無警告")
check(len(tp) == 1 and not w2, "TPEx 一列正常解析、無警告")
check(tw[0]["code"] == "9999" and tw[0]["role"] == "董事本人" and tw[0]["report_date"] == "20261013", "TWSE 欄位改名正確")
check(tp[0]["code"] == "8888" and tp[0]["role"] == "經理人本人" and tp[0]["company"] == "測試上櫃", "TPEx 欄位改名正確（申請人身分→role）")
check(set(tw[0]) == set(tp[0]), "兩邊輸出鍵完全相同")
check(tw[0]["planned_own"] == "100", "數值照原字串保留，不轉型")

bad = dict(TWSE_ROW)
bad.pop("受讓人")
_, w3 = fit.normalize_rows([bad], "TWSE")
check(any("缺欄位" in w for w in w3), "缺欄位照實警告")
nocode = dict(TWSE_ROW, 公司代號="")
r4, w4 = fit.normalize_rows([nocode], "TWSE")
check(not r4 and any("沒有公司代號" in w for w in w4), "沒代號的列略過並警告")

try:
    fit.normalize_rows({"html": "<html>"}, "TWSE")
    check(False, "非陣列回應要拒收")
except ValueError:
    check(True, "非陣列回應要拒收")

records, added = fit.merge(None, tw + tp)
check(added == 2 and len(records) == 2, "首次併入 2 筆")
records2, added2 = fit.merge({"records": records}, tw + tp)
check(added2 == 0 and len(records2) == 2, "同一快照隔天重抓不重複記")
changed = fit.normalize_rows([dict(TWSE_ROW, **{"預定轉讓總股數-自有持股": "200"})], "TWSE")[0]
records3, added3 = fit.merge({"records": records2}, changed)
check(added3 == 1 and len(records3) == 3, "內容不同的申報另記一筆")
records4, added4 = fit.merge({"records": records3}, [])
check(added4 == 0 and len(records4) == 3, "這次沒資料時既有紀錄全部保留")

doc = fit.build_doc(records3, {"added": 1})
check(doc["meta"]["report_dates"] == {"TWSE": ["20261013"], "TPEX": ["20261013"]}, "meta 日期清單正確")
check(doc["meta"]["record_count"] == 3, "meta 筆數正確")

print(f"\n{'全部通過' if not fails else f'失敗 {len(fails)} 項'}")
sys.exit(1 if fails else 0)
