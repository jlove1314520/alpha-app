# -*- coding: utf-8 -*-
"""每日排程更新 data/securities_lending_sell.json（借券賣出當日成交量，非可借額度）。

`PENDING_QUEUE.md`「源頭一.2b」：「借券賣出：查TWSE/TPEx官方端點文件，確認免費
可得後接入」。這是`docs/DATA_SOURCE_MAP.md`「源頭一.1」表格第7項標成🟡待建的
後續工作——源頭一.1只確認了端點存在與摘要文字，本檔案是實際接入。

**跟已有的 `data/short_lending_available.json`（源頭二.3第5名）是兩件不同的事**，
不要混為一談：
- `short_lending_available.json`（`fetch_short_lending_available.py`）＝
  TWSE `SBL/TWT96U`＝**當日可借券賣出股數**（借券供給水位／庫存量）。
- 本檔案 `securities_lending_sell.json` ＝**借券賣出當日「成交」量**（已經借券
  賣出、造成實際放空部位增加的當日活動），是完全不同的經濟意涵——前者是
  「還剩多少可以借」，後者是「今天實際借出去賣了多少」。

**兩個官方端點（本輪2026-09-15實測`curl`直接呼叫確認欄位）**：

1. **TWSE（上市）**：`https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U
   ?response=json`（**不在`openapi.twse.com.tw`的143個端點清單裡**，是
   `www.twse.com.tw/rwd`主站家族的端點，跟T86/MI_QFIIS/TWTASU/BFIAUU同一組，
   已查證的robots.txt允許範圍涵蓋此路徑）。
   官方標題「信用額度總量管制餘額表」，`fields`有15欄，**同名「前日餘額」
   出現兩次、代表兩個不同的信用管制群組**，用「index位置」而非欄位名稱對應
   （因為JSON陣列的重複key在轉dict時後者會覆蓋前者，這是本輪實測踩到、
   已在程式碼用index直接切片避免的地雷）：
   - 群組A（index 2~7，融券信用管制）：前日餘額／賣出／買進／現券／今日餘額／
     次一營業日限額——這是「融券」（一般信用交易放空）在總量管制名單下的
     餘額變化，**不是本檔案要接的東西**（跟`MI_MARGN`的一般融資融券是不同的
     管制子集，避免跟既有`update_margin_maintenance.py`重複，本檔案不擷取）。
   - 群組B（index 8~13，借券信用管制）：前日餘額／**當日賣出**／當日還券／
     當日調整／當日餘額／次一營業日可限額——**這就是借券賣出當日成交量**。
     本輪用台積電（2330）2026-09-14資料驗證餘額勾稽恆等式：
     前日餘額(16,244,514) − 當日還券(26,000) + 當日賣出(318,000)
     + 當日調整(0) = 當日餘額(16,536,514)，數字兜得起來，判定資料可信。
   - 支援`date=YYYYMMDD`歷史查詢參數（本輪實測`date=20260910`回傳
     `stat=OK`且`date`欄位吻合，證實可回溯查詢，但本輪只做每日快照接入，
     未做全歷史回補——回補另立工作單位，避免一輪塞兩種性質的工作）。
   - **實測涵蓋範圍**：2026-09-15實測回傳1,301檔，其中813檔（62%）當日
     `sbl_sell`（借券賣出）非零，涵蓋範圍比預期廣（原以為「信用額度總量
     管制」只適用少數觸發管制的個股，實測結果推翻此假設，**如實更正**：
     這張表看起來是全體上市股票的借券信用管制餘額表，不是限縮子集）。
     個別股票單日剛好0是正常現象（當天沒有新增借券賣出），不是抓取失敗。

2. **TPEx（上櫃）**：`https://www.tpex.org.tw/openapi/v1/tpex_short_sell`
   （「上櫃當日融券賣出與借券賣出成交量值」，本輪實測欄位：`Date`／
   `SecuritiesCompanyCode`／`CompanyName`／`ShortSaleVolume`／
   `ShortSaleAmount`（融券賣出）／`SBLVolume`／`SBLAmount`（借券賣出，本檔案
   要接的欄位）。`Date`為民國年格式（例如`1150914`＝2026-09-14），本檔案原樣
   保留字串、不轉換曆法，避免引入額外解析錯誤面。此端點未見支援歷史`date`
   查詢參數（不像TWSE的rwd家族），只回傳最新一個交易日的快照。

**誠實限制**：TWSE的表名叫「信用額度總量管制餘額表」，字面上暗示是限縮
子集，但2026-09-15實測1,301檔裡有813檔（62%）當日借券賣出非零，涵蓋範圍
比表名暗示的更廣，本檔案不代替官方重新定義這張表的適用範圍，只如實接入
欄位並記錄實測涵蓋率，讓使用者自己判斷。TPEx為全體上櫃股票逐檔資料。
兩邊口徑（欄位命名、是否支援歷史查詢）不完全一致，本檔案原樣保留差異，
不假裝兩邊口徑相同。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "securities_lending_sell.json"

TWSE_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_short_sell"
HEADERS = {"User-Agent": "AlphaApp-SecuritiesLendingSell contact@alpha-app-project.example"}

RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
TWSE_SOURCE = "twse_twt93u"


def _load_rate_limit_state() -> dict:
    try:
        return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    state = _load_rate_limit_state()
    src = state["sources"].get(source, {})
    now = time.time()
    blocked_until = src.get("blocked_until")
    if blocked_until and now < blocked_until:
        remain_min = round((blocked_until - now) / 60, 1)
        raise RuntimeError(
            f"{source} 目前處於封鎖冷卻中（還剩約{remain_min}分鐘，"
            f"原因：{src.get('block_reason', '未知')}），依「資料源禮儀」規則拒絕發送請求"
        )
    last = src.get("last_request_at")
    if last and (now - last) < RATE_LIMIT_MIN_INTERVAL_SEC:
        time.sleep(RATE_LIMIT_MIN_INTERVAL_SEC - (now - last))
    src["last_request_at"] = time.time()
    state["sources"][source] = src
    _save_rate_limit_state(state)


def _rate_limit_record_block(source: str, status_code: int, detail: str = "") -> None:
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}" + (f" {detail}" if detail else "")
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _to_num(s):
    if s in (None, "", "--", "_"):
        return None
    try:
        return float(str(s).replace(",", ""))
    except ValueError:
        return None


def fetch_twse() -> tuple[dict, str | None]:
    """回傳 (代號→借券賣出當日活動 的dict, 資料日期字串)。失敗回傳 ({}, None)。"""
    _rate_limit_wait_or_raise(TWSE_SOURCE)
    r = requests.get(TWSE_URL, params={"response": "json"}, headers=HEADERS, timeout=20)
    if r.status_code in (402, 403, 428, 429):
        _rate_limit_record_block(TWSE_SOURCE, r.status_code, r.text[:200])
        raise RuntimeError(f"{TWSE_SOURCE}回應HTTP {r.status_code}，已標記封鎖2小時：{r.text[:200]}")
    r.raise_for_status()
    body = r.json()
    if body.get("stat") != "OK" or not body.get("data"):
        return {}, None
    fields = body.get("fields") or []
    if len(fields) < 14:
        raise RuntimeError(f"TWT93U回應欄位數不符預期（{len(fields)}<14）：{fields}")
    out: dict[str, dict] = {}
    for row in body["data"]:
        if len(row) < 14:
            continue
        code = (row[0] or "").strip()
        if not code:
            continue
        out[code] = {
            "name": row[1],
            # 群組B（index 8~13）＝借券信用管制當日活動，見檔頭說明
            "sbl_prev_balance": _to_num(row[8]),
            "sbl_sell": _to_num(row[9]),
            "sbl_return": _to_num(row[10]),
            "sbl_adjust": _to_num(row[11]),
            "sbl_balance": _to_num(row[12]),
            "sbl_next_day_quota": _to_num(row[13]),
        }
    return out, body.get("date")


def fetch_tpex() -> tuple[dict, str | None]:
    r = requests.get(TPEX_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    rows = r.json()
    if not isinstance(rows, list) or not rows:
        return {}, None
    out: dict[str, dict] = {}
    date_str = None
    for row in rows:
        code = (row.get("SecuritiesCompanyCode") or "").strip()
        if not code:
            continue
        date_str = row.get("Date") or date_str
        out[code] = {
            "name": row.get("CompanyName"),
            "sbl_sell_volume": _to_num(row.get("SBLVolume")),
            "sbl_sell_amount": _to_num(row.get("SBLAmount")),
            "short_sale_volume": _to_num(row.get("ShortSaleVolume")),
            "short_sale_amount": _to_num(row.get("ShortSaleAmount")),
        }
    return out, date_str


def main() -> int:
    errors: list[str] = []
    twse, twse_date = {}, None
    try:
        twse, twse_date = fetch_twse()
    except Exception as e:
        errors.append(f"TWSE TWT93U：{e}")
        print(f"TWSE TWT93U 失敗：{e}")

    tpex, tpex_date = {}, None
    try:
        tpex, tpex_date = fetch_tpex()
    except Exception as e:
        errors.append(f"TPEx tpex_short_sell：{e}")
        print(f"TPEx tpex_short_sell 失敗：{e}")

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": (
            "TWSE官方rwd/zh/marginTrading/TWT93U「信用額度總量管制餘額表」借券信用管制群組"
            "＋TPEx官方openapi tpex_short_sell「上櫃當日融券賣出與借券賣出成交量值」，皆免金鑰"
        ),
        "urls": {"twse": TWSE_URL, "tpex": TPEX_URL},
        "note": (
            "借券賣出『成交量』，不是可借額度（那是data/short_lending_available.json）；"
            "TWSE只有觸發總量管制名單內的股票有非零活動，多數股票欄位為0屬正常；"
            "TPEx為全體上櫃股票逐檔資料"
        ),
        "twse_date": twse_date,
        "tpex_date": tpex_date,
        "errors": errors,
        "twse": twse,
        "tpex": tpex,
    }

    if not twse and not tpex:
        prior = None
        try:
            prior = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        if prior and (prior.get("twse") or prior.get("tpex")):
            print("本次兩邊都無新資料，保留既有檔案，不覆蓋")
            return 0
        print("本次兩邊都無新資料，且沒有既有檔案可保留")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT_PATH}：TWSE {len(twse)} 檔（資料日{twse_date}）、TPEx {len(tpex)} 檔（資料日{tpex_date}）")
    return 0 if (twse or tpex) else 1


if __name__ == "__main__":
    raise SystemExit(main())
