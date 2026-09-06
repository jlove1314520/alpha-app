"""
#20/#21 US軌短腿常駐ticker FINRA/Nasdaq Reg SHO threshold list 歷史查證。

背景：round418 US_LEADS.md #20/#21 建議下一步——查證value_bm/low_vol空頭腿
常駐ticker（WATT/LEE/AMTX/MNTS/DVLT/WULF/CIIT/PALI）是否長期掛在Reg SHO
threshold securities list（persistent failure-to-deliver清單）。若長期掛在
該名單，代表真實世界持續借不到券／naked short氾濫，這批股票的空頭「報酬」
根本不可能被真實策略實現，依HYPOTHESIS_QUEUE_PROTOCOL.md快殺標準「結構性
不可能」應直接判#20/#21為FAIL而非繼續掛EXPERIMENTAL。

資料源：Nasdaq Reg SHO Threshold List，免費、免登入、匿名FTP：
ftp://ftp.nasdaqtrader.com/SymbolDirectory/regsho/nasdaqth{YYYYMMDD}.txt
（2026-09-07 手動curl測試確認可用，回溯至少到2021年）。
限制：此檔案只涵蓋Nasdaq掛牌證券，NYSE掛牌（例如LEE）不在此清單。

方法：VAL期（2020-2024）每月第一個有資料的交易日抽樣一次（約48個樣本點，
不是完整逐日回補——完整逐日回補需要約1000個請求，屬於下一輪的地基工作，
這裡先用月頻抽樣做方向性判斷），檢查目標ticker是否出現在threshold flag=Y
的清單裡。這是方向性證據不是窮盡證據：抽樣頻率低於逐日，可能漏掉短暫的
threshold事件；但如果目標ticker「長期」掛在清單上，月頻抽樣理應能捕捉到。
"""
import sys
import time
import calendar
import urllib.request
from pathlib import Path

TARGET_TICKERS = ["WATT", "AMTX", "MNTS", "DVLT", "WULF", "CIIT", "PALI"]
# LEE (Lee Enterprises) 是NYSE掛牌，Nasdaq threshold list不涵蓋，本探針無法查證，另記錄。
NOT_COVERED = ["LEE"]

CACHE_DIR = Path(__file__).parent / "data" / "raw_finra_threshold"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FTP_BASE = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/regsho/nasdaqth{}.txt"


def month_sample_dates(start_year=2020, start_month=12, end_year=2024, end_month=12):
    """VAL期每月挑第15號（避開月初月末的假日/週末機率），格式YYYYMMDD字串。"""
    dates = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        dates.append(f"{y:04d}{m:02d}15")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return dates


def fetch_day(date_str, max_retry=3):
    """抓一天的threshold list，失敗（假日/週末沒有檔案）往前找最多3天。回傳(實際用的日期, 內容行list)或(None, None)。"""
    from datetime import datetime, timedelta

    d = datetime.strptime(date_str, "%Y%m%d")
    for offset in range(max_retry + 1):
        try_date = d - timedelta(days=offset)
        try_str = try_date.strftime("%Y%m%d")
        cache_file = CACHE_DIR / f"nasdaqth{try_str}.txt"
        if cache_file.exists():
            return try_str, cache_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        url = FTP_BASE.format(try_str)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
            if content.strip():
                cache_file.write_text(content, encoding="utf-8")
                return try_str, content.splitlines()
        except Exception:
            time.sleep(0.5)
            continue
    return None, None


def main():
    dates = month_sample_dates()
    hits = {t: [] for t in TARGET_TICKERS}
    misses = {t: 0 for t in TARGET_TICKERS}
    checked_dates = []

    for date_str in dates:
        actual_date, lines = fetch_day(date_str)
        if lines is None:
            print(f"[跳過] {date_str} 附近3天內都抓不到檔案")
            continue
        checked_dates.append(actual_date)
        present = set()
        for line in lines[1:]:
            parts = line.split("|")
            if len(parts) >= 4 and parts[3].strip().upper() == "Y":
                present.add(parts[0].strip())
        for t in TARGET_TICKERS:
            if t in present:
                hits[t].append(actual_date)
            else:
                misses[t] += 1
        time.sleep(0.3)

    print(f"\n實際檢查了 {len(checked_dates)} 個抽樣交易日（VAL期2020-12~2024-12月頻）")
    print(f"樣本日期範圍：{checked_dates[0] if checked_dates else 'N/A'} ~ {checked_dates[-1] if checked_dates else 'N/A'}\n")
    for t in TARGET_TICKERS:
        n_hit = len(hits[t])
        n_total = n_hit + misses[t]
        pct = (n_hit / n_total * 100) if n_total else float("nan")
        print(f"{t}: 命中threshold list {n_hit}/{n_total} 次（{pct:.1f}%）"
              + (f"  命中日期樣本：{hits[t][:5]}" if hits[t] else ""))
    print(f"\n未涵蓋（NYSE掛牌，此探針無法查證）：{NOT_COVERED}")


if __name__ == "__main__":
    main()
