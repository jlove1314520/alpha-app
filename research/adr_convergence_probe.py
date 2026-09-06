"""Probe: 假設#45（存託憑證ADR溢價/折價收斂）的地基查證第一步——
FinMind `USStockPrice` 是否實際收錄台灣公司在美掛牌ADR代碼TSM/UMC/CHT/ASX，
涵蓋範圍多長、是否有明顯資料缺口。

背景：`HYPOTHESIS_QUEUE_PROTOCOL.md` 指引，佇列#1~44已全數結案（見
`HYPOTHESIS_QUEUE.md`「排隊順序總結」），#45（ADR溢價收斂）已設計完成
經濟理由但「尚未開始第1關」，狀態段落明確要求下一輪第一步依序查證：
(a) FinMind USStockPrice是否收錄這四檔ADR、(b) 換股比率是否曾變動、
(c) PIT時序對齊邏輯。本腳本只做(a)，資料存在性用最便宜的方式先確認，
不做全歷史回補（那是下一步cheap gate地基建置的事，視這裡的查證結果
決定要不要繼續）。

All fetches go through finmind_client.load_dev()（holdout-safe），依
CONSTITUTION.md規則。
"""
from __future__ import annotations

from finmind_client import load_dev

# 候選ADR代碼——FinMind USStockPrice慣例用美股代碼（跟us_factors.py既有
# US軌腳本一致），不是台股代碼。這幾個代碼本身是否被FinMind收錄正是本
# 探查要確認的事，不可假設。
CANDIDATES = {
    "TSM": "台積電 (2330)",
    "UMC": "聯電 (2303)",
    "CHT": "中華電信 (2412)",
    "ASX": "日月光投控 (3711)",
}

# 用一段涵蓋較長歷史的窗口，觀察涵蓋起始年份與是否有明顯缺口，
# 但仍走load_dev()自動被VAL_END截斷，不會碰到holdout。
PROBE_START = "2000-01-01"


def probe_one(ticker: str, label: str) -> None:
    print(f"\n=== ticker={ticker!r} ({label}) ===")
    try:
        df = load_dev("USStockPrice", ticker, start_date=PROBE_START)
    except Exception as e:  # noqa: BLE001 -- 探查階段要看到每一種失敗模式，不要讓探查腳本自己壞掉
        print(f"FAILED: {type(e).__name__}: {e}")
        return

    if df.empty:
        print("回傳空的dataframe——FinMind可能沒有收錄這個代碼，或代碼本身不對")
        return

    print(f"rows: {len(df)}")
    print(f"columns: {list(df.columns)}")
    dates = sorted(df["date"].unique())
    print(f"涵蓋範圍: {dates[0]} ~ {dates[-1]}")
    print(f"最早5筆:\n{df.head(5).to_string()}")
    print(f"最新5筆:\n{df.tail(5).to_string()}")


def main() -> None:
    for ticker, label in CANDIDATES.items():
        probe_one(ticker, label)


if __name__ == "__main__":
    main()
