"""`HYPOTHESIS_QUEUE.md` #41（內部人董監持股轉讓）節流後的中小樣本回補腳本
（2026-09-06 hypothesis_queue排程接續，地基建置本輪；2026-09-06接續第四輪
把`PILOT_STOCK_COUNT`從15擴大到25；2026-09-06接續第五輪再從25擴大到35；
2026-09-06接續第六輪再從35擴大到45——受限於per-company查詢+headless單次
Bash呼叫10分鐘上限，一次擴到接近factor_ic.py標準300檔規模的時間成本過高
（300檔x20季度=6000筆請求，以1.8秒節流估算需要3小時以上），依協定「一輪
只做一個有界工作單位」原則分批擴大，本輪+10檔、下一輪可再接續擴大）。

依`HYPOTHESIS_QUEUE.md` #41條目最新狀態的指引：「先用中小樣本抽樣先驗第1關
cheap gate訊號存在，再決定是否值得投入全量回補的工程成本」——本腳本**只**
回補一個小樣本（`PILOT_STOCK_COUNT`檔股票 x `PERIODS`個季度快照），不是全
市場全歷史回補（全市場約1700+檔x全歷史會是20萬次請求量級，見#41條目「跟
#38/#39的關鍵差異」段落，本輪不做）。

樣本選取：從`factor_ic.py`既有`sample_universe_ids(PILOT_SAMPLE_SIZE,
SAMPLE_SEED)`（跟其他所有cheap gate同一個決定性抽樣方法，方便未來若通過
pilot要擴大時沿用同一套抽樣邏輯）裡篩出「純4位數字股票代碼」（排除ETF等
5位數/帶字母代碼——`#41`這個資料源本質是『公司內部人』，ETF沒有董監事持股
這個概念，openapi/MOPS對這類代碼本來就查不到資料，篩掉可以省下白打的
請求），取前`PILOT_STOCK_COUNT`檔。

期間：民國105Q1~109Q4（西元2016Q1~2020Q4），共20個季度快照，完全落在
`validation/holdout.py`的TRAIN期（<=2020-12-31）內，不動VAL/holdout。

**只查TYPEK='sii'（上市）**，不做otc(上櫃)回退查詢——這是本輪的刻意簡化
（見模組docstring），若某檔股票剛好是上櫃股，會全部記成`fetched_empty`，
在pilot覆蓋率報告裡看得到、不會被誤判成『資料不存在』，下一輪如果需要
補上櫃股可以加otc回退。

可安全中斷重跑（`fetch_and_cache()`本身就是快取命中就跳過）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from factor_ic import SAMPLE_SEED, sample_universe_ids
from mops_insider_holdings_client import fetch_and_cache

PILOT_SAMPLE_SIZE = 60
PILOT_STOCK_COUNT = 45

PERIODS = [(f"{y:03d}", m) for y in range(105, 110) for m in ["03", "06", "09", "12"]]


def _is_plain_stock_code(sid: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", sid))


def pilot_universe() -> list[str]:
    candidates = sample_universe_ids(PILOT_SAMPLE_SIZE, SAMPLE_SEED)
    plain = [s for s in candidates if _is_plain_stock_code(s)]
    return plain[:PILOT_STOCK_COUNT]


def main() -> None:
    stocks = pilot_universe()
    print(f"pilot樣本 {len(stocks)}檔（來自sample_universe_ids前{PILOT_SAMPLE_SIZE}檔篩4位數字代碼）: {stocks}")
    print(f"期間 {len(PERIODS)}個季度快照（民國）: {PERIODS[0]} ~ {PERIODS[-1]}（西元2016Q1~2020Q4，TRAIN期內）")

    n_total = len(stocks) * len(PERIODS)
    n_done = n_ok = n_empty = n_error = n_cached = 0
    for sid in stocks:
        for year_roc, month in PERIODS:
            r = fetch_and_cache(sid, year_roc, month, typek="sii")
            n_done += 1
            status = r["status"]
            if status == "cached":
                n_cached += 1
                if r.get("board_holdings_total") is not None:
                    n_ok += 1
                else:
                    n_empty += 1
            elif status == "fetched_ok":
                n_ok += 1
            elif status == "fetched_empty":
                n_empty += 1
            else:
                n_error += 1
            if n_done % 30 == 0 or n_done == n_total:
                print(f"  進度 {n_done}/{n_total}  ok={n_ok} empty={n_empty} error={n_error} (含快取命中{n_cached})")

    print(f"\n回補完成：{n_done}筆請求（含快取命中{n_cached}筆），"
          f"ok={n_ok}({n_ok/n_total*100:.1f}%) empty={n_empty} error={n_error}")


if __name__ == "__main__":
    main()
