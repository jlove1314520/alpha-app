# -*- coding: utf-8 -*-
"""補齊 `data/company_info.json` 的官方網址欄位（題材七待辦1，2026-09-15）。

背景：`research/theme_official_site_matcher.py` 需要「host 對得上公司官方
網址」才能判定官網證據是不是 A 級，但 `company_info.json` 原本沒有官網
欄位，只能靠 `data/company_official_domains_seed.json` 人工核實 7 家頂多。
待辦1的範圍就是把這個欄位正式補進 `company_info.json`，來源用 MOPS 官方
「基本資料」開放資料，不用爬蟲（符合「取得方式鐵律」）：

- 上市：TWSE openapi `t187ap03_L`（中文欄名，本檔案已用 `r.encoding='utf-8'`
  避開 `openapi.twse.com.tw` 對非 ASCII 內容偶發判斷成別的編碼的問題）
- 上櫃：TPEx openapi `mopsfin_t187ap03_O`
- 興櫃：TPEx openapi `mopsfin_t187ap03_R`

三個端點的公司代號集合互不重疊（本輪已實測驗證），直接合併不用去重邏輯。

**只補「網址」欄位，不做官網內容抓取**——內容抓取、reverse-exclusion 判斷
是待辦2（259 家 D 級候選抓取管線）的範圍，跟這裡是兩件事。

驗證：本輪已用 `data/company_official_domains_seed.json` 既有 7 家人工核實
種子（2330/2317/6223/2449/1216/2542/2603/5530/3130）逐一比對，MOPS 官方
資料與人工核實結果完全一致（僅 2317 鴻海官網登記為 honhai.com，跟種子
清單記的消費品牌站 foxconn.com 不同网域，兩者皆為鴻海集團官方網域，不算
矛盾——保留 MOPS 官方登記值，不用種子清單覆蓋）。

輸出：就地更新 `data/company_info.json`，對每一家在三個端點任一個查到
網址的公司，新增：
- `official_website`：MOPS 登記的原始網址字串（不改寫）
- `official_domain`：正規化後的裸網域（去 scheme、去開頭 www.），供
  `theme_official_site_matcher.py` 的 `official_domains` 參數直接使用
- `official_website_source`：`twse_L` / `tpex_O` / `tpex_R`
沒查到的公司（多半是 ETF、債券、已下市證券）不新增欄位，不得瞎猜。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / "data" / "company_info.json"
TW_TZ = timezone(timedelta(hours=8))

TWSE_L_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_O_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
TPEX_R_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R"


def normalize_domain(url: str) -> str | None:
    """裸網域：去 scheme、去開頭 www.、轉小寫。空字串或解析失敗回 None。

    MOPS 原始資料實測有兩筆全形冒號髒資料（`http：//...`），對這種已知的
    來源端資料品質問題先修正字元，不是放寬解析邏輯；其餘任何解析失敗一律
    回 None（誠實跳過，不猜）。
    """
    url = (url or "").strip().replace("　", "").replace("：", ":")
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def fetch_twse_listed() -> dict[str, tuple[str, str]]:
    """公司代號 -> (原始網址, 裸網域)，來源上市 t187ap03_L。"""
    r = requests.get(TWSE_L_URL, timeout=40)
    r.raise_for_status()
    r.encoding = "utf-8"
    out: dict[str, tuple[str, str]] = {}
    for row in r.json():
        code = (row.get("公司代號") or "").strip()
        url = (row.get("網址") or "").strip()
        dom = normalize_domain(url)
        if code and url and dom:
            out[code] = (url, dom)
    return out


def fetch_tpex(url: str) -> dict[str, tuple[str, str]]:
    """公司代號 -> (原始網址, 裸網域)，來源上櫃/興櫃 mopsfin_t187ap03_O/R。"""
    r = requests.get(url, timeout=40)
    r.raise_for_status()
    out: dict[str, tuple[str, str]] = {}
    for row in r.json():
        code = (row.get("SecuritiesCompanyCode") or "").strip()
        website = (row.get("WebAddress") or "").strip()
        dom = normalize_domain(website)
        if code and website and dom:
            out[code] = (website, dom)
    return out


def main() -> None:
    doc = json.loads(CI_PATH.read_text(encoding="utf-8"))
    companies = doc["companies"]
    before_missing = sum(1 for v in companies.values() if not v.get("official_website"))
    print(f"開始：{len(companies)} 檔，其中 official_website 缺 {before_missing} 檔")

    sources: list[tuple[str, dict[str, tuple[str, str]]]] = [
        ("twse_L", fetch_twse_listed()),
        ("tpex_O", fetch_tpex(TPEX_O_URL)),
        ("tpex_R", fetch_tpex(TPEX_R_URL)),
    ]
    for tag, data in sources:
        print(f"  {tag}: 抓到 {len(data)} 檔有網址")

    overlap = set(sources[0][1]) & set(sources[1][1])
    overlap |= set(sources[0][1]) & set(sources[2][1])
    overlap |= set(sources[1][1]) & set(sources[2][1])
    if overlap:
        print(f"  警告：三來源代號有重疊 {len(overlap)} 檔（預期應為 0，重疊的以後面來源覆蓋前面）：{sorted(overlap)[:10]}")

    filled = 0
    matched_not_in_ci = 0
    for tag, data in sources:
        for code, (url, dom) in data.items():
            if code not in companies:
                matched_not_in_ci += 1
                continue
            companies[code]["official_website"] = url
            companies[code]["official_domain"] = dom
            companies[code]["official_website_source"] = tag
            filled += 1

    after_missing = sum(1 for v in companies.values() if not v.get("official_website"))
    print(f"補齊：{filled} 檔次寫入（含三來源總和，重疊代號會被後面來源覆寫一次）")
    print(f"MOPS 有登記但不在 company_info.json 名冊裡：{matched_not_in_ci} 檔（多半是已下市或代號變更，不處理）")
    print(f"結束：官網缺 {after_missing} / {len(companies)} 檔（多半是 ETF/債券/已下市證券，MOPS 基本資料本來就沒有這欄）")

    seed_path = ROOT / "data" / "company_official_domains_seed.json"
    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        mismatches = []
        for code, info in seed.get("companies", {}).items():
            got = companies.get(code, {}).get("official_domain")
            want = info.get("official_domain")
            if got and want and got != want:
                mismatches.append((code, info.get("name"), want, got))
        print(f"與既有人工核實種子清單（{len(seed.get('companies', {}))} 家）比對：{len(mismatches)} 家網域不同")
        for code, name, want, got in mismatches:
            print(f"  {code} {name}：種子={want} MOPS={got}（保留 MOPS 官方登記值，兩者可能都是同集團官方網域，不覆寫）")

    meta = doc.setdefault("meta", {})
    meta["generated_at"] = datetime.now(TW_TZ).isoformat()
    meta["official_website_backfill_2026_09_15"] = {
        "before_missing": before_missing,
        "after_missing": after_missing,
        "source_counts": {tag: len(data) for tag, data in sources},
        "note": "題材七待辦1：官方網址來源為 MOPS 開放資料 t187ap03_L（上市）/"
                "mopsfin_t187ap03_O（上櫃）/mopsfin_t187ap03_R（興櫃），三來源代號"
                "互不重疊。ETF/債券/已下市證券沒有這欄是正常現象，非缺漏。"
                "見 research/build_company_official_websites.py。",
    }
    CI_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫回 {CI_PATH}")


if __name__ == "__main__":
    main()
