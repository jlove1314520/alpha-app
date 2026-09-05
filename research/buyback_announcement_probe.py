"""Probe: 假設#40（庫藏股買回公告效應）的地基查證——公開資訊觀測站（MOPS）
`t35sc09`功能（上市公司買回自己公司股份彙總統計表）實際歷史回溯範圍、
欄位是否跟`HYPOTHESIS_QUEUE.md`#40條目記錄的一致、用BeautifulSoup解析
巢狀table結構是否正確（避免上一輪簡易正則切碎資料列的問題）。

背景：`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節指引——佇列#40排隊第一，資料
可行性已於2026-09-06 hypothesis_queue排程確認可行（實測2025/2026有完整
回傳），但尚未實測回溯到TRAIN期起點（本佇列其他假設多以2015年起算）。
本輪目標：只確認2015年附近是否有資料、欄位是否齊全、BeautifulSoup解析
是否正確——不做全歷史回補（那是下一輪正式回補腳本的事）。

資料源禮儀：MOPS非商用API，逐筆查詢間隔加延遲，避免高頻查詢
（`CLAUDE.md`已知地雷章節精神）。
"""
from __future__ import annotations

import time
import requests
from bs4 import BeautifulSoup

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t35sc09"
REFERER = "https://mopsov.twse.com.tw/mops/web/t35sc09"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": REFERER,
    "Content-Type": "application/x-www-form-urlencoded",
}

# 民國年起訖窗口：104年(2015) 上半年，測最早年份是否有資料
PROBE_WINDOWS = [
    ("1040101", "1040630", "民國104年(2015)上半年"),
    ("1140101", "1140630", "民國114年(2025)上半年，對照組（已知可行）"),
]


def fetch_window(typek: str, d1: str, d2: str) -> str:
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": typek,
        "RD": "1",
        "d1": d1,
        "d2": d2,
    }
    r = requests.post(URL, headers=HEADERS, data=payload, timeout=30)
    r.raise_for_status()
    return r.text


def parse_rows(html: str) -> list[dict]:
    """用BeautifulSoup解析巢狀table，避免簡易正則把資料列切碎。"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []
    # 挑欄位數最多、看起來像資料表的那個table（避免抓到外層排版table）
    best = None
    best_cols = 0
    for t in tables:
        first_tr = t.find("tr")
        if not first_tr:
            continue
        n_cols = len(first_tr.find_all(["th", "td"]))
        if n_cols > best_cols:
            best_cols = n_cols
            best = t
    if best is None:
        return []

    trs = best.find_all("tr")
    if not trs:
        return []
    header_cells = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
    rows = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if not cells or len(cells) < 3:
            continue  # 跳過空列/分隔列
        row = dict(zip(header_cells, cells))
        rows.append(row)
    return rows


def probe_one(typek: str, d1: str, d2: str, label: str) -> None:
    print(f"\n=== TYPEK={typek} d1={d1} d2={d2} ({label}) ===")
    try:
        html = fetch_window(typek, d1, d2)
    except Exception as e:  # noqa: BLE001 -- 探查階段要看到每一種失敗模式
        print(f"FAILED (fetch): {type(e).__name__}: {e}")
        return

    print(f"html length: {len(html)}")
    try:
        rows = parse_rows(html)
    except Exception as e:  # noqa: BLE001
        print(f"FAILED (parse): {type(e).__name__}: {e}")
        return

    print(f"parsed rows: {len(rows)}")
    if rows:
        print(f"columns: {list(rows[0].keys())}")
        for row in rows[:5]:
            print(row)
    else:
        print("解析出0列——可能該窗口真的沒有公告，或解析邏輯需要調整（附上html前500字供人工檢查）")
        print(html[:500])


def main() -> None:
    for typek in ("sii", "otc"):
        for d1, d2, label in PROBE_WINDOWS:
            probe_one(typek, d1, d2, label)
            time.sleep(2.0)  # 節流：避免高頻查詢MOPS


if __name__ == "__main__":
    main()
