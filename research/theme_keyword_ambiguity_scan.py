# -*- coding: utf-8 -*-
"""題材七 待辦4：v2詞庫擴充延伸範疇——123題材全面跨行業誤判掃描
（2026-09-15，本輪＝假設佇列自走第八輪）。

背景：上一輪（假設佇列第七輪）在補5530/3130負對照組時，用naive substring
比對（`kw in sentence`不分詞界）意外命中『petrochem石化』題材的關鍵詞
「EG」——原因是句子裡的英文單字「Legacy」剛好包含子字串「eg」。當時只
修好`theme_official_site_negative_control.py`自己測試迴圈的比對邏輯，
並留下待辦：「123個題材裡有多少個短縮寫關鍵詞（2~3字母）具有同樣風險，
需要一次全面掃描才能回答」——本檔案就是那次全面掃描。

**重要更正（本輪查證發現，糾正上一輪文件裡的錯誤陳述）**：
`theme_official_site_negative_control.py` 第64~67行docstring寫「這個修法
只影響本檔案自己的測試迴圈，不影響任何正式管線（因為待辦1的正式管線目前
還沒建，theme_keywords.json目前唯一的消費者就是這個測試腳本本身）」——
**這句話是錯的**。實測`scripts/build_themes.py`第48行
`KWMAP = D / "seed" / "theme_keywords.json"`、第101~113行`build_keyword_map()`
會直接讀取並使用這份規則檔的keywords作為正式的A/C級證據比對關鍵詞來源
（`main()`第203行呼叫），**這才是真正的正式生產管線**，不是題材七待辦1
（官網來源）那條還沒建的管線。上一輪把「題材七待辦1的官網抓取管線」誤
等同於「theme_keywords.json的唯一消費者」，忽略了這份檔案同時也是既有
新聞題材管線（`build_themes.py`）的關�keyword來源，本輪已查證更正。

**查證後的風險範圍重新評估（好消息）**：雖然消費者判斷錯了，但
`build_themes.py`裡實際用到keywords做A/C級「證據等級判定」的路徑
（`evidence_keyword()`）**不是裸的`kw in text`**——它額外要求：
  1. `kw_outside_company_name()`：關鍵詞不能只出現在公司名稱片段裡
  2. `pattern_hit()`：完整的「句型前綴+關鍵詞」組合字串（例如
     「打入EG供應鏈」）要整段literal出現在文字裡，不是只有kw本身出現
第2點大幅限縮了短縮寫詞的意外命中風險——要讓「EG」造成假警報，句子裡
必須literal出現「打入EG供應鏈」這種完整句型片段，光是「Legacy」這種
英文借詞本身不會意外組成這種完整句型片段。**唯一沒有這層防護的地方**
是第252~254行`kw_seen_in_news`/`kw_seen_in_events`——這兩個變數是裸的
`any(k in txt for k in kws)`，但用途只是`blocked`診斷訊息的文字選擇
（「關鍵詞在新聞裡從未出現」vs「出現過但沒對到候選成員」），**不影響
任何A/C級成員資格判定**，頂多讓診斷訊息文字選錯一種，屬於低嚴重度。

**本檔案做的事（純本地計算，不打任何網路請求）**：
  1. 靜態掃描：找出123個題材裡有沒有「完全相同字串」被兩個以上不同題材
     同時當關鍵詞使用（這種詞注定會讓同一句話同時命中兩個題材）。
  2. 靜態掃描：找出純ASCII、長度≤3的「短縮寫」關鍵詞（EG類風險），逐一
     列出，供人工複查。
  3. 實測掃描：把這些短縮寫關鍵詞，用「裸substring比對」與「詞界正則
     比對」兩種方法，同時套用在`data/news_evidence.json`的496句真實
     引言與`data/news.json`的300則標題上，找出兩種比對方法**結果不一致**
     的真實案例——這代表「理論風險」在目前的真實語料裡有沒有真的發生過。
  4. 對於第3步找到的裸substring誤判案例，額外重跑一次`evidence_keyword()`
     風格的完整判定（kw命中 + 非公司名稱 + 句型比對），確認這類誤判會不會
     真的通過`build_themes.py`實際的A/C級判定關卡，驗證上面「好消息」的
     推論是否成立。

範圍界線：本檔案**不修改**`scripts/build_themes.py`或`data/seed/
theme_keywords.json`——這兩個屬於既有正式管線，若掃描結果顯示需要修，
應留給下一輪依發現的具體問題另開有界工作單位（且需先確認是否落在
「純bug修復」可直接做的範圍，或需要先提案）。
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有⚠/✓
# (U+26A0/2713)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
KEYWORDS_PATH = DATA_DIR / "seed" / "theme_keywords.json"
NEWS_EVIDENCE_PATH = DATA_DIR / "news_evidence.json"
NEWS_PATH = DATA_DIR / "news.json"

# 純ASCII字母/數字組成、長度上限——比這個短的詞在中文語境裡最容易被
# 英文借詞的子字串意外命中（EG-in-Legacy就是長度2的例子）。
SHORT_ASCII_MAX_LEN = 3
_ASCII_ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")


def load_themes() -> dict:
    d = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    return d.get("themes") or {}


def is_short_ascii_keyword(kw: str) -> bool:
    return bool(_ASCII_ALNUM_RE.match(kw)) and len(kw) <= SHORT_ASCII_MAX_LEN


def find_cross_theme_duplicate_keywords(themes: dict) -> dict[str, list[str]]:
    """回傳 {關鍵詞字串: [使用它的題材id清單]}，只保留出現在 ≥2 個題材的。"""
    owners: dict[str, list[str]] = defaultdict(list)
    for tid, t in themes.items():
        for kw in t.get("keywords") or []:
            owners[kw].append(tid)
    return {kw: tids for kw, tids in owners.items() if len(set(tids)) >= 2}


def collect_short_ascii_keywords(themes: dict) -> dict[str, list[str]]:
    """回傳 {題材id: [短ASCII關鍵詞清單]}，只保留有命中的題材。"""
    out: dict[str, list[str]] = {}
    for tid, t in themes.items():
        hits = [kw for kw in (t.get("keywords") or []) if is_short_ascii_keyword(kw)]
        if hits:
            out[tid] = hits
    return out


def word_boundary_match(kw: str, text: str) -> bool:
    """詞界正則比對（沿用negative_control.py本輪確認過的修法）：
    純ASCII關鍵詞前後不能緊接[A-Za-z0-9]，避免當成英文借詞的子字串。
    大小寫不敏感（"EG"應同時排除"eg"/"Eg"這類子字串命中）。
    """
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return bool(pat.search(text or ""))


def naive_substring_match(kw: str, text: str) -> bool:
    return kw in (text or "")


def load_corpus_texts() -> list[tuple[str, str]]:
    """回傳 [(來源標籤, 文字)]，來源包含新聞標題與內文題材句引言。"""
    texts: list[tuple[str, str]] = []
    ev = json.loads(NEWS_EVIDENCE_PATH.read_text(encoding="utf-8"))
    for item in ev.get("evidence") or []:
        for q in item.get("quotes") or []:
            quote = q.get("quote") or ""
            if quote:
                texts.append((f"news_evidence:{item.get('url', '')}", quote))
    news = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    for n in news.get("news") or []:
        title = n.get("title") or ""
        if title:
            texts.append((f"news_title:{n.get('url', '')}", title))
    return texts


COMPANY_SUFFIX = ("股份有限公司", "有限公司", "控股公司", "公司",
                  "企業", "實業", "貿易", "投資", "控股")
_COMPANY_RE = re.compile(
    r"[一-鿿A-Za-z0-9()（）]{1,20}?(?:" + "|".join(COMPANY_SUFFIX) + ")")


def kw_outside_company_name(text: str, kw: str) -> bool:
    """複製自 scripts/build_themes.py 的同名函式（唯讀複製供離線驗證，
    不 import 生產模組，避免掃描腳本意外依賴或牽動生產程式路徑）。"""
    if not text or not kw:
        return False
    spans = [m.span() for m in _COMPANY_RE.finditer(text)]
    start = 0
    while True:
        i = text.find(kw, start)
        if i < 0:
            return False
        j = i + len(kw)
        if not any(a <= i and j <= b for a, b in spans):
            return True
        start = i + 1


def would_pass_full_pipeline(kw: str, text: str, patterns: list[str]) -> bool:
    """模擬 build_themes.py `evidence_keyword()` 的完整判定邏輯：
    裸substring命中 + 非公司名稱片段 + 完整句型片段literal出現。
    用來驗證「短縮寫誤判是否真的能通過正式管線的A/C級判定」。
    """
    if kw not in text:
        return False
    if not kw_outside_company_name(text, kw):
        return False
    for pat in patterns:
        frag = pat.replace("{theme}", kw).replace("{code}", "").strip()
        if frag and frag in text:
            return True
    return False


def load_sentence_patterns() -> list[str]:
    d = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    return (d.get("sentence_patterns") or {}).get("patterns") or []


def run() -> int:
    themes = load_themes()
    print(f"題材數量：{len(themes)}")

    # ── 掃描1：跨題材完全相同字串的關鍵詞 ──────────────────────────
    dups = find_cross_theme_duplicate_keywords(themes)
    print()
    print(f"=== 掃描1：跨題材重複關鍵詞（完全相同字串用在 ≥2 個題材）===")
    print(f"發現 {len(dups)} 個")
    for kw, tids in sorted(dups.items()):
        print(f"  「{kw}」→ {sorted(set(tids))}")

    # ── 掃描2：短ASCII縮寫關鍵詞盤點 ──────────────────────────────
    short_kw = collect_short_ascii_keywords(themes)
    total_short = sum(len(v) for v in short_kw.values())
    print()
    print(f"=== 掃描2：短ASCII縮寫關鍵詞（純字母/數字、長度≤{SHORT_ASCII_MAX_LEN}）===")
    print(f"共 {total_short} 個，分布在 {len(short_kw)} 個題材")
    for tid, kws in sorted(short_kw.items()):
        print(f"  {tid}: {kws}")

    # ── 掃描3：對真實語料跑裸substring vs 詞界正則，找不一致案例 ─────
    corpus = load_corpus_texts()
    print()
    print(f"=== 掃描3：對 {len(corpus)} 則真實語料句子做裸substring vs 詞界正則比對 ===")
    patterns = load_sentence_patterns()
    discrepancies = []
    for tid, kws in short_kw.items():
        for kw in kws:
            for src, text in corpus:
                naive = naive_substring_match(kw, text)
                boundary = word_boundary_match(kw, text)
                if naive and not boundary:
                    passes_full = would_pass_full_pipeline(kw, text, patterns)
                    discrepancies.append(dict(
                        theme_id=tid, keyword=kw, source=src, text=text,
                        would_pass_full_pipeline=passes_full,
                    ))
    print(f"發現 {len(discrepancies)} 筆「裸substring命中但詞界比對不命中」的真實案例")
    for d in discrepancies:
        flag = "⚠️會通過正式A/C級判定" if d["would_pass_full_pipeline"] else "✓正式管線的句型關卡會擋下"
        print(f"  [{d['theme_id']}/{d['keyword']}] {flag}")
        print(f"    來源：{d['source']}")
        print(f"    句子：{d['text'][:120]}")

    passing_count = sum(1 for d in discrepancies if d["would_pass_full_pipeline"])
    print()
    print("=== 結論 ===")
    print(f"跨題材重複關鍵詞：{len(dups)} 個（需人工複查是否為刻意設計的共用詞）")
    print(f"短ASCII縮寫關鍵詞：{total_short} 個（理論風險清單）")
    print(f"真實語料裡實際發生「裸substring命中但詞界比對不命中」：{len(discrepancies)} 筆")
    print(f"其中會通過正式管線完整A/C級判定關卡的：{passing_count} 筆")
    if passing_count == 0 and discrepancies:
        print("→ 驗證『好消息』推論成立：即使短縮寫詞有理論子字串風險，")
        print("  build_themes.py實際的句型關卡（evidence_keyword）已經把")
        print("  所有真實語料裡出現的誤判案例擋下，未通過任何正式A/C級判定。")
    elif passing_count == 0 and not discrepancies:
        print("→ 目前496句真實內文引言 + 300則標題語料裡，短縮寫關鍵詞")
        print("  完全沒有發生過裸substring vs 詞界比對的不一致——這批語料")
        print("  規模尚小（496句），不能因此斷言未來擴大語料池後也不會發生，")
        print("  下一輪語料池擴大後應重跑本掃描複查。")
    else:
        print("→ ⚠️ 發現真實案例會通過正式管線判定，需要另開工作單位評估")
        print("  是否需要修 build_themes.py 的 evidence_keyword()（屬於")
        print("  正式管線變更，需先確認是純bug修復或需要提案）。")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
