# -*- coding: utf-8 -*-
"""每日排程更新 data/us_events.json（美股重大訊息，SEC EDGAR Form 8-K）。

`PENDING_QUEUE.md`「三」／「新三」（免費第一手資料管線）點名的美股那一半：
台股那一半（MOPS 重大訊息／月營收／除權息／RSS 新聞）2026-09-08 已建好並排進
`.github/workflows/news_events.yml` 每 30 分鐘排程（`fetch_news_events.py`），
唯獨「SEC 8-K」這塊一直沒接——8-K 是美股「重大訊息即時揭露」制度的對應物
（財報前瞻、董監異動、重大合約、破產等須在 4 個工作天內申報），跟 TW 那邊的
MOPS 重大訊息是同一種資訊角色，缺了它等於美股完全沒有事件資料源。

涵蓋範圍：跟 fetch_us_insider_trading.py 同一份 ticker→CIK 對映，直接讀
data/us_sic.json（market.yml 排程裡排在 fetch_us_sic.py 之後執行，零額外
請求去重打 company_tickers.json）；讀不到某檔 CIK 就跳過並記錄原因，不整份
失敗。

端點（SEC EDGAR 官方，免金鑰，2026-09-15 用 AAPL CIK 0000320193 實測 200）：
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&owner=include&count={N}&output=atom
—— 列出該發行人最近 N 筆 8-K／8-K/A 申報。**只存索引，不額外抓申報全文**
（沿用 fetch_news_events.py 的「只存索引」原則）：atom feed 本身的
<summary> 欄位已經含 SEC 官方寫的 Item 條號與條號說明（例如「Item 2.02:
Results of Operations and Financial Condition」），不需要再多打一次
index.json/主文件去解析內容——這點跟 Form 4（必須另外抓 XML 解析交易明細）
不同，8-K 一個請求就有全部我們要的欄位。

SEC 公平使用政策建議上限約 10 req/sec，本腳本只追蹤 us_sic.json 裡的少數
標的（每檔 1 個請求），沿用 fetch_us_sic.py／fetch_us_insider_trading.py
同款保守間隔（每次請求後 sleep 0.2 秒）。User-Agent 沿用專案識別用佔位
信箱（不把使用者本人 email 外流給不相關第三方服務）。

**誠實限制**：外國私人發行人（本清單裡的 TSM/UMC/ASX/CHT 台股ADR）依規定
改用 Form 6-K（非定期揭露）而非 8-K，2026-09-15 實測這四檔查到 0 筆是正常
狀態、不是抓取失敗；6-K 格式與 8-K 不同（沒有標準化 Item 條號），暫不接入，
需要時另立一支腳本，不強行套用這裡的解析邏輯。

輸出寫進 `data/us_events.json`（獨立檔案，不與 `data/events.json` 混在一起——
後者的 `code` 欄位是台股四位數代號、被 `research/live_factors.py` 的題材/
事件因子直接消費，美股 ticker 混進去會污染那支因子；美股頁另外讀這支檔案，
架構對齊 `data/us_insider_trading.json`／`data/us_13f_holdings.json` 的既有
先例）。
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "us_events.json"
SIC_PATH = REPO_ROOT / "data" / "us_sic.json"

HEADERS = {"User-Agent": "AlphaApp-US8K contact@alpha-app-project.example"}
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
REQUEST_SLEEP_SEC = 0.2
MAX_FILINGS_PER_TICKER = 10
KEEP_DAYS = 180  # 8-K 頻率遠低於台股重大訊息，留半年才有足夠密度可看

ITEM_RE = re.compile(r"Item[s]?\s+([\d.]+(?:\s+and\s+[\d.]+)*):\s*([^<\n]+?)(?=(?:<br|$))")


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _get(url: str, params: dict | None = None):
    """跟 fetch_us_insider_trading.py 同款：偶發逾時是暫時性網路問題，重試一次
    （非配額拒絕後的排隊重試，屬單純逾時重試，不受「取得方式鐵律」約束）。"""
    time.sleep(REQUEST_SLEEP_SEC)
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    except requests.exceptions.RequestException:
        time.sleep(1.0)
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r


def parse_items(summary_html: str) -> list[str]:
    """從 atom <summary>（HTML escaped 純文字）抓出「Item X.XX: 說明」清單。
    抓不到就回空陣列——不猜、不硬塞一個看起來合理的分類。"""
    if not summary_html:
        return []
    items = []
    for m in ITEM_RE.finditer(summary_html):
        items.append(f"Item {m.group(1).strip()}: {m.group(2).strip()}")
    return items


def list_recent_8k(cik: int) -> list[dict]:
    cik_padded = str(cik).zfill(10)
    r = _get(BROWSE_URL, params={
        "action": "getcompany", "CIK": cik_padded, "type": "8-K",
        "dateb": "", "owner": "include", "count": str(MAX_FILINGS_PER_TICKER),
        "output": "atom",
    })
    root = ET.fromstring(r.content)
    out = []
    for entry in root.findall("a:entry", ATOM_NS)[:MAX_FILINGS_PER_TICKER]:
        content = entry.find("a:content", ATOM_NS)
        if content is None:
            continue
        acc = content.findtext("a:accession-number", default=None, namespaces=ATOM_NS)
        fd = content.findtext("a:filing-date", default=None, namespaces=ATOM_NS)
        href = content.findtext("a:filing-href", default=None, namespaces=ATOM_NS)
        ftype = content.findtext("a:filing-type", default=None, namespaces=ATOM_NS)
        if not (acc and fd and href):
            continue
        summary_el = entry.find("a:summary", ATOM_NS)
        summary_txt = summary_el.text if summary_el is not None else ""
        out.append({
            "accession": acc,
            "filed_at": fd,
            "url": href,
            "filing_type": ftype or "8-K",
            "items": parse_items(summary_txt or ""),
        })
    return out


def fetch_ticker(cik: int) -> tuple[list[dict], list[str]]:
    try:
        filings = list_recent_8k(cik)
        return filings, []
    except Exception as e:  # noqa: BLE001
        return [], [f"列出8-K申報失敗：{type(e).__name__}: {e}"]


def main() -> int:
    sic = _load(SIC_PATH, {}) or {}
    tickers_map = sic.get("tickers") or {}
    if not tickers_map:
        print(f"錯誤：讀不到 {SIC_PATH}（需先跑 fetch_us_sic.py 產生CIK對映）")
        return 1

    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    out_tickers: dict[str, dict] = {}
    all_errors: list[dict] = []
    for ticker, info in tickers_map.items():
        cik = info.get("cik")
        if cik is None:
            all_errors.append({"ticker": ticker, "reason": "us_sic.json沒有cik欄位"})
            print(f"  ・{ticker}: 沒有 cik 欄位，跳過")
            continue
        filings, errs = fetch_ticker(cik)
        filings = [f for f in filings if f["filed_at"] >= cutoff]
        filings.sort(key=lambda f: f["filed_at"], reverse=True)
        out_tickers[ticker] = {
            "cik": cik,
            "entity_name": info.get("entity_name"),
            "filings": filings,
            "errors": errs,
        }
        print(f"  ・{ticker}: {len(filings)} 筆8-K（近{KEEP_DAYS}天），錯誤{len(errs)}筆")
        if errs:
            all_errors.append({"ticker": ticker, "reasons": errs})

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "SEC EDGAR官方 Form 8-K（browse-edgar atom feed，只存索引，免金鑰）",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K",
        "keep_days": KEEP_DAYS,
        "max_filings_per_ticker": MAX_FILINGS_PER_TICKER,
        "errors": all_errors,
        "tickers": out_tickers,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total = sum(len(v["filings"]) for v in out_tickers.values())
    print(f"寫入 {OUT_PATH}，{len(out_tickers)} 檔、共 {total} 筆8-K"
          + (f"，{len(all_errors)}檔有錯誤" if all_errors else ""))
    return 0 if out_tickers else 1


if __name__ == "__main__":
    raise SystemExit(main())
