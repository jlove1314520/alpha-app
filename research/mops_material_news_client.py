"""假設#52（事件反應速度）資料源客戶端——公開資訊觀測站（MOPS）
`t05st01`（公司當日重大訊息之詳細內容）功能，全市場逐日窄查詢。

跟`mops_buyback_client.py`/`twse_day_trading_client.py`同一種「可重複
呼叫、per-window（此處為per-day）快取檔案本身就是完成紀錄」設計：每個
交易日一個parquet，已存在就跳過不重打，backfill腳本可以中斷後重跑接續。

查證結果見`HYPOTHESIS_QUEUE.md` #52條目「(j)」「(k)」段落（2026-09-08
hypothesis_queue排程）：`ajax_t05st01`需要先GET表單頁拿`jcsession`
cookie（早前一度誤判被安全阻擋，其實是參數不完整+缺cookie）；`co_id`
留空＋`b_date=e_date`（同一天）可繞過MOPS內部筆數上限，回傳精確到秒的
`發言時間`欄位（PIT時間戳，本假設事前綁定的硬性要求）。

**節流**：MOPS非商用API，同一個`requests.Session`可重複用於多天查詢
（不必每天重新GET表單頁拿cookie），逐日查詢間隔由呼叫端（backfill
腳本）控制，比照`mops_buyback_client.py`/`twse_day_trading_client.py`
同一個節流精神（`CLAUDE.md`已知地雷章節）。本模組不內建重試/session
重建邏輯——單一職責，session生命週期與重試策略留給呼叫端（跟
`mops_buyback_client.py`的`fetch_window()`一樣把重試邏輯上移一層）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data" / "raw_mops_material_news"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FORM_URL = "https://mopsov.twse.com.tw/mops/web/t05st01"
AJAX_URL = "https://mopsov.twse.com.tw/mops/web/ajax_t05st01"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": FORM_URL,
    "Origin": "https://mopsov.twse.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
}

# 中文欄名英文化，方便後續程式處理（避免中文欄名在不同工具間傳遞出問題）。
COLUMN_MAP = {
    "公司代號": "stock_id",
    "公司名稱": "stock_name",
    "發言日期": "announce_date_roc",
    "發言時間": "announce_time",
    "主旨": "subject",
}


class MOPSMaterialNewsError(RuntimeError):
    """單日窄查詢理論上不該觸發「查詢資料量過大」或「僅能查詢單日」這
    兩種已知錯誤訊息（那是全月/未指定單日查詢才會遇到的限制）——出現
    代表查詢規格本身有問題（例如session過期導致回應變成登入頁/錯誤頁
    而非資料表），呼叫端應重建session或停止，重試同一個請求不會變
    成功。"""


def new_session() -> requests.Session:
    """GET表單頁拿`jcsession`cookie。session生命週期由呼叫端（backfill
    腳本）管理，需要時（例如偵測到錯誤）自行呼叫本函式重建，本函式
    本身不快取session、不做重試。"""
    s = requests.Session()
    r = s.get(FORM_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return s


def _cache_path(date_str: str) -> Path:
    return DATA_DIR / f"MATNEWS_{date_str}.parquet"


def _to_roc(date_str: str) -> tuple[str, str, str]:
    """date_str為YYYYMMDD西元格式（跟本專案多數client一致，換算民國年
    只在本函式內部做一次，避免`CLAUDE.md`警告過的未查證推算風險擴散到
    呼叫端）。回傳(roc_year, month, day)三個數字字串。"""
    year = int(date_str[:4]) - 1911
    month = date_str[4:6]
    day = date_str[6:8]
    return str(year), month, day


def _parse_rows(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []
    best, best_cols = None, 0
    for t in tables:
        first_tr = t.find("tr")
        if not first_tr:
            continue
        n_cols = len(first_tr.find_all(["th", "td"]))
        if n_cols > best_cols:
            best_cols, best = n_cols, t
    if best is None:
        return []
    trs = best.find_all("tr")
    if len(trs) < 2:
        return []
    header = [c.get_text(strip=True) for c in trs[0].find_all(["th", "td"])]
    rows = []
    for tr in trs[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if len(cells) != len(header):
            continue  # 跳過結構不符的列，寧可漏不要錯拼
        rows.append(dict(zip(header, cells)))
    return rows


def fetch_material_news_day(session: requests.Session, date_str: str, force: bool = False) -> pd.DataFrame:
    """抓一個交易日全市場重大訊息，寫入快取parquet，回傳DataFrame（可能
    是空的，代表當天無公告或非交易日——空結果一樣落盤快取，backfill視為
    「已完成」不重打，比照`twse_day_trading_client.py`同一個慣例）。
    date_str為YYYYMMDD西元格式。"""
    path = _cache_path(date_str)
    if path.exists() and not force:
        return pd.read_parquet(path)

    roc_year, month, day = _to_roc(date_str)
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all",
        "co_id": "",
        "year": roc_year,
        "month": month,
        "b_date": day,
        "e_date": day,
    }
    resp = session.post(AJAX_URL, headers=HEADERS, data=payload, timeout=30)
    resp.raise_for_status()
    text = resp.text
    if "查詢資料量過大" in text or "僅能查詢單日" in text:
        raise MOPSMaterialNewsError(
            f"{date_str}：單日窄查詢理論上不該觸發此錯誤，可能是session過期，"
            f"內容前200字：{text[:200]}"
        )

    rows = _parse_rows(text)
    df = pd.DataFrame(rows)
    if not df.empty:
        if "" in df.columns:
            # 實測表頭第6欄是無文字的圖示/詳細連結欄（2026-09-08查證，見
            # `_header_check.txt`探測紀錄），非資料欄位，丟棄避免污染快取。
            df = df.drop(columns=[""])
        rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        df = df.rename(columns=rename)
        df["date"] = date_str
    df.to_parquet(path, index=False)
    return df


def load_all_cached() -> pd.DataFrame:
    """把DATA_DIR底下所有已快取的parquet讀進來合併成一份。"""
    files = sorted(DATA_DIR.glob("MATNEWS_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)
