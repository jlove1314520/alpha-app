# -*- coding: utf-8 -*-
"""#75（美股內部人交易Form 4）歷史批次抓取——15檔pilot樣本地基工程。

跟 `.github/scripts/fetch_us_insider_trading.py` 的差異：那支是「每日抓最近
MAX_FILINGS_PER_TICKER=8筆」的即時快照排程，這支是「抓全歷史」的一次性批次
回補，供#75回測用。解析邏輯（Form 4 XML欄位路徑）與那支完全相同，此處重寫
一份精簡版而非跨目錄import（`.github/scripts/`不是套件、避免sys.path技巧），
但欄位定義與交易代碼對照表必須逐字保持一致，未來若那支的解析欄位改了要
同步檢查這裡。

端點（SEC EDGAR官方，免金鑰，PIT申報層級資料）：
1. https://data.sec.gov/submissions/CIK{cik:010d}.json
   —— `filings.recent`（近期）+ `filings.files`（更早分頁，需再各自GET）。
2. https://www.sec.gov/Archives/edgar/data/{cik}/{accession無dash}/index.json
   —— 找該筆申報目錄裡的.xml檔名。
3. 上一步xml —— Form 4結構化內容，逐筆解析。

SEC官方頻率上限10 req/秒（見CLAUDE.md「外部API頻率上限清單」SEC EDGAR段），
本腳本每次請求後sleep 0.2秒（約5 req/秒，同`fetch_us_insider_trading.py`
既有保守慣例）。15檔pilot樣本：見`CIK_PILOT_15`，選自`us_universe_pit.json`，
**誠實限制**：該檔案`delisted`旗標僅涵蓋Form 25近4季（約1年）掃描窗口
（2025-10~2026-09），train/val慣用起點約2015年的舊歷史下市公司完全不在
這份快照裡，本輪無法用它挑出「落在train/val視窗內的下市公司」；且AAPL/PG/
IBM三檔被標`delisted`但明顯是還在交易的公司（誤判，疑似Form 25資料源本身
有bug，非本輪修正範圍，如實記錄留給資料源維護帽），故15檔全數取自`active`
狀態的知名大型股，**尚未做到「混入下市股驗證管線」這一項**，是本輪誠實
未達成的目標，留給下一輪或待us_universe_pit.py修正涵蓋範圍後重新挑選。
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).resolve().parent / "data" / "form4_historical_pilot15.json"

HEADERS = {"User-Agent": "AlphaApp-USInsiderTradingHistorical contact@alpha-app-project.example"}
REQUEST_SLEEP_SEC = 0.2

TRANSACTION_CODE_LABELS = {
    "P": "公開市場買進", "S": "公開市場賣出", "A": "獎酬/授予取得",
    "D": "處分予發行人", "F": "稅務代扣", "M": "選擇權履約",
    "G": "贈與", "C": "轉換", "X": "選擇權到期履約",
    "J": "其他（申報書另行說明）", "K": "可交換權益設質",
}

# 15檔pilot樣本，CIK取自research/data/us_universe_pit.json（2026-09-19本輪
# 手動核對），皆為`active`狀態（見docstring誠實限制段）。
CIK_PILOT_15: dict[str, int] = {
    "MSFT": 789019, "NVDA": 1045810, "GOOGL": 1652044, "AMZN": 1018724,
    "META": 1326801, "JPM": 19617, "XOM": 2115436, "JNJ": 200406,
    "KO": 21344, "INTC": 50863, "GE": 40545, "F": 37996,
    "AAPL": 320193, "PG": 80424, "IBM": 51143,
}


def _get(url: str):
    time.sleep(REQUEST_SLEEP_SEC)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
    except requests.exceptions.RequestException:
        time.sleep(1.0)
        r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r


def list_all_form4(cik: int) -> list[dict]:
    """回傳該CIK全歷史Form 4申報清單（recent分頁+files舊分頁合併）。"""
    padded = str(cik).zfill(10)
    r = _get(f"https://data.sec.gov/submissions/CIK{padded}.json")
    data = r.json()
    out: list[dict] = []
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    for form, acc, fd in zip(forms, accns, dates):
        if form == "4":
            out.append({"accession": acc, "filed_at": fd})
    for f in data.get("filings", {}).get("files", []):
        name = f.get("name")
        if not name:
            continue
        try:
            r2 = _get(f"https://data.sec.gov/submissions/{name}")
            sub = r2.json()
        except Exception:
            continue
        forms2 = sub.get("form", [])
        accns2 = sub.get("accessionNumber", [])
        dates2 = sub.get("filingDate", [])
        for form, acc, fd in zip(forms2, accns2, dates2):
            if form == "4":
                out.append({"accession": acc, "filed_at": fd})
    return out


def find_xml_doc(cik: int, accession: str) -> str | None:
    accnodash = accession.replace("-", "")
    r = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/index.json")
    items = r.json().get("directory", {}).get("item", [])
    xml_names = [it["name"] for it in items if it["name"].lower().endswith(".xml")]
    if not xml_names:
        return None
    for n in xml_names:
        if "form4" in n.lower():
            return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/{n}"
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/{xml_names[0]}"


def _txt(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def _num(node, path):
    v = _txt(node, path)
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_form4_xml(xml_bytes: bytes, accession: str, filed_at: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    owner_name = _txt(root, "./reportingOwner/reportingOwnerId/rptOwnerName")
    rel = root.find("./reportingOwner/reportingOwnerRelationship")
    title = None
    if rel is not None:
        parts = []
        if _txt(rel, "./isOfficer") == "true":
            parts.append(_txt(rel, "./officerTitle") or "高階主管")
        if _txt(rel, "./isDirector") == "true":
            parts.append("董事")
        if _txt(rel, "./isTenPercentOwner") == "true":
            parts.append("10%以上大股東")
        title = "、".join(parts) if parts else None

    out = []
    for table_name in ("nonDerivativeTable", "derivativeTable"):
        table = root.find(f"./{table_name}")
        if table is None:
            continue
        for txn in table:
            if "Transaction" not in txn.tag:
                continue
            code = _txt(txn, "./transactionCoding/transactionCode")
            out.append({
                "reporting_owner": owner_name,
                "title": title,
                "transaction_date": _txt(txn, "./transactionDate/value"),
                "code": code,
                "code_label": TRANSACTION_CODE_LABELS.get(code, code),
                "shares": _num(txn, "./transactionAmounts/transactionShares/value"),
                "price": _num(txn, "./transactionAmounts/transactionPricePerShare/value"),
                "acquired_disposed": _txt(txn, "./transactionAmounts/transactionAcquiredDisposedCode/value"),
                "shares_owned_after": _num(txn, "./postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
                "security_title": _txt(txn, "./securityTitle/value"),
                "filed_at": filed_at,
                "accession": accession,
                "is_derivative": table_name == "derivativeTable",
            })
    return out


def fetch_ticker_full_history(ticker: str, cik: int) -> dict:
    errors: list[str] = []
    transactions: list[dict] = []
    try:
        filings = list_all_form4(cik)
    except Exception as e:
        errors.append(f"列出Form4申報失敗：{e}")
        return {"cik": cik, "transactions": [], "filing_count": 0, "errors": errors}
    seen_acc = set()
    for f in filings:
        if f["accession"] in seen_acc:
            continue
        seen_acc.add(f["accession"])
        try:
            xml_url = find_xml_doc(cik, f["accession"])
            if not xml_url:
                errors.append(f"{f['accession']}：目錄裡找不到.xml檔")
                continue
            r = _get(xml_url)
            transactions.extend(parse_form4_xml(r.content, f["accession"], f["filed_at"]))
        except Exception as e:
            errors.append(f"{f['accession']}：解析失敗 {e}")
    transactions.sort(key=lambda t: t.get("transaction_date") or "")
    dates = [t["transaction_date"] for t in transactions if t.get("transaction_date")]
    return {
        "cik": cik,
        "filing_count": len(seen_acc),
        "transaction_count": len(transactions),
        "earliest_transaction_date": min(dates) if dates else None,
        "latest_transaction_date": max(dates) if dates else None,
        "transactions": transactions,
        "errors": errors,
    }


def main() -> int:
    out_tickers: dict[str, dict] = {}
    for ticker, cik in CIK_PILOT_15.items():
        result = fetch_ticker_full_history(ticker, cik)
        out_tickers[ticker] = result
        print(
            f"  ・{ticker}(CIK{cik}): {result['filing_count']}筆申報／"
            f"{result['transaction_count']}筆交易，區間"
            f"{result.get('earliest_transaction_date')}~{result.get('latest_transaction_date')}，"
            f"錯誤{len(result['errors'])}筆"
        )
        if result["errors"]:
            for e in result["errors"][:5]:
                print(f"      錯誤：{e}")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "#75美股內部人交易假設——15檔pilot樣本全歷史Form 4回補（地基工程，非正式判定）",
        "source": "SEC EDGAR官方data.sec.gov/submissions + Archives申報XML，免金鑰",
        "known_limitation": (
            "15檔全取自us_universe_pit.json的active狀態，未含下市股——"
            "該檔案delisted旗標僅涵蓋近4季Form25掃描窗口(2025-10~2026-09)，"
            "train/val慣用起點約2015年的歷史下市公司不在快照內，"
            "且AAPL/PG/IBM三檔被誤標delisted（明顯仍在交易，疑似資料源bug，"
            "非本輪修正範圍）。"
        ),
        "tickers": out_tickers,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total = sum(v["transaction_count"] for v in out_tickers.values())
    print(f"寫入 {OUT_PATH}，{len(out_tickers)}檔、共{total}筆交易")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
