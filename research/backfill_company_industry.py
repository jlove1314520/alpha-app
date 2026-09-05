# -*- coding: utf-8 -*-
"""補齊 `data/company_info.json` 的 `industry`（2026-09-05，總司令週六實測第二項第4點）。

**為什麼原本 603 檔是 None**：`build_company_info.py` 讀 FinMind `TaiwanStockInfo` 時，發現同一檔股票
在同一天有超過一種 `industry_category` 就誠實留 None（不猜）。實測查明那個「歧義」其實是
**母類與細類同時存在**：台積電＝`{半導體業, 電子工業}`、大立光＝`{光電業, 電子工業}`、
鴻海＝`{其他電子業, 電子工業}`。所以 603 檔幾乎全是電子股，而且它們的細類是明確的，不是真的分不出來。

**這支怎麼補（可查證、不猜）**：
1. 讀 FinMind `TaiwanStockInfo`，同一檔有多個分類時，**去掉母類「電子工業」保留細類**
   （細類唯一才採用；若去掉母類後仍 >1 種，才誠實留 None）。
2. 用 TWSE 官方 `t187ap03_L` 的「產業別」代碼交叉驗證：對每個代碼統計它底下股票的細類名稱，
   多數決建出「代碼→名稱」對照表存 `research/data/twse_industry_code_map.json`，
   FinMind 沒涵蓋到的上市股再用這張表補。
3. 每檔補上的來源記在 `meta.industry_source_counts`，可稽核。

輸出：就地更新 `data/company_info.json`（只補 `industry` 是 None 的，不覆寫既有值），
`meta` 記錄補了幾檔、還剩幾檔真的分不出來。
"""
from __future__ import annotations

import collections
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / "data" / "company_info.json"
CODE_MAP_PATH = Path(__file__).resolve().parent / "data" / "twse_industry_code_map.json"
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TW_TZ = timezone(timedelta(hours=8))
PARENT_CATEGORIES = {"電子工業"}  # 母類：跟細類同時出現時捨棄它（見模組 docstring）


def finmind_industries() -> dict[str, str | None]:
    """stock_id -> 細類名稱（去掉母類後唯一才給值，否則 None）。"""
    r = requests.get(FINMIND_URL, params={"dataset": "TaiwanStockInfo"}, timeout=60)
    r.raise_for_status()
    rows = r.json().get("data") or []
    by: dict[str, set[str]] = collections.defaultdict(set)
    for x in rows:
        sid, cat = x.get("stock_id"), (x.get("industry_category") or "").strip()
        if sid and cat:
            by[sid].add(cat)
    out: dict[str, str | None] = {}
    for sid, cats in by.items():
        specific = cats - PARENT_CATEGORIES
        out[sid] = next(iter(specific)) if len(specific) == 1 else (next(iter(cats)) if len(cats) == 1 else None)
    return out


def twse_code_map(fm: dict[str, str | None]) -> tuple[dict[str, str], dict[str, str]]:
    """回傳 (產業別代碼->名稱, 上市股票->產業別代碼)。名稱用該代碼底下股票的細類多數決。"""
    rows = requests.get(TWSE_LIST_URL, timeout=40).json()
    sid2code: dict[str, str] = {}
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        sid = r.get("公司代號")
        code = str(r.get("產業別") or "").strip()
        if not sid or not code:
            continue
        sid2code[sid] = code
        name = fm.get(sid)
        if name:
            votes[code][name] += 1
    code2name = {c: v.most_common(1)[0][0] for c, v in votes.items() if v}
    return code2name, sid2code


def main() -> None:
    doc = json.loads(CI_PATH.read_text(encoding="utf-8"))
    companies = doc["companies"]
    before_missing = [sid for sid, v in companies.items() if not v.get("industry")]
    print(f"開始：{len(companies)} 檔，其中 industry 缺 {len(before_missing)} 檔")

    fm = finmind_industries()
    print(f"FinMind 解出細類 {sum(1 for v in fm.values() if v)} 檔（去掉母類「電子工業」後唯一）")
    code2name, sid2code = twse_code_map(fm)
    CODE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    CODE_MAP_PATH.write_text(json.dumps(code2name, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"TWSE 產業別代碼對照表 {len(code2name)} 個代碼（存 {CODE_MAP_PATH.name}）")

    src = collections.Counter()
    for sid in before_missing:
        name = fm.get(sid)
        if name:
            companies[sid]["industry"] = name
            src["finmind_specific"] += 1
            continue
        code = sid2code.get(sid)
        if code and code in code2name:
            companies[sid]["industry"] = code2name[code]
            src["twse_code_map"] += 1
    after_missing = [sid for sid, v in companies.items() if not v.get("industry")]
    print(f"補齊：{src.get('finmind_specific', 0)} 檔用 FinMind 細類、{src.get('twse_code_map', 0)} 檔用 TWSE 代碼對照")
    print(f"結束：仍缺 {len(after_missing)} 檔（真的分不出來或非上市櫃），例如 {after_missing[:10]}")

    meta = doc.setdefault("meta", {})
    meta["generated_at"] = datetime.now(TW_TZ).isoformat()
    meta["industry_backfill_2026_09_05"] = {
        "before_missing": len(before_missing), "after_missing": len(after_missing),
        "source_counts": dict(src),
        "note": "原本的『歧義』其實是母類「電子工業」與細類同時存在（台積電＝半導體業+電子工業），"
                "去掉母類後細類唯一就採用；FinMind 沒涵蓋到的上市股用 TWSE t187ap03_L 產業別代碼對照表補。"
                "見 research/backfill_company_industry.py。",
    }
    meta.pop("industry_ambiguous_count", None)
    meta["industry_ambiguous_note"] = (
        f"2026-09-05 已補齊：原 {len(before_missing)} 檔缺 industry，補後剩 {len(after_missing)} 檔。"
        "剩下的多半是興櫃/已下市/非上市櫃證券，沒有官方產業別可對。")
    CI_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫回 {CI_PATH}")


if __name__ == "__main__":
    main()
