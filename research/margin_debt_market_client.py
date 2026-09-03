"""TWSE MI_MARGN 全市場信用交易統計 client（2026-09-03，`HYPOTHESIS_QUEUE.md`
#26 全市場融資餘額成長率 regime 訊號用）。

**資料來源**：`https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN`
（`rwd`舊式AJAX端點，同`twse_t86_client.py`的T86端點同一家族，不是
`openapi.twse.com.tw`正式開放資料——本輪排程接續2026-09-03先前輪次的
資料可行性查證結果，見`HYPOTHESIS_QUEUE.md`#26條目）。

**已知編碼陷阱（本輪探測新發現，不在`CLAUDE.md`既有地雷清單裡）**：
`requests`的`.json()`內建編碼偵測在這個API上會誤判成非UTF-8，中文欄位
名稱/標題會變亂碼——必須手動`json.loads(resp.content.decode('utf-8'))`，
不能用`resp.json()`。

**回傳結構**：`body['tables']`是長度2的list：
- `tables[0]`：全市場加總統計，6欄（項目/買進/賣出/現金(券)償還/前日
  餘額/今日餘額），3列（融資(交易單位)/融券(交易單位)/融資金額(仟元)）
  ——本模組只取第3列「融資金額(仟元)」的「今日餘額」，這正是全市場
  總融資餘額（單位：仟元，即千元新台幣）。
- `tables[1]`：1200+檔個股逐檔明細，本模組不使用，用不到就不解析
  （避免浪費解析成本+降低schema依賴面）。

**快取設計**：逐日一個parquet檔（同`twse_t86_client.py`同一種atomic
read/write pattern，防併發寫入截斷），`stat!='OK'`（假日/非交易日）
也快取成一個標記空值的row，避免重複請求同一個非交易日。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data" / "raw_margin_debt_market"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"

_COLS = ["date", "is_trading_day", "financing_amount_today_balance_kNTD",
         "financing_amount_buy_kNTD", "financing_amount_sell_kNTD",
         "financing_amount_prev_balance_kNTD"]


class TWSEBlockedError(RuntimeError):
    """跟`twse_t86_client.py::TWSEBlockedError`同一種偵測（同`rwd`端點家族，
    保守假設共用反爬蟲機制，未實測驗證是否真的共用IP層級封鎖，但用同一套
    防呆邏輯處理沒有壞處）——呼叫端應立刻停止，不要重試。"""


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    """跟`twse_t86_client.py::_atomic_read_parquet()`同一份修法，自成一體
    複製（Windows下另一process正在os.replace()換名時讀取會遇到暫時性
    PermissionError，加短重試）。"""
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """跟`twse_t86_client.py::_atomic_to_parquet()`同一份修法，自成一體
    複製。"""
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    df.to_parquet(tmp_path, index=False)
    for attempt in range(20):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _cache_path(date_str: str) -> Path:
    return DATA_DIR / f"MARGIN_{date_str}.parquet"


def _num(v) -> float | None:
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_margin_market_day(date_str: str, force_refresh: bool = False,
                             timeout: float = 15.0, max_retries: int = 3) -> pd.DataFrame:
    """單一交易日的全市場融資餘額彙總（一列DataFrame）。date_str='YYYYMMDD'。
    非交易日（假日）回傳`is_trading_day=False`、金額欄位皆為`None`的一列
    （不是空DataFrame——保留欄位結構方便後續concat），且會被快取，之後
    同一天不會重複打API。"""
    path = _cache_path(date_str)
    if path.exists() and not force_refresh:
        return _atomic_read_parquet(path)

    last_err: Exception | None = None
    body = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(MARGIN_URL, params={
                "response": "json", "date": date_str, "selectType": "ALL",
            }, timeout=timeout)
            if "FOR SECURITY REASONS" in resp.text or resp.status_code == 307:
                raise TWSEBlockedError(
                    f"TWSE MI_MARGN 端點回傳反爬蟲封鎖頁（date={date_str}）——"
                    "跟`twse_t86_client.py`記錄的T86端點封鎖是同一種伺服器端"
                    "主動封鎖，重試無用，需停止呼叫並等待未知冷卻時間。"
                )
            resp.raise_for_status()
            body = json.loads(resp.content.decode("utf-8"))
            break
        except TWSEBlockedError:
            raise
        except Exception as e:  # noqa: BLE001 -- network/5xx/timeout: worth retrying
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"MI_MARGN fetch failed after {max_retries} attempts for date={date_str}: {last_err}")

    date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    if not isinstance(body, dict) or body.get("stat") != "OK" or not body.get("tables"):
        out = pd.DataFrame([{
            "date": date_iso, "is_trading_day": False,
            "financing_amount_today_balance_kNTD": None,
            "financing_amount_buy_kNTD": None, "financing_amount_sell_kNTD": None,
            "financing_amount_prev_balance_kNTD": None,
        }], columns=_COLS)
        _atomic_to_parquet(out, path)
        return out

    table0 = body["tables"][0]
    fields = table0.get("fields", [])
    rows = table0.get("data", [])
    try:
        i_buy = fields.index("買進")
        i_sell = fields.index("賣出")
        i_prev = fields.index("前日餘額")
        i_today = fields.index("今日餘額")
    except ValueError:
        raise RuntimeError(f"MI_MARGN table0 fields 跟預期不符（date={date_str}）：{fields}")

    amount_row = None
    for r in rows:
        if str(r[0]).strip() == "融資金額(仟元)":
            amount_row = r
            break
    if amount_row is None:
        raise RuntimeError(f"MI_MARGN table0 找不到「融資金額(仟元)」列（date={date_str}）："
                            f"{[r[0] for r in rows]}")

    out = pd.DataFrame([{
        "date": date_iso, "is_trading_day": True,
        "financing_amount_today_balance_kNTD": _num(amount_row[i_today]),
        "financing_amount_buy_kNTD": _num(amount_row[i_buy]),
        "financing_amount_sell_kNTD": _num(amount_row[i_sell]),
        "financing_amount_prev_balance_kNTD": _num(amount_row[i_prev]),
    }], columns=_COLS)
    _atomic_to_parquet(out, path)
    return out


def load_all_cached() -> pd.DataFrame:
    """把`DATA_DIR`裡所有已快取的日期組成一條按日期排序的時間序列（只留
    `is_trading_day=True`且金額非None的列）。"""
    frames = []
    for p in sorted(DATA_DIR.glob("MARGIN_*.parquet")):
        try:
            frames.append(_atomic_read_parquet(p))
        except Exception:  # noqa: BLE001 -- 單一壞檔不應讓整條序列載入失敗
            continue
    if not frames:
        return pd.DataFrame(columns=_COLS)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["is_trading_day"] == True]  # noqa: E712
    df = df.dropna(subset=["financing_amount_today_balance_kNTD"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
