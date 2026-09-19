"""#72 研究.a續 (a)：估算 MOPS t51sb10 重大訊息，五個「重大訂單」關鍵字在
2015-2024（民國104-113）上市/上櫃的逐年筆數（各關鍵字分別查詢，加總為上界，
未跨關鍵字去重——去重留給正式回補腳本）。只做計數，不做統計檢定。
"""
from __future__ import annotations
import json, re, sys, time
import requests
import net_guard  # 2026-09-20合規.二：網域層防呆疊加在既有腳本層防呆上（belt-and-suspenders）
net_guard.install()
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
URL = "https://mopsov.twse.com.tw/mops/web/ajax_t51sb10"
HEADERS = {"User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
           "Referer": "https://mopsov.twse.com.tw/mops/web/t51sb10_q1"}
KEYWORDS = ["接單", "訂單", "得標", "簽約", "合作備忘"]
KINDS = {"L": "上市", "O": "上櫃"}
YEARS = list(range(104, 114))

def q(kind, kw, year, page=None):
    # 【緊急·合規】2026-09-20總司令裁示：本腳本2026-09-19已對
    # mopsov.twse.com.tw/mops/web/ajax_t51sb10 發出100次POST請求
    # （5關鍵字×2市場×10年度），該網域robots.txt為`Disallow: /`（僅
    # bingbot可存取），本專案2026-09-15已對同一網域的其他四支client
    # （mops_material_news_client.py等）加PermissionError禁用，這支
    # 新腳本繞過了那次禁令（防呆綁在既有client上，新腳本沒繼承到）。
    # 立即停用，直到有合規替代方案或總司令另行核准，見
    # docs/DATA_SOURCE_MAP.md「MOPS 合規」節與`net_guard.py`（根因修復：
    # 防呆已從腳本層移到網域層，任何新腳本現在都會被net_guard擋下）。
    raise PermissionError(
        "MOPS mopsov.twse.com.tw 存取已依 2026-09-15 總司令裁示停用"
        "（robots.txt 對非 bingbot UA 全站 Disallow）。本腳本2026-09-19"
        "曾繞過禁令發出100次請求，屬違規事件（見PENDING_QUEUE.md），"
        "已於2026-09-20停用。如需恢復，需先有合規替代方案或總司令另行核准。"
    )
    p = {"step": "1", "firstin": "true", "id": "", "key": "", "TYPEK": "", "Stp": "4", "go": "false",
         "r1": "1", "KIND": kind, "CODE": "", "keyWord": kw, "Condition2": "1", "keyWord2": "",
         "year": str(year), "month1": "0", "begin_day": "1", "end_day": "31", "Orderby": "1"}
    r = requests.post(URL, headers=HEADERS, data=p, timeout=30)
    r.raise_for_status()
    return r.text

def count(html):
    if "查無資料" in html:
        return 0
    rows = html.count("<TR class=")
    pages = [int(n) for n in re.findall(r"pagenum\.value='(\d+)'", html)]
    last = max(pages, default=1)
    return rows if last <= 1 else last * 15  # 粗估上界

out = {}
for kind in KINDS:
    for kw in KEYWORDS:
        for y in YEARS:
            key = f"{kind}|{kw}|{y+1911}"
            for attempt in range(3):
                try:
                    out[key] = count(q(kind, kw, y)); break
                except Exception as e:  # noqa: BLE001
                    out[key] = f"ERR {type(e).__name__}"
                    time.sleep(5)
            print(key, out[key], flush=True)
            time.sleep(2.0)
json.dump(out, open("material_disclosure_order_win_count.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
