# -*- coding: utf-8 -*-
"""每日排程更新 data/cftc_cot.json（CFTC COT 部位報告，美股大盤情緒指標）。

`PENDING_QUEUE.md`「源頭二.3」第3名：CFTC 每週公布的 Commitments of Traders
報告，記錄期貨市場各類交易者（非商業/投機客 vs 商業/避險者）的淨部位，是
機構投資人常態監控的市場情緒指標之一（例如「投機客淨多單創新高」常被當成
反指標警訊）。

資料源（CFTC 官方 Socrata Public Reporting Environment，免金鑰）：
https://publicreporting.cftc.gov/resource/6dca-aqww.json
（Legacy Futures Only 報告，CFTC 自己的公開資料入口，非第三方鏡像；
2026-09-15 實測：`$where=market_and_exchange_names like '%...%'` 語法可用，
`requests` 會自動把 `%` 正確編碼成 `%25`，**不要自己手動加 `%25`**——手動加
會被 `requests` 二次編碼成 `%2525`，導致 `$where` 完全比對不到任何列
（本專案已踩過這個坑，故寫進這裡避免重踩）。

追蹤三檔美股情緒相關合約（僅美股，因 CFTC 只涵蓋美國期貨市場，不含 TAIFEX）：
- S&P 500 Consolidated（CME，代碼 13874+）——官方合併標準+微型E-mini後的
  總計數字，是財經媒體常引用的「S&P 500 COT」口徑。
- NASDAQ-100 Consolidated（CME，代碼 20974+）——同上邏輯，Nasdaq口徑。
- VIX FUTURES（CBOE Futures Exchange，代碼 1170E1）——恐慌指數期貨部位，
  常被當成波動率情緒的輔助指標。

**誠實限制**：COT報告資料日固定為每週二，實際公布在該週五（美東時間），
所以「今天」抓到的可能還是上週二的舊資料，這是CFTC官方公布節奏本身如此，
不是本管線抓取延遲；`report_date_as_yyyy_mm_dd`欄位本身就標明真實資料日，
前端一律顯示這個日期而非抓取時間。每檔只取最近 HISTORY_WEEKS 週，用於
畫出淨部位變化趨勢（原始金額，非變化率——COT本身沒有標準化基準可供計算
百分比）。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "cftc_cot.json"

BASE_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
HEADERS = {"User-Agent": "AlphaApp-CftcCot contact@alpha-app-project.example"}
REQUEST_SLEEP_SEC = 0.5
HISTORY_WEEKS = 12

CONTRACTS = {
    "sp500": {"name": "S&P 500 Consolidated", "code": "13874+"},
    "nasdaq100": {"name": "NASDAQ-100 Consolidated", "code": "20974+"},
    "vix": {"name": "VIX FUTURES", "code": "1170E1"},
}


def fetch_contract(code: str) -> list[dict]:
    params = {
        "$where": f"cftc_contract_market_code = '{code}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": str(HISTORY_WEEKS),
    }
    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def main() -> int:
    out_contracts: dict[str, dict] = {}
    all_errors: list[dict] = []

    for key, info in CONTRACTS.items():
        time.sleep(REQUEST_SLEEP_SEC)
        try:
            rows = fetch_contract(info["code"])
        except Exception as e:
            all_errors.append({"contract": key, "reason": str(e)})
            print(f"  ・{key}: 抓取失敗 {e}")
            continue
        if not rows:
            all_errors.append({"contract": key, "reason": "查無資料（合約代碼可能已變更，需人工核對）"})
            print(f"  ・{key}: 查無資料")
            continue
        history = []
        for row in rows:
            try:
                long_ = float(row["noncomm_positions_long_all"])
                short_ = float(row["noncomm_positions_short_all"])
            except (KeyError, ValueError, TypeError):
                continue
            history.append({
                "date": row.get("report_date_as_yyyy_mm_dd", "")[:10],
                "noncomm_long": int(long_),
                "noncomm_short": int(short_),
                "net": int(long_ - short_),
                "open_interest": int(float(row["open_interest_all"])) if row.get("open_interest_all") else None,
            })
        history.sort(key=lambda h: h["date"])
        out_contracts[key] = {
            "name": info["name"],
            "cftc_contract_market_code": info["code"],
            "history": history,
        }
        latest = history[-1] if history else None
        print(f"  ・{key}: {len(history)} 週，最新資料日 {latest['date'] if latest else '—'}"
              f"（淨部位 {latest['net'] if latest else '—'}）")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "CFTC官方 Public Reporting Environment（Socrata，Legacy Futures Only報告），免金鑰",
        "url": BASE_URL,
        "note": "資料日為COT報告日（固定週二），官方於當週五公布，非即時；淨部位=非商業(投機客)多單-空單，正值代表淨多、負值代表淨空",
        "history_weeks": HISTORY_WEEKS,
        "errors": all_errors,
        "contracts": out_contracts,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"寫入 {OUT_PATH}，{len(out_contracts)} 個合約"
          + (f"，{len(all_errors)}筆錯誤" if all_errors else ""))
    return 0 if out_contracts else 1


if __name__ == "__main__":
    raise SystemExit(main())
