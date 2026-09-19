"""#75續8(c2)：以yfinance補抓DERA「有買入發行人」的美股日線調整收盤價（分批、可續跑）。

事前綁定（在看任何報酬前定死，不得依結果回頭改）：
- 抓取順序＝各發行人「有買入的月數」由多到少，同數以issuer_cik升冪；只看買入月數，不看價格/報酬。
- 每輪上限 MAX_TICKERS_PER_RUN 檔（分批、批間節流、遇連續限流即停損，下一輪續抓）。
- 價格截止 END_EXCLUSIVE=2025-01-01（VAL_END=2024-12-31含；不碰holdout區間）。
- 抓不到/ticker對不上/已下市者一律記status=none，計入覆蓋缺口，不剔除後宣稱全宇宙。
- 每檔記first_date/last_date，供下一輪只統計「買入月落在有價格區間內」的覆蓋（防ticker被沿用/OTC空殼污染，
  見CLAUDE.md「下市股資料：取得不等於正確」）。
輸出：data/dera_insider/prices/px_*.csv（gitignore涵蓋）、insider_dera_price_fetch_status.json（進度）。
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
CSV = HERE / "data" / "dera_insider" / "issuer_month_net.csv"
OUTDIR = HERE / "data" / "dera_insider" / "prices"
STATUS = HERE / "insider_dera_price_fetch_status.json"

START = "2005-06-01"
END_EXCLUSIVE = "2025-01-01"
BATCH = 40
MAX_TICKERS_PER_RUN = 720
SLEEP_BETWEEN_BATCH = 4.0
MAX_TIME_SEC = 17 * 60


def yf_symbol(t):
    return t.replace(".", "-").strip()


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV, dtype={"issuer_cik": str})
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    b = df[(df["buy_usd"] > 0) & df["ticker"].str.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}")]
    rank = (b.groupby("ticker").size().rename("buy_months").reset_index()
            .sort_values(["buy_months", "ticker"], ascending=[False, True]))
    order = rank["ticker"].tolist()

    st = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {"tickers": {}}
    done = st["tickers"]
    todo = [t for t in order if t not in done][:MAX_TICKERS_PER_RUN]
    print(f"排序後可抓ticker={len(order)}，已處理={len(done)}，本輪待抓={len(todo)}")

    t0 = time.time()
    fail_streak = 0
    for i in range(0, len(todo), BATCH):
        if time.time() - t0 > MAX_TIME_SEC:
            print("達本輪時間上限，停止（下一輪續抓）")
            break
        chunk = todo[i:i + BATCH]
        syms = [yf_symbol(t) for t in chunk]
        try:
            d = yf.download(syms, start=START, end=END_EXCLUSIVE, progress=False,
                            auto_adjust=True, group_by="ticker", threads=True)
        except Exception as e:  # 限流/網路：不記成none（不是資料事實），停損
            print(f"批次失敗 {type(e).__name__}: {e}")
            fail_streak += 1
            if fail_streak >= 2:
                print("連續2批失敗，停損；下一輪續抓")
                break
            time.sleep(30)
            continue
        got = 0
        for t, s in zip(chunk, syms):
            try:
                x = d[s]["Close"].dropna() if len(syms) > 1 else d["Close"].dropna()
            except Exception:
                x = pd.Series(dtype=float)
            if len(x) >= 20:
                x.rename("adj_close").to_csv(OUTDIR / f"px_{t}.csv", header=True)
                done[t] = {"status": "ok", "n": int(len(x)),
                           "first": str(x.index[0].date()), "last": str(x.index[-1].date())}
                got += 1
            else:
                done[t] = {"status": "none"}
        fail_streak = 0 if got else fail_streak + 1
        STATUS.write_text(json.dumps({"tickers": done}, ensure_ascii=False), encoding="utf-8")
        print(f"批{i // BATCH + 1}: 取得{got}/{len(chunk)}，累計ok={sum(v['status']=='ok' for v in done.values())} none={sum(v['status']=='none' for v in done.values())}")
        if fail_streak >= 3:
            print("連續3批全空，疑似限流，停損")
            break
        time.sleep(SLEEP_BETWEEN_BATCH)

    ok = sum(v["status"] == "ok" for v in done.values())
    print(f"完成：累計處理{len(done)}，ok={ok}，none={len(done) - ok}，耗時{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
