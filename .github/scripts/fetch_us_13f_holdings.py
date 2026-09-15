# -*- coding: utf-8 -*-
"""每日排程更新 data/us_13f_holdings.json（SEC EDGAR Form 13F機構持倉季報，
僅追蹤指標型申報人，僅比對本專案既有美股追蹤清單）。

`PENDING_QUEUE.md`「源頭二.3」第6名：13F（機構持倉季報）用途強度高（機構
投資人常態關注「聰明錢在買什麼」），但接入成本高——13F沒有官方ticker欄位，
只有`nameOfIssuer`（發行人名稱）與`cusip`，要做「全市場13F整合」（誰持有
哪些股票）需要CUSIP↔ticker對映表（本身是商業資料，非免費公開），規模遠超
一輪工作單位。

**本輪刻意大幅縮小範圍，誠實只做這一件事**：只追蹤**波克夏海瑟威一家**
申報人（CIK 1067983，最知名、最被公開關注的13F申報人，每季公布時是財經
媒體固定報導的「巴菲特持股」），比對它最新一份13F持股清單裡的`nameOfIssuer`
是否**精確**（大小寫不敏感的完全比對，不是模糊子字串）命中`ISSUER_NAME_MAP`
裡手動核對過的名稱，只有命中才記錄，沒命中就是誠實的「這季沒有這檔」，不是
抓取失敗。**不做**CUSIP對映、不做全市場13F整合、不擴大到其他申報人——那些
留給後續輪次視需要決定要不要投入（成本遠高於本輪其他四個已接入項目）。

`ISSUER_NAME_MAP`的每一筆都是**看過真實13F XML內容後手動核對**寫死的，
不是猜的或用字串相似度算出來的（2026-09-15查證波克夏最新一期13F
`accession=0001193125-26-352200`實際持股清單，交叉比對本專案`data/
us_sic.json`既有追蹤的9檔美股清單，只有APPLE INC/ALPHABET INC兩檔在
裡面，其餘7檔本季確實沒有）。

端點（SEC EDGAR官方，免金鑰）：
1. `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&output=atom`
   —— 列出該申報人最近的13F-HR申報。
2. `https://www.sec.gov/Archives/edgar/data/{cik}/{accession無dash}/index.json`
   —— 找出資訊表XML檔名（**已知地雷**：目錄裡通常有`primary_doc.xml`
   （封面頁）跟另一個數字檔名的xml（資訊表本體，例如`56757.xml`）——
   優先挑檔名不是`primary_doc.xml`且內容含`informationTable`的那個，
   不能靠猜檔名規則，因為每個申報人的資訊表檔名不固定）。
3. 資訊表XML —— 逐筆`infoTable`（`nameOfIssuer`/`cusip`/`value`/
   `shrsOrPrnAmt.sshPrnamt`）。

**已知地雷（2026-09-15實測發現，容易踩錯）**：13F紙本申報年代的慣例是
`value`欄位單位為「千美元」，但2026-09-15實測波克夏最新XML申報，用
`value/shares`反推每股隱含價格：AAPL約$289.36/股、GOOGL（混合A/C股）約
$356.33/股，皆是合理的當期股價量級——**代表這份XML技術檔的`value`欄位
其實是「整數美元」，不是「千美元」**。若照紙本慣例誤乘1000，會得到荒謬
的天文數字（例如AAPL變成每股近29萬美元）。本專案`value_usd`欄位**直接
存原始數字、不做任何倍數轉換**，前端顯示時才自行除以1e6換算成百萬美元。

SEC公平使用政策建議上限約10 req/sec，這裡沿用`fetch_us_sic.py`/`fetch_us_
insider_trading.py`同款保守間隔（每次請求後sleep 0.2秒）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "us_13f_holdings.json"

HEADERS = {"User-Agent": "AlphaApp-US13F contact@alpha-app-project.example"}
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
REQUEST_SLEEP_SEC = 0.2

FILERS = {
    "berkshire_hathaway": {"name": "Berkshire Hathaway Inc", "cik": 1067983},
}

# 2026-09-15實際看過波克夏最新13F XML內容後手動核對，非猜測、非字串相似度比對。
ISSUER_NAME_MAP = {
    "APPLE INC": "AAPL",
    "ALPHABET INC": "GOOGL",
    "MICROSOFT CORP": "MSFT",
    "NVIDIA CORP": "NVDA",
    "AMAZON COM INC": "AMZN",
}


def _get(url: str, params: dict | None = None):
    time.sleep(REQUEST_SLEEP_SEC)
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r


def latest_13f_accession(cik: int) -> tuple[str, str] | None:
    r = _get(BROWSE_URL, params={
        "action": "getcompany", "CIK": str(cik).zfill(10), "type": "13F-HR",
        "dateb": "", "owner": "include", "count": "1", "output": "atom",
    })
    root_text = r.text
    acc = re.search(r"<accession-number>(.*?)</accession-number>", root_text)
    fd = re.search(r"<filing-date>(.*?)</filing-date>", root_text)
    if not acc or not fd:
        return None
    return acc.group(1), fd.group(1)


def find_infotable_xml(cik: int, accession: str) -> str | None:
    accnodash = accession.replace("-", "")
    r = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/index.json")
    items = r.json().get("directory", {}).get("item", [])
    candidates = [it["name"] for it in items if it["name"].lower().endswith(".xml") and it["name"] != "primary_doc.xml"]
    for name in candidates:
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/{name}"
        r2 = _get(url)
        if "informationTable" in r2.text:
            return url
    return None


def parse_infotable(xml_text: str) -> list[dict]:
    rows = []
    for block in re.findall(r"<infoTable>(.*?)</infoTable>", xml_text, re.S):
        name = re.search(r"<nameOfIssuer>(.*?)</nameOfIssuer>", block)
        cusip = re.search(r"<cusip>(.*?)</cusip>", block)
        value = re.search(r"<value>(.*?)</value>", block)
        shares = re.search(r"<sshPrnamt>(.*?)</sshPrnamt>", block)
        rows.append({
            "name_of_issuer": name.group(1) if name else None,
            "cusip": cusip.group(1) if cusip else None,
            "value_usd": int(value.group(1)) if value else None,
            "shares": int(shares.group(1)) if shares else None,
        })
    return rows


def main() -> int:
    out_filers: dict[str, dict] = {}
    all_errors: list[dict] = []

    for key, info in FILERS.items():
        try:
            latest = latest_13f_accession(info["cik"])
            if not latest:
                all_errors.append({"filer": key, "reason": "查無13F-HR申報"})
                continue
            accession, filed_at = latest
            xml_url = find_infotable_xml(info["cik"], accession)
            if not xml_url:
                all_errors.append({"filer": key, "reason": f"{accession}：目錄裡找不到資訊表xml"})
                continue
            xml_text = _get(xml_url).text
            rows = parse_infotable(xml_text)
        except Exception as e:
            all_errors.append({"filer": key, "reason": str(e)})
            print(f"  ・{key}: 抓取失敗 {e}")
            continue

        # 2026-09-15實測發現：同一發行人常拆成多筆infoTable列（不同子公司/被授權
        # 管理人各自的投票權分配，SEC 13F combination filing的標準格式，非重複列，
        # 見腳本docstring）——必須全部加總才是真實總持股，只取其中一列會嚴重
        # 低估（甚至只取最大或最後一列會拿到錯誤數字）。
        holdings: dict[str, dict] = {}
        for row in rows:
            ticker = ISSUER_NAME_MAP.get((row["name_of_issuer"] or "").strip().upper())
            if not ticker:
                continue
            if ticker not in holdings:
                holdings[ticker] = {
                    "name_of_issuer": row["name_of_issuer"],
                    "cusips": [],
                    "value_usd": 0,
                    "shares": 0,
                    "row_count": 0,
                }
            h = holdings[ticker]
            h["value_usd"] += row["value_usd"] or 0
            h["shares"] += row["shares"] or 0
            h["row_count"] += 1
            if row["cusip"] and row["cusip"] not in h["cusips"]:
                h["cusips"].append(row["cusip"])
        out_filers[key] = {
            "name": info["name"],
            "cik": info["cik"],
            "accession": accession,
            "filed_at": filed_at,
            "total_positions_in_filing": len(rows),
            "holdings": holdings,
        }
        print(f"  ・{key}: 申報日{filed_at}，共{len(rows)}筆持股，命中追蹤清單{len(holdings)}檔")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "SEC EDGAR官方Form 13F-HR（browse-edgar atom feed + 資訊表XML），免金鑰",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR",
        "note": "本輪刻意只追蹤波克夏海瑟威一家申報人（未做CUSIP對映/全市場13F整合），只比對ISSUER_NAME_MAP裡手動核對過的5檔ticker，其餘美股追蹤清單本項不適用；holdings裡沒有的ticker代表該申報人這一期確實沒有該檔部位，非抓取失敗；shares/value_usd是同一nameOfIssuer底下所有infoTable列（不同子公司/被授權管理人各自持有的區塊，可能含不同股份類別如GOOGL Class A/C）加總後的結果，非單一列",
        "filers": out_filers,
        "errors": all_errors,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"寫入 {OUT_PATH}，{len(out_filers)} 家申報人" + (f"，{len(all_errors)}筆錯誤" if all_errors else ""))
    return 0 if out_filers else 1


if __name__ == "__main__":
    raise SystemExit(main())
