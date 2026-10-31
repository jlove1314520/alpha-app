# -*- coding: utf-8 -*-
"""先.八十一-21（2026-10-13）：掃描冒煙測試的「等待條件被預設文字／骨架即滿足」競態。

背景：#117 等「走勢註記出現『來源：』」，但 index.html 裡該元素的預設文字本來就是「來源：日收盤價」，
等待條件在真正資料寫入前就成立，測試拿到預設文字而誤判（先.八十一-10 踩到）。
做法：
1. 從 scripts/smoke_test.mjs 抓出所有 `waitForFunction(() => /正則/.test(...getElementById("ID")...))` 形狀的等待
   （以及 `querySelector("#ID")`），取得 (ID, 正則)。
2. 從 index.html 取該 ID 元素的「預設內容」（去標籤後的文字）。
3. 用 Python re 測試：預設文字已符合正則 → 列為「可疑：預設文字即滿足等待」。
另外列出等待「元素數量 > 0」的 selector 若在 index.html 預設骨架裡就已存在 → 也列可疑。
只讀檔、不改任何東西；輸出清單供人工確認。用法：python scripts/scan_smoke_waits.py
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SMOKE = (ROOT / "scripts" / "smoke_test.mjs").read_text(encoding="utf-8")
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")

WAIT_RE = re.compile(r"waitForFunction\(\s*\(\)\s*=>\s*(?P<body>.*?)\s*,\s*(?:null|undefined|\{)", re.S)
TEST_RE = re.compile(r"/(?P<rx>(?:\\/|[^/\n])+?)/(?P<flags>[gimsuy]*)\.test\(", re.S)
ID_RE = re.compile(r"""getElementById\(\s*["'](?P<id>[\w-]+)["']\s*\)|querySelector\(\s*["']#(?P<id2>[\w-]+)["']\s*\)""")


def default_text(el_id: str) -> str | None:
    m = re.search(r"<(?P<tag>[a-zA-Z0-9]+)[^>]*\bid=[\"']" + re.escape(el_id) + r"[\"'][^>]*>", INDEX)
    if not m:
        return None
    tag, start, depth, i = m.group("tag"), m.end(), 1, m.end()
    open_re, close_re = re.compile(r"<" + tag + r"\b[^>]*?(?<!/)>"), re.compile(r"</" + tag + r"\s*>")
    while depth and i < len(INDEX):
        o, c = open_re.search(INDEX, i), close_re.search(INDEX, i)
        if not c:
            break
        if o and o.start() < c.start():
            depth += 1; i = o.end()
        else:
            depth -= 1; i = c.end()
            if depth == 0:
                inner = INDEX[start:c.start()]
                return html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
    return None


def js_rx_to_py(rx: str) -> str:
    return rx.replace("\\/", "/")


def js_flags_to_py(flags: str) -> int:
    """先.一三五-1fh：JS 的 i（大小寫不分）／s（. 含換行）／m（多行）要照樣套用，否則 /abc/i 會漏抓預設文字 ABC。"""
    return (re.I if "i" in flags else 0) | (re.S if "s" in flags else 0) | (re.M if "m" in flags else 0)


def main() -> int:
    sus, checked = [], 0
    for wm in WAIT_RE.finditer(SMOKE):
        body = wm.group("body")
        line = SMOKE.count("\n", 0, wm.start()) + 1
        for tm in TEST_RE.finditer(body):
            ids = sorted({m.group("id") or m.group("id2") for m in ID_RE.finditer(body)})  # 等待主體裡出現的所有元素
            for el in ids:
                d = default_text(el)
                if d is None:
                    continue
                checked += 1
                try:
                    if re.search(js_rx_to_py(tm.group("rx")), d, js_flags_to_py(tm.group("flags"))):
                        sus.append((line, el, tm.group("rx"), d[:60]))
                except re.error as e:  # JS 語法 Python 編不過：只略過這一組並說明，不中斷掃描
                    print(f"[warn] smoke_test.mjs:{line} /{tm.group('rx')}/ Python 編不過，略過：{e}")
    print(f"檢查了 {checked} 組（等待條件 × 元素預設文字）")
    if not sus:
        print("沒有發現「預設文字即滿足等待」的條件")
    for line, el, rx, d in sus:
        print(f"可疑 smoke_test.mjs:{line}  #{el}  /{rx}/  預設文字＝「{d}」")
    return 1 if sus else 0


if __name__ == "__main__":
    sys.exit(main())
