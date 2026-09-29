# -*- coding: utf-8 -*-
"""評.B-2 二：「上櫃轉上市（櫃轉市）」股票的上櫃起算日估計表。

問題：`twse_listing_dates.json`（TWSE `t187ap03_L`）裡的「上市日期」對櫃轉市
股票是「轉上市日」，不是首次掛牌日；`truncate_to_listing_date()`拿它截斷，
會把先前在上櫃掛牌期間（正常交易、有漲跌幅限制）的歷史整段誤砍。
TPEx名單只涵蓋「現存」上櫃公司，櫃轉市股票早已不在其中，兩個官方檔案都
查不到它們的上櫃日，官方端點也沒有歷史轉板紀錄（查過TPEx swagger 225個、
TWSE swagger 143個端點）。

做法（只用官方旗標＋既有價格快取，零FinMind請求、不碰holdout）：
1. 官方旗標：TWSE OpenAPI `/company/newlisting`（最近上市公司）的`Note`含
   「櫃轉市」者，即櫃轉市股票（正解，非猜測）。
2. 上櫃起算日「估計」：取該股轉上市日之前的價格列，把「近20列內有≥3個零成交量
   日」視為興櫃式的無流動性期間（上櫃股幾乎不會連續出現零成交量日），最後一個
   這種視窗結束後的下一個交易日即估計上櫃起算日；整段都沒有這種視窗者取第一筆
   價格日；整段都是興櫃式者不給估計（維持轉上市日截斷，不早於轉上市日）。
   這是資料推估、不是官方日期，輸出檔逐檔標明`basis`。
3. 只讀`*__2024-12-31.parquet`快取（VAL_END封頂），沒有快取的股票`otc_start_est`
   為null＝未估計，`universe.listing_date_lookup()`對這種股票不截斷（沿用
   「查無上市日→不截斷」既有職責邊界，見`truncate_to_listing_date()`），
   不再在轉上市日誤砍上櫃期間。新增價格快取後重跑本腳本即可補估計。

輸出：`research/data/otc_to_twse_dates.json`（research/data/被gitignore，
提交時用`git add -f`，與兩個上市日檔案相同）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))

NEWLISTING_URL = "https://openapi.twse.com.tw/v1/company/newlisting"
OUT_PATH = Path(__file__).parent / "data" / "otc_to_twse_dates.json"
TW_TZ = timezone(timedelta(hours=8))
ZERO_VOL_WINDOW = 20
ZERO_VOL_MIN = 3


def fetch_transfer_codes() -> dict[str, str]:
    r = requests.get(NEWLISTING_URL, timeout=40)
    r.raise_for_status()
    rows = json.loads(r.content.decode("utf-8"))
    if not isinstance(rows, list) or len(rows) < 100:
        raise RuntimeError(f"TWSE newlisting 回傳非預期格式或過短（len={len(rows) if isinstance(rows, list) else 'N/A'}）")
    out: dict[str, str] = {}
    for row in rows:
        note = str(row.get("Note") or "")
        code = str(row.get("Code") or "").strip()
        if "櫃轉市" in note and code:
            out[code] = note
    return out


def _cached_price(stock_id: str) -> pd.DataFrame | None:
    from finmind_client import DATA_DIR
    from validation.holdout import VAL_END

    files = sorted(DATA_DIR.glob(f"TaiwanStockPrice__{stock_id}__*__{VAL_END}.parquet"))
    if not files:
        return None
    df = pd.read_parquet(files[0])
    if df.empty or "Trading_Volume" not in df.columns:
        return None
    df = df[df["date"].astype(str) <= VAL_END].copy()
    df["date"] = df["date"].astype(str)
    return df.sort_values("date").reset_index(drop=True)


def estimate_otc_start(pre: pd.DataFrame) -> tuple[str | None, str]:
    """`pre`：轉上市日之前的價格列（date遞增、含Trading_Volume）。回傳(估計日, basis)。"""
    if pre.empty:
        return None, "轉上市日前無價格列（無可截斷內容）"
    zero = (pre["Trading_Volume"].fillna(0) == 0).astype(int)
    bad = zero.rolling(ZERO_VOL_WINDOW, min_periods=1).sum() >= ZERO_VOL_MIN
    if not bad.any():
        return str(pre["date"].iloc[0]), "轉上市日前整段皆為正常成交，取第一筆價格日"
    last_bad = int(bad[bad].index[-1])
    if last_bad + 1 >= len(pre):
        return None, "轉上市日前最後仍為興櫃式無流動性期間，不早於轉上市日"
    return str(pre["date"].iloc[last_bad + 1]), "最後一個興櫃式視窗（近20列≥3個零成交量日）結束後的下一交易日"


def build() -> dict:
    from universe import _TWSE_LISTING_PATH

    transfers = fetch_transfer_codes()
    twse = json.loads(_TWSE_LISTING_PATH.read_text(encoding="utf-8"))["listing_dates"]
    out: dict[str, dict] = {}
    for sid in sorted(transfers):
        ymd = twse.get(sid)
        if not ymd:
            out[sid] = {"twse_listing_date": None, "otc_start_est": None, "basis": "TWSE現存名單無此代號（已下市或轉投控），不處理"}
            continue
        twse_date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        df = _cached_price(sid)
        if df is None:
            out[sid] = {"twse_listing_date": twse_date, "otc_start_est": None, "basis": "無價格快取，未估計（lookup不截斷）"}
            continue
        pre = df[df["date"] < twse_date].reset_index(drop=True)
        est, basis = estimate_otc_start(pre)
        if est is None and not pre.empty:
            est = twse_date
        out[sid] = {"twse_listing_date": twse_date, "otc_start_est": est, "n_pre_rows": int(len(pre)),
                    "first_price_date": str(df["date"].iloc[0]), "basis": basis}
    return out


def main() -> None:
    transfers = build()
    n_est = sum(1 for v in transfers.values() if v.get("otc_start_est"))
    doc = {
        "generated_at": datetime.now(TW_TZ).isoformat(),
        "source": NEWLISTING_URL + "（Note含「櫃轉市」）＋research/data/raw價格快取（*__2024-12-31.parquet）",
        "scope": "櫃轉市股票的上櫃起算日「估計」，不是官方日期；otc_start_est為null者lookup不截斷。",
        "n_transfers": len(transfers),
        "n_estimated": n_est,
        "transfers": transfers,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"櫃轉市 {len(transfers)} 檔，其中 {n_est} 檔有價格快取可估計；已寫入 {OUT_PATH}")


if __name__ == "__main__":
    main()
