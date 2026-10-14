# -*- coding: utf-8 -*-
"""先.九十五-5：把中文維基百科「臺灣50指數」條目的「成份股變動」表結構化，只存本機（不進 repo）。

授權：維基百科文字以 CC BY-SA 4.0 授權（https://creativecommons.org/licenses/by-sa/4.0/），
衍生資料必須標示出處、作者（維基百科貢獻者）、授權，並以相同授權分享。輸出檔內附這些說明。
2026-10-14 總司令裁示先.九十五-5：可用維基百科，只存本機 research/data（不進 repo），檔案附出處與授權說明。
證交所 FTSE 路徑不抓（DATA_GAP_PLAN 第 6 節禁抓清單）。

取得（只抓一次，條目頁 /zh-tw/ 在 zh.wikipedia.org/robots.txt 允許；/w/ 與 /api/ 禁止，所以不用 API）：
  curl -A "AlphaResearch/1.0 (personal research; https://github.com/jlove1314520/alpha-app)" \\
       "https://zh.wikipedia.org/zh-tw/臺灣50指數" -o research/data/raw/wikipedia/tai50_zh-tw.html
本程式只讀上面那份本機 HTML，0 次網路請求。
輸出：research/data/tai50_constituent_changes_wiki.json
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = HERE / "data" / "raw" / "wikipedia" / "tai50_zh-tw.html"
OUT = HERE / "data" / "tai50_constituent_changes_wiki.json"
PAGE_URL = "https://zh.wikipedia.org/zh-tw/%E8%87%BA%E7%81%A350%E6%8C%87%E6%95%B8"
ITEM = re.compile(r"^(\d{4}[A-Z]?)\s*(.*)$")


def _cell_items(cell: str) -> list[dict]:
    cell = re.sub(r"<sup.*?</sup>", "", cell, flags=re.S)          # 去掉註腳
    parts = re.split(r"<br\s*/?>|</li>|</p>|\n", cell)
    out = []
    for p in parts:
        t = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        if not t:
            continue
        m = ITEM.match(t)
        if m:
            name = m.group(2).strip()
            out.append({"code": m.group(1), "name": name.rstrip("*").strip(), "footnote_mark": name.endswith("*")})
        else:
            out.append({"code": None, "name": t, "unparsed": True})   # 例如「?」：照原文記，不猜
    return out


def main() -> int:
    s = SRC.read_text(encoding="utf-8")
    rev = re.search(r'"wgRevisionId":(\d+)', s)
    i, j = s.find('id="成份股變動"'), s.find('id="相關條目"')
    sec = s[i:j]
    tbl = re.search(r"<table.*?</table>", sec, flags=re.S).group(0)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)
        if len(cells) != 3:
            continue
        label = html.unescape(re.sub(r"<[^>]+>", "", cells[0])).strip()
        m = re.match(r"(\d{4})年(\d{1,2})月", label)
        if not m:
            continue                                                  # 表頭
        rows.append({"month": f"{m.group(1)}-{int(m.group(2)):02d}", "label": label,
                     "added": _cell_items(cells[1]), "removed": _cell_items(cells[2])})
    unparsed = sum(1 for r in rows for k in ("added", "removed") for x in r[k] if x.get("unparsed"))
    doc = {
        "source": {"title": "臺灣50指數（中文維基百科）", "url": PAGE_URL,
                   "revision_id": int(rev.group(1)) if rev else None,
                   "revision_url": f"https://zh.wikipedia.org/w/index.php?oldid={rev.group(1)}" if rev else None,
                   "retrieved_at": datetime.fromtimestamp(SRC.stat().st_mtime).isoformat(timespec="seconds"),
                   "section": "成份股變動"},
        "license": {"name": "CC BY-SA 4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    "attribution": "資料取自中文維基百科「臺灣50指數」條目，作者為維基百科貢獻者；本檔為其結構化衍生資料，依 CC BY-SA 4.0 以相同授權提供。",
                    "note": "只存本機 research/data（不進公開 repo），先.九十五-5 裁示。"},
        "caveats": ["維基百科是社群編輯，非官方公告；先前 #82 以工商時報、鉅亨、聯合、自由時報核對 2016-06、2018-06、2020-09 三筆，組成全吻合，其餘未逐筆核對。",
                    "條目寫明 2011 年 1 月以前每年 1／4／7／10 月變動，2011 年 3 月起 3／6／9／12 月；沒有變動的季度不列。",
                    "「?」等無法解析的格照原文保留（unparsed=true），不猜代號。",
                    "月份是審核生效月份，不是精確生效日；用於回測要另外對齊實際生效日。"],
        "n_rows": len(rows), "n_unparsed_items": unparsed, "rows": rows,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} 列（{rows[0]['month']}～{rows[-1]['month']}），無法解析 {unparsed} 格 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
