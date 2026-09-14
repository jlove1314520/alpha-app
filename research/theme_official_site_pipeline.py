# -*- coding: utf-8 -*-
"""官網來源抓取管線（題材七・待辦2，2026-09-15 假設佇列自走第十輪起步）。

**這支檔案要解決什麼**：`theme_official_site_matcher.py` 只有判斷規則（四條
規則的函式），沒有「實際去抓官網頁面」的管線；之前四輪（第5~9輪）都用
WebFetch 手動讀 1~2 家官網湊單元測試案例，`PENDING_QUEUE.md` 待辦2要的
「對 259 家 D 級候選逐一抓官網頁面」的**批次管線**一直沒有被建出來——
這支檔案補上這個地基。

**規模控制（本輪只做地基+小批試跑，不是一次做完259家）**：
`259 / 一輪` 早就被前四輪判定「規模超出一個有界工作單位」（PENDING_QUEUE.md
`第五輪`起連續4輪紀錄）。這支腳本設計成**可重複呼叫、每次只吃一個批次**
（`--batch-size`，預設10），比照題材三「分批做、每批20個、每批commit一次」
的既有慣例，把259家拆成約13批，每輪馬拉松吃一批，不強求一次做完。

**用哪一版分類規則**：只用`classify_sentence_v1_original`（PENDING_QUEUE.md
原文四條規則），**不用v2**——v2目前只驗證過5句真實案例、且第九輪已發現
兩個詞庫覆蓋不足的缺口、需要更多案例才能判斷會不會引入反效果，還沒有
準備好接生產管線（見`theme_official_site_matcher.py` main區塊待辦4段落）。

**輸出去向（刻意不寫進 themes.json）**：寫到獨立的
`data/theme_official_site_evidence_draft.json`，**明確標`status:"draft_
unreviewed"`**，不是正式的`data/themes.json`成員來源。理由：這支管線目前
只有3個真實案例驗過（旺矽/京元電正反例），259家批次跑出來的結果分佈還沒
有人工抽查過，直接餵進生產資料有把未經查核的雜訊當A級證據的風險——這正是
`CLAUDE.md`「做與判分離」帽子規則要求分開的兩件事：這支腳本負責「做」
（抓取+套規則），是否正式採用要留給下一輪或使用者查核批次結果後再決定。

**節流與資料源禮儀**：259家官網不是我們已知友善、已查過robots.txt的兩個
新聞來源（`.github/scripts/news_body_extract.py`那種白名單），是259個完全
不同、未知節流政策的第三方網站，禮儀要更保守——逐站間隔拉到3秒（新聞內文
管線是2秒）、逾時10秒、只重試1次（新聞內文管線重試2次；官網非我方核心
資料源，連不上直接記錄跳過即可，不必像新聞那樣力求成功）。

**JS渲染偵測（不裝無頭瀏覽器，PENDING_QUEUE.md原文明講）**：純用「抓到的
可見文字長度」當簡單啟發式——低於門檻視為`blocked_js_render`直接跳過，
不嘗試任何形式的瀏覽器自動化。這是保守判準，可能誤判部分文字確實很少的
極簡官網，但符合「不裝無頭瀏覽器」的硬規則，寧可漏抓不違規。

**分句方式**：官網文字沒有新聞那種明確段落結構，用中文句號/驚嘆號/問號
與換行同時當切點，比新聞內文抽取更粗略；每句取關鍵詞比對前會先過長度
下限（≥6字），濾掉導覽列殘留的短碎片（例如「首頁」「關於我們」）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from theme_official_site_matcher import (  # noqa: E402
    classify_sentence_v1_original,
    is_excluded_path,
)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
SEED_THEMES = D / "seed" / "seed_themes_validated.json"
THEME_KEYWORDS = D / "seed" / "theme_keywords.json"
COMPANY_INFO = D / "company_info.json"
OUT_DRAFT = D / "theme_official_site_evidence_draft.json"
TZ = timezone(timedelta(hours=8))

UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaResearch/1.0; research use)"}
REQ_INTERVAL = 3.0      # 逐站間隔（秒）——比新聞內文管線(2秒)更保守，官網非已知友善來源
TIMEOUT = 10             # 單次請求逾時（秒）
MAX_RETRY = 1            # 連不上重試上限（新聞內文管線是2，官網非核心來源不必力求成功）
RETRY_BACKOFF = 3.0
MIN_TEXT_LEN = 200       # 抓到的可見文字低於這個字數視為可能JS渲染，跳過
MIN_SENTENCE_LEN = 6     # 句子太短（導覽列殘留）不納入判定

_last = [0.0]


def _ensure_scheme(url: str) -> str:
    """company_info.json的official_website刻意保留MOPS原始字串不改寫
    （見build_company_official_websites.py），部分來源資料本身沒有
    scheme（例如'www.acc.com.tw'），requests會直接拋MissingSchema。
    這是消費端（本管線）該處理的問題，不是資料源該改寫——資料源保留
    原始值是為了可追溯，這裡才是真正需要「可請求的URL」的地方。"""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return "https://" + url
    return url


def _throttled_get(url: str) -> requests.Response:
    wait = REQ_INTERVAL - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    return requests.get(url, headers=UA, timeout=TIMEOUT)


def fetch_homepage_sentences(url: str) -> tuple[list[str], str | None]:
    """抓官網首頁、萃取可見文字並粗略分句。回傳 (句子清單, 失敗原因或None)。"""
    url = _ensure_scheme(url)
    last_reason = "unknown"
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = _throttled_get(url)
        except requests.RequestException as e:  # noqa: BLE001
            last_reason = f"exc_{type(e).__name__}"
            if attempt < MAX_RETRY:
                time.sleep(RETRY_BACKOFF)
                continue
            return [], last_reason
        if resp.status_code != 200:
            last_reason = f"http_{resp.status_code}"
            if attempt < MAX_RETRY:
                time.sleep(RETRY_BACKOFF)
                continue
            return [], last_reason
        try:
            resp.encoding = resp.apparent_encoding or resp.encoding
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        except Exception as e:  # noqa: BLE001
            return [], f"parse_exc_{type(e).__name__}"
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        joined = " ".join(lines)
        joined = re.sub(r"\s+", " ", joined).strip()
        if len(joined) < MIN_TEXT_LEN:
            return [], "blocked_js_render"
        sentences = re.split(r"(?<=[。！？])", joined)
        sentences = [s.strip() for s in sentences if len(s.strip()) >= MIN_SENTENCE_LEN]
        return sentences, None
    return [], last_reason


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_code_to_themes() -> dict[str, list[str]]:
    d = _load_json(SEED_THEMES)
    mapping: dict[str, list[str]] = {}
    for t in d["themes"]:
        for code in t.get("members", []):
            mapping.setdefault(code, []).append(t["id"])
    return mapping


def load_theme_keywords() -> dict[str, list[str]]:
    d = _load_json(THEME_KEYWORDS)
    out = {}
    for tid, info in d["themes"].items():
        out[tid] = info.get("keywords") or []
    return out


def run_batch(codes: list[str]) -> dict:
    companies = _load_json(COMPANY_INFO)["companies"]
    code_to_themes = build_code_to_themes()
    theme_kw = load_theme_keywords()

    results = []
    for code in codes:
        c = companies.get(code)
        entry = {"code": code, "name": c.get("name") if c else None}
        if not c or not c.get("official_website"):
            entry["status"] = "no_official_website"
            results.append(entry)
            continue
        url = c["official_website"]
        domain = c.get("official_domain") or ""
        themes = code_to_themes.get(code, [])
        entry["url"] = url
        entry["themes"] = themes
        if is_excluded_path(url):
            entry["status"] = "excluded_path"
            results.append(entry)
            continue

        sentences, fail_reason = fetch_homepage_sentences(url)
        if fail_reason:
            entry["status"] = fail_reason
            results.append(entry)
            continue

        kws: list[str] = []
        for tid in themes:
            kws.extend(theme_kw.get(tid, []))
        kws = sorted(set(kw for kw in kws if kw), key=len, reverse=True)

        hits = []
        for s in sentences:
            hit_kw = next((kw for kw in kws if kw in s), None)
            if not hit_kw:
                continue
            is_a_level = classify_sentence_v1_original(url, s, {domain} if domain else set())
            hits.append({
                "sentence": s[:160],
                "keyword": hit_kw,
                "a_level": is_a_level,
            })
        entry["status"] = "fetched"
        entry["sentence_count"] = len(sentences)
        entry["keyword_hits"] = len(hits)
        entry["a_level_hits"] = sum(1 for h in hits if h["a_level"])
        entry["hits"] = hits
        results.append(entry)
    return {
        "generated_at": datetime.now(TZ).isoformat(),
        "rule_version": "v1_original",
        "status": "draft_unreviewed",
        "note": (
            "本檔案由 theme_official_site_pipeline.py 產生，只用 v1 規則"
            "（host+path+反向排除），尚未經人工抽查，不是 data/themes.json"
            "的正式來源。a_level_hits>0 的候選在正式採用前，建議至少抽查"
            "幾筆 sentence 是否真的講對題材。"
        ),
        "batch_codes": codes,
        "results": results,
    }


def _sorted_all_codes() -> list[str]:
    d = _load_json(SEED_THEMES)
    codes = set()
    for t in d["themes"]:
        codes.update(t.get("members", []))
    return sorted(codes)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--offset", type=int, default=0, help="從全部259檔排序清單第幾個開始")
    ap.add_argument("--codes", type=str, default=None, help="逗號分隔，手動指定要跑的代號（略過offset/batch-size）")
    args = ap.parse_args()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        all_codes = _sorted_all_codes()
        codes = all_codes[args.offset: args.offset + args.batch_size]

    print(f"本次批次：{len(codes)} 檔 {codes}")
    out = run_batch(codes)

    # 累加寫入：若已有既有draft檔，合併（同代號以本次結果覆蓋，其餘保留）
    existing = {}
    if OUT_DRAFT.exists():
        try:
            prev = _load_json(OUT_DRAFT)
            for r in prev.get("results", []):
                existing[r["code"]] = r
        except (OSError, json.JSONDecodeError):
            existing = {}
    for r in out["results"]:
        existing[r["code"]] = r

    merged = dict(out)
    merged["results"] = list(existing.values())
    merged["total_codes_covered"] = len(existing)
    merged["total_candidates"] = len(_sorted_all_codes())

    OUT_DRAFT.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fetched = [r for r in out["results"] if r["status"] == "fetched"]
    a_level = sum(r.get("a_level_hits", 0) for r in fetched)
    print(f"本批次：fetched={len(fetched)}/{len(codes)}，a_level_hits合計={a_level}")
    print("失敗原因分布：")
    from collections import Counter
    print(Counter(r["status"] for r in out["results"]))
    print(f"累計進度：{merged['total_codes_covered']}/{merged['total_candidates']} 檔已跑過")
    print(f"寫入 {OUT_DRAFT}")


if __name__ == "__main__":
    main()
