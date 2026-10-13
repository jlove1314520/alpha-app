"""company_info.json 產業別改以官方公司基本資料為準（2026-10-13 先.八十一-36）。

**為什麼**：company_info.json 的 industry 原本來自 FinMind TaiwanStockInfo，同一個產業有好幾種寫法
（「其他電子類」／「其他電子業」、「數位雲端類」／「數位雲端」、「金融業」／「金融保險」…），
還有母類「電子工業」、舊分類「化學生技醫療」混在裡面——同產業的股票被拆成兩組，
估值的「同產業百分位」與類股資金流都會算錯。

**官方來源（2026-10-13 查證，四個端點各 1 次請求、同源間隔 ≥3 秒）**：
- 上市：`openapi.twse.com.tw/v1/opendata/t187ap03_L`（公司基本資料，欄位「產業別」＝兩碼代碼）
- 上櫃：`www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O`（`SecuritiesIndustryCode`＝代碼）
- 興櫃：`www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R`（同上）
- 代碼→名稱：`www.tpex.org.tw/openapi/v1/tpex_index_consti`（上櫃指數成分股，`SecuritiesIndustryCode`
  欄位直接是**中文產業名稱**）；與上櫃公司基本資料用公司代號對起來，得到官方「代碼→名稱」，
  10/13 實測 28 個代碼每個都只對到一個名稱（無歧義）。
- 只有上市才有的代碼（01、08、09、11、12、18、91），TPEx 沒有名稱可對；17 兩邊名稱不同（上櫃「金融業」），統一用上市的「金融保險」；
  名稱用 OFFICIAL_TWSE_ONLY_NAMES（TWSE 類股指數 MI_INDEX 有同名類別：水泥類、玻璃陶瓷類、
  造紙類、橡膠類、汽車類、金融保險類、貿易百貨類；存託憑證為 TWSE 證券別）。
兩家 swagger 都沒有公布次數上限；本腳本一次執行 4 次請求，手動跑（公司產業別很少變動）。

**怎麼套**：官方清單裡有的代號，industry 改成官方代碼對應的名稱，記 industry_source／industry_code；
官方清單沒有的（ETF、ETN、受益證券、已下市…）維持原值（FinMind 只補缺），不猜。
官方清單有、company_info 沒有的代號會補進來（名稱用官方簡稱）。
抓取失敗或任一端點筆數過少 → 不覆蓋（exit 1）。
"""
from __future__ import annotations

import collections
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / "data" / "company_info.json"
MAP_PATH = ROOT / "research" / "data" / "official_industry_code_map.json"
TW_TZ = timezone(timedelta(hours=8))
SAME_HOST_GAP_SEC = 3.0

URL_TWSE = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
URL_TPEX_O = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
URL_TPEX_R = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R"
URL_TPEX_NAMES = "https://www.tpex.org.tw/openapi/v1/tpex_index_consti"

# 上櫃沒有的上市代碼（TPEx 對不到名稱）。名稱依 TWSE 類股指數同名類別（見檔頭）。
OFFICIAL_TWSE_ONLY_NAMES = {
    "01": "水泥工業", "08": "玻璃陶瓷", "09": "造紙工業", "11": "橡膠工業",
    "12": "汽車工業", "17": "金融保險", "18": "貿易百貨", "91": "存託憑證",
}
MIN_ROWS = {"twse": 800, "tpex_o": 700, "tpex_r": 150, "tpex_names": 700}


def _get(url: str) -> list[dict]:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    j = r.json()  # TWSE 無效路徑回 200＋HTML，這裡會直接拋錯（不會靜默吃進去）
    if not isinstance(j, list):
        raise ValueError(f"{url} 不是 JSON 陣列")
    return j


def fetch_all() -> dict[str, list[dict]]:
    out = {"twse": _get(URL_TWSE)}
    out["tpex_o"] = _get(URL_TPEX_O)
    time.sleep(SAME_HOST_GAP_SEC)
    out["tpex_r"] = _get(URL_TPEX_R)
    time.sleep(SAME_HOST_GAP_SEC)
    out["tpex_names"] = _get(URL_TPEX_NAMES)
    for k, n in MIN_ROWS.items():
        if len(out[k]) < n:
            raise ValueError(f"{k} 只有 {len(out[k])} 筆（< {n}），疑似被限流或端點異常")
    return out


def build_code_map(raw: dict) -> tuple[dict[str, str], dict]:
    name_by_sid = {x.get("SecuritiesCompanyCode"): (x.get("SecuritiesIndustryCode") or "").strip() for x in raw["tpex_names"]}
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for x in raw["tpex_o"]:
        n = name_by_sid.get(x.get("SecuritiesCompanyCode"))
        c = (x.get("SecuritiesIndustryCode") or "").strip()
        if n and c:
            votes[c][n] += 1
    code_map, conflicts = {}, {}
    for c, v in votes.items():
        code_map[c] = v.most_common(1)[0][0]
        if len(v) > 1:
            conflicts[c] = dict(v)
    for c, n in OFFICIAL_TWSE_ONLY_NAMES.items():
        code_map.setdefault(c, n)
    # 代碼 17：上櫃叫「金融業」、上市類股指數叫「金融保險類」，上市 31 檔為多數 → 統一用「金融保險」
    # （research/precheck_supply_tightness.py 兩種都認）。[自行裁量]
    code_map["17"] = OFFICIAL_TWSE_ONLY_NAMES["17"]
    return dict(sorted(code_map.items())), conflicts


def main() -> int:
    try:
        doc = json.loads(CI_PATH.read_text(encoding="utf-8"))
        companies = doc["companies"]
    except Exception as e:  # noqa: BLE001
        print(f"[error] 讀不到 {CI_PATH.name}：{e}")
        return 1
    try:
        raw = fetch_all()
    except Exception as e:  # noqa: BLE001
        print(f"[error] 官方端點抓取失敗：{type(e).__name__}: {e}；不覆蓋")
        return 1
    code_map, conflicts = build_code_map(raw)

    official: dict[str, tuple[str, str, str]] = {}  # 代號 -> (代碼, 簡稱, 來源)
    for x in raw["twse"]:
        official[str(x.get("公司代號", "")).strip()] = ((x.get("產業別") or "").strip(), (x.get("公司簡稱") or "").strip(), "twse_t187ap03_L")
    for key, src in (("tpex_o", "tpex_t187ap03_O"), ("tpex_r", "tpex_t187ap03_R")):
        for x in raw[key]:
            sid = str(x.get("SecuritiesCompanyCode", "")).strip()
            official.setdefault(sid, ((x.get("SecuritiesIndustryCode") or "").strip(), (x.get("CompanyAbbreviation") or "").strip(), src))
    official.pop("", None)

    # 改前歧義量測：官方清單內的股票，同一官方代碼底下出現幾種寫法、幾檔跟官方名稱不同
    def ambiguity(comp: dict) -> dict:
        spellings: dict[str, set] = collections.defaultdict(set)
        differ = missing = 0
        for sid, (code, _, _) in official.items():
            cur = (comp.get(sid) or {}).get("industry")
            if code not in code_map:
                continue
            if not cur:
                missing += 1
                continue
            spellings[code].add(cur)
            differ += cur != code_map[code]
        multi = {c: sorted(s) for c, s in spellings.items() if len(s) > 1}
        return {"label_differs_from_official": differ, "missing": missing,
                "codes_with_multiple_spellings": len(multi), "extra_spellings": sum(len(s) - 1 for s in multi.values()),
                "examples": dict(list(multi.items())[:6])}

    before = ambiguity(companies)
    counts = collections.Counter()
    unknown_codes = collections.Counter()
    for sid, (code, abbr, src) in official.items():
        name = code_map.get(code)
        if not name:
            unknown_codes[code] += 1
            continue
        row = companies.get(sid)
        if row is None:
            companies[sid] = row = {"name": abbr or None, "industry": None}
            counts["added_company"] += 1
        if row.get("industry") != name:
            counts["changed"] += 1
        row["industry"] = name
        row["industry_code"] = code
        row["industry_source"] = src
        counts[src] += 1
    after = ambiguity(companies)

    stamp = datetime.now(TW_TZ).isoformat(timespec="seconds")
    doc.setdefault("meta", {})["official_industry_2026_10_13"] = {
        "applied_at": stamp,
        "sources": [URL_TWSE, URL_TPEX_O, URL_TPEX_R, URL_TPEX_NAMES],
        "note": "官方清單內的上市／上櫃／興櫃公司 industry 改用官方產業別代碼對應名稱；清單外（ETF 等）維持原值。腳本 scripts/apply_official_industry.py。",
        "counts": dict(counts),
        "unknown_codes": dict(unknown_codes),
        "code_name_conflicts": conflicts,
        "ambiguity_before": before,
        "ambiguity_after": after,
    }
    tmp = CI_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CI_PATH)
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps({"generated_at": stamp, "source": "TPEx tpex_index_consti × mopsfin_t187ap03_O（代號對代號）；上市獨有代碼見 scripts/apply_official_industry.py OFFICIAL_TWSE_ONLY_NAMES",
                                    "code_to_name": code_map, "conflicts": conflicts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"官方代碼 {len(code_map)} 個（衝突 {len(conflicts)}）；套用 {dict(counts)}；未知代碼 {dict(unknown_codes)}")
    print(f"改前：{json.dumps(before, ensure_ascii=False)}")
    print(f"改後：{json.dumps(after, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
