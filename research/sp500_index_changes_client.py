"""假設#51-US（強制交易者事件·美股版）資料源客戶端——S&P Dow Jones
Indices 指數成分調整公告，來源`press.spglobal.com`（PRNewswire代管的
官方新聞稿發布系統，`www.spglobal.com/spdji`主站403擋爬蟲，此為
迂迴查證後確認可行的官方公開端點，見`HYPOTHESIS_QUEUE.md` #51-US
條目2026-09-08馬拉松第460輪查證紀錄）。

**踩到的分頁陷阱（本模組修正，2026-09-08第462輪查證）**：`press.
spglobal.com/index.php?s=2429&...&pagetemplate=rss`這個RSS模板**不管
`o`/`l`參數給什麼值，一律回傳同樣的最新5篇**——第460輪只驗證了
HTTP 200，沒有比對不同`o`值的實際內容是否不同，誤判為「o=0~3680皆為
合法分頁」。這正是`CLAUDE.md`已知地雷警告過的「回200但內容其實不變/
不合法」同一種陷阱，只是換了個網站。**修正**：拿掉`pagetemplate=rss`，
改用一般HTML列表頁（`index.php?s=2429&o=<offset>&l=<limit>`），這個
版本的`o`/`l`參數實測真的會改變回傳內容（不同offset回傳不重疊的10~50
筆），且首頁分頁連結本身就給出`o=3680`當作最後一頁，佐證約3,680篇。

**兩層快取設計**（比照`mops_material_news_client.py`per-window慣例）：
1. 列表頁快取（`LISTING_*.parquet`）：每個`(offset, page_size)`一份，
   記錄該頁全部文章的標題／連結／發布日期（未過濾），供之後重新套用
   或調整關鍵字規則時不必重打listing。
2. 文章內容快取（`ARTICLE_*.parquet`）：每篇「標題符合指數成分調整
   關鍵字」的文章，解析後的表格列（可能是空表——代表關鍵字誤判或
   頁面結構例外，一樣落盤避免重複嘗試）。

**關鍵字規則**（2026-09-08本輪對前200篇新聞稿人工抽樣得出，事前寫死，
不得為了塞入更多樣本事後放寬）：標題含"Set to Join"（大小寫不敏感）
且同時提到下列任一指數名稱關鍵字：S&P 500 / S&P 100 / S&P MidCap 400 /
S&P SmallCap 600 / Dow Jones Industrial Average / Dow Jones Transportation
Average。抽樣200篇中全部指數成分調整公告都符合此規則，未見"will
replace"/"to Replace"這類措辭（可能存在於未抽到的樣本，回補時若某頁
文章表格解析為空但看起來像指數公告，記錄进`UNMATCHED_TITLES_LOG`供
人工複核，不得為了衝樣本數放寬關鍵字）。

**節流**：`press.spglobal.com`為S&P Global自家新聞稿站台，非付費/登入
資源，官方頁面本身無公開速率上限文件。呼叫端（backfill腳本）比照
`mops_material_news_client.py`同一節流精神，逐頁/逐篇間隔由呼叫端控制，
本模組不內建重試/延遲。
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data" / "raw_sp_index_changes"
DATA_DIR.mkdir(parents=True, exist_ok=True)

LISTING_URL = "https://press.spglobal.com/index.php"
HEADERS = {"User-Agent": "AlphaApp/0.2 (jlove201314@yahoo.com.tw)"}

DEFAULT_PAGE_SIZE = 50

INDEX_NAME_KEYWORDS = (
    "S&P 500",
    "S&P 100",
    "S&P MidCap 400",
    "S&P SmallCap 600",
    "Dow Jones Industrial Average",
    "Dow Jones Transportation Average",
)


def is_index_change_title(title: str) -> bool:
    """事前寫死的關鍵字規則，見模組docstring。標題需同時滿足『提到
    "Set to Join"』與『提到至少一個目標指數名稱』。"""
    if "set to join" not in title.lower():
        return False
    return any(k.lower() in title.lower() for k in INDEX_NAME_KEYWORDS)


def _listing_cache_path(offset: int, page_size: int) -> Path:
    return DATA_DIR / f"LISTING_o{offset:05d}_l{page_size:03d}.parquet"


def fetch_listing_page(offset: int, page_size: int = DEFAULT_PAGE_SIZE, force: bool = False) -> pd.DataFrame:
    """抓一頁新聞稿列表（未過濾），欄位：offset/date/title/link。
    回傳空DataFrame代表該offset已超過列表末端（可作為backfill的停止
    條件）。"""
    path = _listing_cache_path(offset, page_size)
    if path.exists() and not force:
        return pd.read_parquet(path)

    resp = requests.get(
        LISTING_URL,
        params={"s": 2429, "o": offset, "l": page_size},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for item in soup.find_all("li", class_="wd_item"):
        title_a = item.select_one(".wd_title a")
        date_div = item.select_one(".wd_date")
        if title_a is None:
            continue
        rows.append(
            {
                "offset": offset,
                "date": date_div.get_text(strip=True) if date_div else None,
                "title": title_a.get_text(strip=True),
                "link": title_a.get("href", ""),
            }
        )
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    return df


def _article_slug(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", path)
    return slug[:150]


def _article_cache_path(url: str) -> Path:
    return DATA_DIR / f"ARTICLE_{_article_slug(url)}.parquet"


def fetch_and_parse_article(url: str, title: str = "", article_date: str = "", force: bool = False) -> pd.DataFrame:
    """抓單篇公告內文，解析『Effective Date/Index Name/Action/Company
    Name/Ticker/GICS Sector』表格。回傳空DataFrame代表該頁沒有這種
    結構的表格（例如標題誤判為指數公告，或頁面格式例外），一樣落盤
    快取避免重複嘗試打同一個URL。"""
    path = _article_cache_path(url)
    if path.exists() and not force:
        return pd.read_parquet(path)

    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows: list[dict] = []
    for table in soup.find_all("table"):
        first_tr = table.find("tr")
        if first_tr is None:
            continue
        header = [c.get_text(strip=True) for c in first_tr.find_all(["th", "td"])]
        if not any("Effective Date" in h for h in header):
            continue
        for tr in table.find_all("tr")[1:]:
            cells = [c.get_text(strip=True) for c in tr.find_all("td")]
            if len(cells) != len(header):
                continue  # 跳過結構不符的列，寧可漏不要錯拼
            record = dict(zip(header, cells))
            rows.append(record)
        break  # 一篇公告只有一張這種表格，找到就停

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.rename(
            columns={
                "Effective Date": "effective_date_raw",
                "Index Name": "index_name",
                "Action": "action",
                "Company Name": "company_name",
                "Ticker": "ticker",
                "GICS Sector": "gics_sector",
            }
        )
    df["source_url"] = url
    df["article_title"] = title
    df["article_date_raw"] = article_date
    df.to_parquet(path, index=False)
    return df


def load_all_cached_articles() -> pd.DataFrame:
    """把DATA_DIR底下所有已快取且非空的ARTICLE parquet合併。"""
    files = sorted(DATA_DIR.glob("ARTICLE_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(f) for f in files]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)
