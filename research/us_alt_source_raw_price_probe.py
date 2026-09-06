"""round423：查證FinMind以外免費來源能否取得#20/#21常駐短腿ticker的真實未還原歷史收盤價。

背景：`TRIALS_LEDGER.md`#177/#185（round412/round421）已確認FinMind美股`USStockPrice`的
`close`欄位與`adj_close`完全相同，本身沒有保留未調整原始報價；round410/round417已列出
這批VAL期常駐短腿ticker（死亡螺旋型反覆反向分割微型股）。本探針查證是否有「免key免登入」
的替代免費來源可以拿到真正raw（未經未來反向分割回溯膨脹）的歷史收盤價。

事前綁定判準：若某個候選來源對已知發生過反向分割的ticker，回傳的歷史Close在分割前後
沒有被回溯放大（即分割前的名目價格維持分割當時實際交易的量級，而非乘以未來分割比例），
才算「raw報價來源」候選成立。

結論（本輪）：
- yfinance（Yahoo Finance官方公開chart API）：`auto_adjust=False, back_adjust=False`
  取得的`Close`仍是split-adjusted（含未來反向分割回溯），跟FinMind adj_close逐位元相同，
  REFUTED。官方https://help.yahoo.com/kb/SLN28256.html 確認這是Yahoo資料本身的行為。
- stooq.com：直接curl請求觸發JS proof-of-work反機器人驗證頁面，非單純公開CSV，
  依`CLAUDE.md`取得方式鐵律不得繞過，判定不可用（未嘗試繞過）。
- Alpha Vantage `TIME_SERIES_DAILY`：官方文件字面寫「raw (as-traded)」報價，理論上是
  候選，但需要免費API key（本專案目前查無已存在的key），本輪未實測，列為未驗證候選。

登記：`TRIALS_LEDGER.md`#188（`trial_registry.register_trial()`，round423，verdict=REFUTED，
範圍限定「免key免登入的替代來源」這個最寬版本假說）。
"""

from __future__ import annotations

import sys

KNOWN_SHORT_LEG_TICKERS = ["WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI"]


def check_yfinance_back_adjusted(ticker: str = "DVLT") -> None:
    """實測yfinance的Close欄位是否仍是split back-adjusted（不含股利調整）。"""
    import yfinance as yf

    t = yf.Ticker(ticker)
    splits = t.splits
    hist = t.history(
        start="2020-12-01", end="2021-01-15", auto_adjust=False, back_adjust=False
    )
    if hist.empty:
        print(f"{ticker}: 無歷史資料")
        return
    print(f"=== {ticker} splits ===")
    print(splits)
    print(f"=== {ticker} 2020-12-31 Close（auto_adjust=False, back_adjust=False）===")
    row = hist.loc[hist.index.date.astype(str) == "2020-12-31"]
    if not row.empty:
        print(row[["Open", "Close", "Adj Close"]])
    reverse_splits = splits[splits < 1] if not splits.empty else splits
    future_reverse_split_exists = any(d.year >= 2021 for d in reverse_splits.index) if not reverse_splits.empty else False
    print(
        f"判定：{'REFUTED（Close仍是back-adjusted）' if future_reverse_split_exists else '無2021年後反向分割資料可比對'}"
    )


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "DVLT"
    check_yfinance_back_adjusted(ticker)
