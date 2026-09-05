"""假設#40（庫藏股買回公告效應）資料源客戶端——公開資訊觀測站（MOPS）
`t35sc09`功能（上市公司買回自己公司股份彙總統計表）。

跟`twse_day_trading_client.py`/`twse_t86_client.py`同一種「可重複呼叫、
per-window快取檔案本身就是完成紀錄」設計：每個(market, 半年窗口)一個
parquet檔，已存在就跳過不重打，backfill腳本可以中斷後重跑接續。

查證結果（`buyback_announcement_probe.py`，2026-09-06本輪）：
- `TYPEK=sii`(上市)/`otc`(上櫃)皆可查，`d1`/`d2`用民國年純數字格式
  （例如`1140101`），一次查半年份沒問題。
- 回應宣稱`charset=UTF-8`且內容確實是合法UTF-8（用`requests`預設
  `apparent_encoding`即可正確解碼，不需要特殊處理——之前一度懷疑亂碼，
  查證後證實只是終端機顯示問題，資料本身是乾淨UTF-8）。
- 民國104年(2015)上半年：sii 64列、otc 38列；民國114年(2025)上半年：
  sii 120列、otc 90列——確認可回溯至少到2015年，涵蓋本佇列TRAIN期
  起點（`validation/holdout.py` VAL_END之前）。
- 回傳HTML巢狀table結構，簡易正則會把資料列切碎，改用`BeautifulSoup`
  挑「欄位數最多的table」再逐列解析，欄位對得上文件記錄的18欄。

**節流**：MOPS非商用API，逐筆查詢間隔`SLEEP_BETWEEN_CALLS`秒，比照
`twse_t86_client.py`/`backfill_day_trading_ratio.py`同一個節流精神
（`CLAUDE.md`已知地雷章節）。
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data" / "raw_mops_buyback"
DATA_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t35sc09"
REFERER = "https://mopsov.twse.com.tw/mops/web/t35sc09"
HEADERS = {
    "User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)",
    "Referer": REFERER,
    "Content-Type": "application/x-www-form-urlencoded",
}
SLEEP_BETWEEN_CALLS = 2.0
MAX_RETRIES = 3

# 欄位英文化，方便後續程式處理（避免中文欄名在不同工具間傳遞出問題）。
# 注意：實測發現表頭是「兩列」結構（第一列18個群組欄，其中「買回價格
# 區間」跟「預定買回期間」各用colspan=2橫跨兩個子欄，第二列補上「最低/
# 最高」「起/迄」子標籤），資料列實際是20欄，不是表面看到的18欄——
# `_parse_rows()`已依此展開，這裡的key要對應展開後的20個最終欄名。
COLUMN_MAP = {
    "序號": "seq",
    "公司代號": "stock_id",
    "公司名稱": "stock_name",
    "董事會決議日期": "board_resolution_date",
    "買回目的": "purpose_code",
    "買回股份總金額上限(依最新財報計算之法定上限)": "max_total_amount",
    "預定買回股數": "planned_shares",
    "買回價格區間_最低": "price_min",
    "買回價格區間_最高": "price_max",
    "預定買回期間_起": "period_start",
    "預定買回期間_迄": "period_end",
    "是否執行完畢": "is_completed",
    "買回達一定標準資料": "threshold_flag",
    "本次已買回股數(空白為尚在執行中)": "actual_shares",
    "本次執行完畢已註銷或轉讓股數": "cancelled_or_transferred_shares",
    "本次已買回股數佔預定買回股數比例(%)(空白為尚在執行中)": "actual_pct_of_planned",
    "本次已買回總金額(空白為尚在執行中)": "actual_total_amount",
    "本次平均每股買回價格(空白為尚在執行中)": "avg_price",
    "本次買回股數佔公司已發行股份總數比例(%)": "pct_of_outstanding",
    "本次未執行完畢之原因": "incomplete_reason",
}

# 需要展開colspan的群組欄名 -> 子標籤前綴（依實測第二列子標籤出現順序）
_COLSPAN_GROUPS = {"買回價格區間", "預定買回期間"}


def _cache_path(market: str, d1: str, d2: str) -> Path:
    return DATA_DIR / f"BUYBACK_{market}_{d1}_{d2}.parquet"


def _fetch_html(market: str, d1: str, d2: str) -> str:
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "TYPEK": market,
        "RD": "1",
        "d1": d1,
        "d2": d2,
    }
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(URL, headers=HEADERS, data=payload, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001 -- 資料源禮儀：重試+backoff，不要靜默吞錯
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"MOPS t35sc09 fetch失敗 market={market} {d1}~{d2}: {last_err}")


def _build_header(trs) -> list[str] | None:
    """展開兩列表頭：第一列群組欄用colspan橫跨兩個子欄的（`_COLSPAN_GROUPS`
    列名），從第二列依序取子標籤接在群組名後面；資料實際列數才對得上。
    實測（`buyback_announcement_probe.py`跟本模組首次試跑共同確認）：
    row0=18群組欄、row1=4個子標籤（最低/最高/起/迄）、資料列=20欄。"""
    if len(trs) < 3:
        return None
    row0 = trs[0].find_all(["th", "td"])
    row1 = trs[1].find_all(["th", "td"])
    sub_labels = [c.get_text(strip=True) for c in row1]
    sub_idx = 0
    header: list[str] = []
    for cell in row0:
        text = cell.get_text(strip=True)
        colspan = int(cell.get("colspan", 1))
        if colspan >= 2 and text in _COLSPAN_GROUPS:
            for _ in range(colspan):
                if sub_idx >= len(sub_labels):
                    return None  # 子標籤數對不上，結構跟預期不同，交給呼叫端判定失敗
                header.append(f"{text}_{sub_labels[sub_idx]}")
                sub_idx += 1
        else:
            header.append(text)
    return header


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
    if len(trs) < 3:
        return []

    header_cells = _build_header(trs)
    if header_cells is None:
        return []

    rows = []
    for tr in trs[2:]:
        cells = [c.get_text(strip=True) for c in tr.find_all("td")]
        if len(cells) != len(header_cells):
            continue  # 跳過結構不符的列（分隔列/合併儲存格列），寧可漏不要錯拼
        rows.append(dict(zip(header_cells, cells)))
    return rows


def fetch_window(market: str, d1: str, d2: str, force: bool = False) -> pd.DataFrame:
    """抓一個(market, 半年窗口)，寫入快取parquet，回傳DataFrame（可能是空的）。"""
    path = _cache_path(market, d1, d2)
    if path.exists() and not force:
        return pd.read_parquet(path)

    html = _fetch_html(market, d1, d2)
    rows = _parse_rows(html)
    df = pd.DataFrame(rows)
    if not df.empty:
        rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        df = df.rename(columns=rename)
        df["market"] = market
        df["query_d1"] = d1
        df["query_d2"] = d2
    df.to_parquet(path, index=False)
    time.sleep(SLEEP_BETWEEN_CALLS)
    return df


def load_all_cached() -> pd.DataFrame:
    """把DATA_DIR底下所有已快取的parquet讀進來合併成一份，去重
    （同一筆公告可能因窗口相鄰重複被抓到——用stock_id+board_resolution_date
    去重，保留第一筆）。"""
    files = sorted(DATA_DIR.glob("BUYBACK_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "stock_id" in df.columns and "board_resolution_date" in df.columns:
        df = df.drop_duplicates(subset=["stock_id", "board_resolution_date"], keep="first")
    return df.reset_index(drop=True)
