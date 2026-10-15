# -*- coding: utf-8 -*-
"""fetch_insider_transfer_tw.py 自測（不連網，先.九十四-5d）。

夾具是合成資料（欄位名照 2026-10-14 實測回應，姓名／受讓人是假的），
驗：民國轉西元、兩邊欄位統一、缺欄位照實警告、非陣列拒收、去重、
既有紀錄保留、meta 日期清單。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import os

# 先.一〇三-19：HMAC 金鑰用測試專用假值（不是正式金鑰；正式金鑰只在 GitHub Secret）
os.environ["INSIDER_HASH_KEY"] = "selftest-only-not-a-real-key"

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
# 先.九十五-3：姓名、受讓人改雜湊，原文不得出現在輸出
dump = json.dumps(tw + tp, ensure_ascii=False)
check("測試甲" not in dump and "測試乙" not in dump, "姓名／受讓人原文不落地")
check("name" not in tw[0] and "transferee" not in tw[0], "輸出沒有 name／transferee 原文鍵")
check(tw[0]["name_hash"] == tp[0]["name_hash"] and len(tw[0]["name_hash"]) == 16, "同一姓名雜湊相同（可辨識同一人）")
check(tw[0]["name_hash"] != tw[0]["transferee_hash"], "不同人雜湊不同")
check(fit.person_hash("") is None and fit.person_hash(None) is None, "空值雜湊回 None 不補")
# 先.一〇三-19：HMAC 與舊 v1 不同、換金鑰雜湊就變、沒金鑰不寫雜湊（不退回 v1）
import hashlib as _hl
_v1 = _hl.sha256((fit.HASH_PREFIX + "測試甲").encode("utf-8")).hexdigest()[:16]
check(fit.person_hash("測試甲") != _v1 and fit.hash_scheme() == "hmac-sha256-v2", "有金鑰時用 HMAC，不等於舊 v1 雜湊")
_h1 = fit.person_hash("測試甲")
os.environ["INSIDER_HASH_KEY"] = "another-selftest-key"
check(fit.person_hash("測試甲") != _h1, "換金鑰雜湊就變（沒金鑰無法比對姓名）")
os.environ["INSIDER_HASH_KEY"] = ""
check(fit.person_hash("測試甲") is None and fit.hash_scheme() == "none", "沒設金鑰不寫姓名雜湊、不退回 v1")
os.environ["INSIDER_HASH_KEY"] = "selftest-only-not-a-real-key"

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
