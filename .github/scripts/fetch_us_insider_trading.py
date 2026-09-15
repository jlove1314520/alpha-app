# -*- coding: utf-8 -*-
"""每日排程更新 data/us_insider_trading.json（美股內部人交易，SEC EDGAR Form 4）。

`PENDING_QUEUE.md`「源頭二.3」（依機構用途強度×接入成本排前10名先接入）第2名：
內部人買賣是機構投資人常態監控的核心指標之一（內部人買進常被視為對公司前景
有信心的訊號），資料源是 SEC EDGAR 官方公開端點、免金鑰，符合 CLAUDE.md「美股
一律用美股原生資料源」的裁示（不繞道台灣資料商）。

涵蓋範圍：跟 fetch_us_sic.py 的 US_TICKERS 用同一份 ticker→CIK 對映——直接讀
data/us_sic.json（同一個 market.yml 排程裡本腳本排在 fetch_us_sic.py 之後執行，
零額外請求去重打 company_tickers.json）；若讀不到某檔 CIK 則該檔跳過並記錄
原因，不整份失敗。

端點（SEC EDGAR 官方，免金鑰）：
1. https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&owner=include&count={N}&output=atom
   —— 列出該發行人最近 N 筆 Form 4 申報（accession number/申報日/連結）。
   2026-09-15 實測：本專案追蹤股票（AAPL）用真實 CIK 打過，回應含逐筆申報
   accession-number/filing-date/filing-href，格式穩定。
2. https://www.sec.gov/Archives/edgar/data/{cik}/{accession無dash}/index.json
   —— 該筆申報的檔案目錄，找出 .xml 檔名（申報人不同、檔名不固定，例如
   form4.xml，這裡用「找目錄裡的 .xml 檔」而非寫死檔名，避免踩到命名差異）。
3. 上一步找到的 xml —— Form 4 結構化申報內容（reportingOwner/nonDerivativeTable/
   derivativeTable），逐筆解析交易日期/代號/股數/價格/交易後持股。
   2026-09-15 實測：AAPL 2026-09-10 申報（SVP Jennifer Newstead 賣出1438股，
   均價317.23，代碼S）欄位路徑與下方解析邏輯一致。

SEC 公平使用政策建議上限約 10 req/sec，這裡跟 fetch_us_sic.py 同款保守間隔
（每次請求後 sleep 0.2 秒；9 檔 * 最多 (1+8*2) 次請求 ≈ 153 次，約 30 秒跑完，
遠低於門檻）。User-Agent 沿用專案識別用佔位信箱（同 fetch_us_sic.py 理由：
不把使用者本人 email 外流給不相關第三方服務）。

**誠實限制**：外國私人發行人（本清單裡的 UMC/ASX/CHT 台股ADR）多數依規定豁免
Section 16 申報義務，預期查到 0 筆是正常狀態，不是抓取失敗。
每檔只取最近 MAX_FILINGS_PER_TICKER 筆 Form 4（避免不活躍申報人的歷史清單
過長時處理過多請求），交易代碼中文對照見 TRANSACTION_CODE_LABELS（SEC官方
Form 4 說明書 Table I/II 代碼定義）。
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "us_insider_trading.json"
SIC_PATH = REPO_ROOT / "data" / "us_sic.json"

HEADERS = {"User-Agent": "AlphaApp-USInsiderTrading contact@alpha-app-project.example"}
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
BROWSE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
REQUEST_SLEEP_SEC = 0.2
MAX_FILINGS_PER_TICKER = 8

TRANSACTION_CODE_LABELS = {
    "P": "公開市場買進", "S": "公開市場賣出", "A": "獎酬/授予取得",
    "D": "處分予發行人", "F": "稅務代扣", "M": "選擇權履約",
    "G": "贈與", "C": "轉換", "X": "選擇權到期履約",
    "J": "其他（申報書另行說明）", "K": "可交換權益設質",
}


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _get(url: str, params: dict | None = None):
    """`browse-edgar`（CGI端點）實測比data.sec.gov/Archives慢，偶發read timeout，
    這是暫時性網路問題不是配額問題，重試一次（非「硬性配額拒絕後排隊重試」，
    見CLAUDE.md「取得方式鐵律」——那條規範的是被判定超限後的行為，跟這裡的
    單純逾時重試是兩回事）。"""
    time.sleep(REQUEST_SLEEP_SEC)
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    except requests.exceptions.RequestException:
        time.sleep(1.0)
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r


def list_recent_form4(cik: int) -> list[dict]:
    cik_padded = str(cik).zfill(10)
    r = _get(BROWSE_URL, params={
        "action": "getcompany", "CIK": cik_padded, "type": "4",
        "dateb": "", "owner": "include", "count": str(MAX_FILINGS_PER_TICKER),
        "output": "atom",
    })
    root = ET.fromstring(r.content)
    out = []
    for entry in root.findall("a:entry", ATOM_NS)[:MAX_FILINGS_PER_TICKER]:
        acc = entry.find(".//a:accession-number", ATOM_NS)
        fd = entry.find(".//a:filing-date", ATOM_NS)
        if acc is None or fd is None:
            continue
        out.append({"accession": acc.text, "filed_at": fd.text})
    return out


def find_xml_doc(cik: int, accession: str) -> str | None:
    accnodash = accession.replace("-", "")
    r = _get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accnodash}/index.json")
    items = r.json().get("directory", {}).get("item", [])
    xml_names = [it["name"] for it in items if it["name"].lower().endswith(".xml")]
    if not xml_names:
        return None
    for n in xml_names:  # 優先挑檔名含form4的（多數申報人慣例），沒有就取第一個.xml
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
                continue  # 只取異動(Transaction)，跳過單純持股揭露(Holding)紀錄
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


def fetch_ticker(cik: int) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    transactions: list[dict] = []
    try:
        filings = list_recent_form4(cik)
    except Exception as e:
        errors.append(f"列出Form4申報失敗：{e}")
        return transactions, errors
    for f in filings:
        try:
            xml_url = find_xml_doc(cik, f["accession"])
            if not xml_url:
                errors.append(f"{f['accession']}：目錄裡找不到.xml檔")
                continue
            r = _get(xml_url)
            transactions.extend(parse_form4_xml(r.content, f["accession"], f["filed_at"]))
        except Exception as e:
            errors.append(f"{f['accession']}：解析失敗 {e}")
    transactions.sort(key=lambda t: t.get("transaction_date") or "", reverse=True)
    return transactions, errors


def main() -> int:
    sic = _load(SIC_PATH, {}) or {}
    tickers_map = sic.get("tickers") or {}
    if not tickers_map:
        print(f"錯誤：讀不到 {SIC_PATH}（需先跑 fetch_us_sic.py 產生CIK對映）")
        return 1

    out_tickers: dict[str, dict] = {}
    all_errors: list[dict] = []
    for ticker, info in tickers_map.items():
        cik = info.get("cik")
        if cik is None:
            all_errors.append({"ticker": ticker, "reason": "us_sic.json沒有cik欄位"})
            print(f"  ・{ticker}: 沒有 cik 欄位，跳過")
            continue
        txns, errs = fetch_ticker(cik)
        buys = sum(1 for t in txns if t["code"] == "P")
        sells = sum(1 for t in txns if t["code"] == "S")
        out_tickers[ticker] = {
            "cik": cik,
            "transactions": txns,
            "buy_count": buys,
            "sell_count": sells,
            "errors": errs,
        }
        print(f"  ・{ticker}: {len(txns)} 筆交易（買{buys}/賣{sells}），錯誤{len(errs)}筆")
        if errs:
            all_errors.append({"ticker": ticker, "reasons": errs})

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "SEC EDGAR官方 Form 4（browse-edgar atom feed + 申報XML），免金鑰",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4",
        "max_filings_per_ticker": MAX_FILINGS_PER_TICKER,
        "errors": all_errors,
        "tickers": out_tickers,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total_txns = sum(len(v["transactions"]) for v in out_tickers.values())
    print(f"寫入 {OUT_PATH}，{len(out_tickers)} 檔、共 {total_txns} 筆交易"
          + (f"，{len(all_errors)}檔有錯誤" if all_errors else ""))
    return 0 if out_tickers else 1


if __name__ == "__main__":
    raise SystemExit(main())
