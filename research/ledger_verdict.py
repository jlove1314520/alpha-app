# -*- coding: utf-8 -*-
"""試驗帳本「判定欄」解析——selection_bias_ledger.py 與 .github/scripts/build_trials_index.py 共用（先.一〇三-15，2026-10-16）。

為什麼要獨立一支：兩支程式原本各自「從右往左找第一個含判定關鍵字的欄」，備註欄（最後一欄）或結果欄裡只要
用散文提到別筆的 PASS／FAIL，就會被當成這一筆的判定。10/16 逐列比對 448 列有 96 列判錯，例：
#445 事前登記判定欄是「**未結案**」，備註寫「PASS需全過…」→ 被讀成 PASS；#426 判定欄「**PASS**」、
備註提到 FAIL → 被讀成 FAIL；#29 判定欄「FAIL（單測門檻未過）」、備註提到 CHEAP_PASS → 被讀成 CHEAP_PASS。

規則（判定欄是「以判定字開頭」的欄，不是「含判定字」的欄）：
1. 從右往左、不含最後一欄（備註），找第一個「去掉 ** ` 空白後以判定字開頭、且原文以 ** 粗體開頭」的欄
   ——register_trial() 一律寫成 `**{verdict}**`；
2. 沒有粗體的，同範圍找第一個「以判定字開頭」的欄；
3. 再沒有，看最後一欄（少數舊列判定寫在最後一欄）；
4. 都沒有回 None，由呼叫端退回舊的「含關鍵字」規則（舊帳本有判定寫成散文的列，例 #31）。
"""
from __future__ import annotations

import re

# 順序有意義：較長、為另一個字子字串的要放前面（FRAMEWORK_CHECK_FAILED 在 FRAMEWORK_CHECK 前、CHEAP_PASS 在 PASS 前）
VERDICT_KEYS = ("FRAMEWORK_CHECK_FAILED", "FRAMEWORK_CHECK", "CHEAP_PASS", "EXPERIMENTAL", "IRREPRODUCIBLE",
                "VIOLATES_SURVIVAL", "ABANDONED", "REFUTED", "DUPLICATE", "INVALID", "未結案", "不確定", "FAIL", "PASS")
_STRIP = re.compile(r"[`*\s]")


def _starts(cell: str) -> str | None:
    t = _STRIP.sub("", cell or "")
    for k in VERDICT_KEYS:
        if t.startswith(k):
            return k
    return None


def strict_verdict(cells: list[str]) -> str | None:
    """cells＝該列的欄位（不含表格兩側空字串），第 0 欄編號、第 1 欄日期。回傳判定字或 None。"""
    body = cells[2:]
    if not body:
        return None
    mid, last = body[:-1], body[-1]
    for c in reversed(mid):
        k = _starts(c)
        if k and c.lstrip().startswith("**"):
            return k
    for c in reversed(mid):
        k = _starts(c)
        if k:
            return k
    return _starts(last)
