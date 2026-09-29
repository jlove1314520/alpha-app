# -*- coding: utf-8 -*-
"""補齊 `data/company_info.json` 中 industry 仍為 None 的上市公司（評.B-2 冒煙46的來源缺口）。

backfill_company_industry.py（2026-09-05）補完後仍剩 89 檔上市股是 None：FinMind 對它們同時給
「化學工業」與「化學生技醫療」兩個標籤而被判歧義。TWSE 官方 `t187ap03_L`「產業別」代碼把它們拆得很清楚：
21＝化學工業、22＝生技醫療業。這支只補 industry 是 None 且 TWSE 產業別代碼為 21/22 的公司，
不覆寫既有值；來源記在 meta.industry_backfill_2026_09_29。
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / "data" / "company_info.json"
TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
CODE_NAME = {"21": "化學工業", "22": "生技醫療業"}
TW_TZ = timezone(timedelta(hours=8))


def main() -> None:
    doc = json.loads(CI_PATH.read_text(encoding="utf-8"))
    companies = doc["companies"]
    rows = requests.get(TWSE_LIST_URL, timeout=40).json()
    code_of = {r["公司代號"]: str(r.get("產業別") or "").strip() for r in rows if r.get("公司代號")}
    before = [s for s, v in companies.items() if not v.get("industry")]
    filled = {}
    for sid in before:
        name = CODE_NAME.get(code_of.get(sid, ""))
        if name:
            companies[sid]["industry"] = name
            filled[sid] = name
    after = [s for s, v in companies.items() if not v.get("industry")]
    print(f"缺 industry {len(before)} → {len(after)}；補 {len(filled)} 檔："
          f"{sum(1 for v in filled.values() if v == '化學工業')} 化學工業、{sum(1 for v in filled.values() if v == '生技醫療業')} 生技醫療業")
    doc.setdefault("meta", {})["industry_backfill_2026_09_29"] = {
        "before_missing": len(before), "after_missing": len(after), "filled": len(filled),
        "source": TWSE_LIST_URL + "（產業別代碼 21=化學工業、22=生技醫療業）",
        "note": "backfill_company_industry.py 後仍缺的上市股（FinMind 同時給化學工業/化學生技醫療而判歧義），改用 TWSE 官方產業別代碼補；只補 None，不覆寫既有值。",
        "generated_at": datetime.now(TW_TZ).isoformat(),
    }
    CI_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
