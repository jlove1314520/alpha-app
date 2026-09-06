"""`HYPOTHESIS_QUEUE.md` #48（董監事/經理人/大股東股權質押比例）全歷史回補
腳本（2026-09-06 hypothesis_queue排程接續，地基建置本輪）。

`irb130_pledge_probe.py`已確認(a)(b)(c)三點資料可行性：端點為全市場單一
請求（不需per-company查詢，比`#41`/`#38`效率高很多）、歷史回溯深度涵蓋
TRAIN(2015-2020)/VAL(2021-2024)全區間、PIT時間差為正常月頻揭露延遲。
本腳本把探測階段的少量測試請求擴大為**完整TRAIN+VAL月頻回補**：
2015-01~2024-12共120個月 x {sii,otc}兩市場 = 240次請求，複用探測腳本的
`fetch_irb130_month()`/`parse_irb130_rows()`，逐月寫入獨立CSV快取檔，
可安全中斷重跑（已存在的快取檔案直接跳過，不重複發請求）。

**節流**：每次請求間隔1.5秒（比照`irb130_pledge_probe.py`），240次請求
理論總耗時約6分鐘，加上偶發網路延遲，預期跑到20~30分鐘量級——依
`MARATHON_PROTOCOL.md`第0b節規則用`run_detached.py`脫離session執行，
不在互動session裡等。

**快取格式**：`data/raw_irb130_pledge/{market}_{roc_year:03d}{month:02d}.csv`，
欄位同`parse_irb130_rows()`回傳的dict鍵，另加`market`/`roc_year`/`month`
三欄方便下游直接concat讀取整個目錄。若該月份HTTP請求失敗（例如尚未公布
或端點暫時無回應），寫一個只有header、標記`status=error`的空檔案，避免
下次重跑時又對已知失敗的月份重試（比照`mops_insider_holdings_client.py`
`fetched_empty`的先例，記錄失敗原因而非靜默略過）。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import requests

from irb130_pledge_probe import fetch_irb130_month, parse_irb130_rows

CACHE_DIR = Path(__file__).parent / "data" / "raw_irb130_pledge"
MARKETS = ["sii", "otc"]
START_YEAR, END_YEAR = 2015, 2024  # TRAIN(2015-2020)+VAL(2021-2024)全區間
SLEEP_SEC = 1.5


def _months() -> list[tuple[int, int]]:
    return [(y, m) for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)]


def fetch_and_cache_month(market: str, western_year: int, month: int) -> dict:
    roc_year = western_year - 1911
    cache_path = CACHE_DIR / f"{market}_{roc_year:03d}{month:02d}.csv"
    if cache_path.exists():
        cached = pd.read_csv(cache_path)
        status = "error" if (len(cached) == 0) else "cached"
        return {"market": market, "western_year": western_year, "month": month,
                "status": status, "n_rows": len(cached)}

    try:
        text = fetch_irb130_month(market, roc_year, month)
        rows = parse_irb130_rows(text)
    except requests.exceptions.RequestException as e:
        print(f"  [WARN] {market} {western_year}-{month:02d} 請求失敗: {e}")
        pd.DataFrame(columns=["co_id"]).to_csv(cache_path, index=False)
        return {"market": market, "western_year": western_year, "month": month,
                "status": "error", "n_rows": 0}

    if not rows:
        print(f"  [WARN] {market} {western_year}-{month:02d} 解析出0列（可能尚未公布或格式變動）")
        pd.DataFrame(columns=["co_id"]).to_csv(cache_path, index=False)
        return {"market": market, "western_year": western_year, "month": month,
                "status": "empty", "n_rows": 0}

    df = pd.DataFrame(rows)
    df["market"] = market
    df["roc_year"] = roc_year
    df["month"] = month
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return {"market": market, "western_year": western_year, "month": month,
            "status": "fetched_ok", "n_rows": len(df)}


def main() -> None:
    months = _months()
    total = len(months) * len(MARKETS)
    print(f"#48 IRB130質押比例全歷史回補：{len(months)}個月 x {len(MARKETS)}市場 = {total}次請求")
    print(f"期間: {START_YEAR}-01 ~ {END_YEAR}-12（TRAIN+VAL全區間，未涉及holdout）")

    n_done = n_ok = n_empty = n_error = n_cached = 0
    for western_year, month in months:
        for market in MARKETS:
            r = fetch_and_cache_month(market, western_year, month)
            n_done += 1
            if r["status"] == "cached":
                n_cached += 1
            elif r["status"] == "fetched_ok":
                n_ok += 1
                time.sleep(SLEEP_SEC)
            elif r["status"] == "empty":
                n_empty += 1
                time.sleep(SLEEP_SEC)
            else:
                n_error += 1
                time.sleep(SLEEP_SEC)
            if n_done % 20 == 0 or n_done == total:
                print(f"  進度 {n_done}/{total}  ok={n_ok} empty={n_empty} error={n_error} "
                      f"(快取命中{n_cached})")

    print(f"\n回補完成：{n_done}次請求（快取命中{n_cached}），"
          f"ok={n_ok} empty={n_empty} error={n_error}")

    all_files = sorted(CACHE_DIR.glob("*.csv"))
    frames = [pd.read_csv(f) for f in all_files]
    frames = [f for f in frames if len(f) > 0 and "co_id" in f.columns and "board_pledge_pct" in f.columns]
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined.to_csv(CACHE_DIR.parent / "irb130_pledge_combined.csv", index=False)
        print(f"合併輸出: {len(combined)}列 -> data/irb130_pledge_combined.csv "
              f"（{combined['market'].nunique()}市場, "
              f"{combined.groupby(['roc_year','month']).ngroups}個月）")
    else:
        print("[WARN] 沒有任何成功解析的月份，未輸出合併檔案")


if __name__ == "__main__":
    main()
