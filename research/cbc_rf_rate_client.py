"""央行五大銀行「定存利率-一個月」CSV client（2026-09-10 hypothesis_queue排程，
`HYPOTHESIS_QUEUE.md` #70 選擇權波動度偏斜第1關前置地基建置(a)）。

**用途**：#70的Black-Scholes反推OTM隱含波動度需要無風險利率輸入。查證結論
（見`HYPOTHESIS_QUEUE.md` #70條目「三來源資料可行性查證」段落）：中央銀行
`data.gov.tw`資料集#10359「五大銀行存放款利率歷史月資料」
（`https://www.cbc.gov.tw/public/data/OpenData/A13Rate.csv`）免費、CSV
直接下載，含2001年1月至今、月頻、五大銀行（第一/臺灣/合作金庫/土地/彰化/
華南，實測本輪為6家，含華南銀行）分別列示的「定存利率-一個月-固定/機動」
欄位，天期與#70事前綁定的選擇權篩選區間[10,45]天相符。

**SSL已知問題與正確修法（非長期停用驗證）**：`requests`預設驗證
`www.cbc.gov.tw`會拋`CERTIFICATE_VERIFY_FAILED: Missing Subject Key
Identifier`——這不是憑證過期或偽造，是這台機器的Python 3.13+OpenSSL 3.0.21
組合下，`ssl.VERIFY_X509_STRICT`旗標（近年OpenSSL/Python預設開啟的較嚴格
X.509檢查）對央行憑證鏈裡某張中繼CA缺少`Subject Key Identifier`擴充欄位
較真——這是憑證鏈本身格式上的小瑕疵，不是MITM或偽造的訊號。**正確做法是
只關閉這一個較新且較嚴格的旗標**（`ctx.verify_flags &= ~ssl.VERIFY_X509_
STRICT`），主機名稱驗證與CA信任鏈驗證都維持開啟（`ctx.check_hostname`、
`ctx.verify_mode`不變動），跟`verify=False`（整條鏈都不驗證，`CLAUDE.md`
明文禁止的長期做法）是完全不同等級的放寬，本輪已用該修法實測成功
（HTTP 200、260563 bytes、`utf-8-sig`可正確解碼）。

**編碼**：回應內容需用`utf-8-sig`解碼（含BOM），不是`cp950`/`big5`——
`requests`的`.text`自動偵測在這個端點上會誤判，比照`margin_debt_market_
client.py`docstring記載的TWSE MI_MARGN類似編碼陷阱，本模組一律手動
`resp.content.decode('utf-8-sig')`。

**年月格式**：`年月`欄位是5位數字字串，前3碼為民國年（zero-padded）、
後2碼為月份，例如`"09001"`=民國90年1月=2001-01，`"11508"`=民國115年8月=
2026-08（實測本輪抓取時的最新一筆）。西元年=民國年+1911。

**快取設計**：整份CSV一次性快取成單一parquet檔（跟逐日快取的
`twse_t86_client.py`/`margin_debt_market_client.py`不同，因為這個端點
本身就是「全歷史一次回傳」，沒有逐日請求的必要），比照既有atomic write
pattern防併發寫入截斷。快取有效期本輪未設過期機制（月頻資料變動慢，
之後若需要「取得最新一個月」可另外加時間戳判斷是否重抓，本輪只求#70
地基堪用，不過度工程化）。

**風險利率代理值的組裝方式（事前決定，寫在這裡供#70後續程式碼引用）**：
取當月**六家銀行**「定存利率-一個月-固定」欄位的算術平均（缺值銀行忽略，
不用0代入），理由：固定利率比機動利率更貼近選擇權定價理論假設的「已知
無風險利率」概念（機動利率會隨市場浮動，理論上更適合拿來對照浮動天期
的Black-Scholes但增加複雜度，本輪選簡單路線，若後續發現顯著影響IV反推
結果再重新考慮）；六家銀行平均而非固定挑一家，降低單一銀行報價雜訊。
"""
from __future__ import annotations

import io
import os
import ssl
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "data" / "raw_cbc_rf_rate"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = CACHE_DIR / "A13Rate_monthly.parquet"

SOURCE_URL = "https://www.cbc.gov.tw/public/data/OpenData/A13Rate.csv"
RATE_COL = "定存利率-一個月-固定"


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    """只關閉`ssl.VERIFY_X509_STRICT`這一個旗標，主機名稱驗證與CA信任鏈
    驗證維持開啟——見本檔docstring「SSL已知問題與正確修法」段落，不是
    `verify=False`。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _atomic_to_parquet(df: pd.DataFrame, path: Path) -> None:
    """跟`margin_debt_market_client.py::_atomic_to_parquet()`同一份修法。"""
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


def _atomic_read_parquet(path: Path) -> pd.DataFrame:
    for attempt in range(20):
        try:
            return pd.read_parquet(path)
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05 * (attempt + 1))


def _roc_yyymm_to_date(v) -> pd.Timestamp:
    """'09001' -> 2001-01-01, '11508' -> 2026-08-01。"""
    s = str(int(v)).zfill(5)
    roc_year, month = int(s[:3]), int(s[3:])
    return pd.Timestamp(year=roc_year + 1911, month=month, day=1)


def fetch_raw(force: bool = False) -> pd.DataFrame:
    """回傳原始寬格式（銀行 x 年月 x 各利率欄位），有本機快取則直接讀，
    force=True強制重抓。"""
    if CACHE_PATH.exists() and not force:
        return _atomic_read_parquet(CACHE_PATH)

    session = requests.Session()
    session.mount("https://", _StrictOffAdapter())
    resp = session.get(SOURCE_URL, timeout=30)
    resp.raise_for_status()
    text = resp.content.decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(text))
    if RATE_COL not in df.columns:
        raise RuntimeError(
            f"A13Rate.csv欄位不含預期的'{RATE_COL}'，實際欄位: {list(df.columns)}"
        )
    _atomic_to_parquet(df, CACHE_PATH)
    return df


def load_risk_free_rate_series(force: bool = False) -> pd.DataFrame:
    """回傳月頻無風險利率代理序列，columns: date(月初), rf_rate_pct
    （六家銀行『定存利率-一個月-固定』算術平均，單位：百分比年化）。"""
    raw = fetch_raw(force=force)
    raw = raw.copy()
    raw["date"] = raw["年月"].map(_roc_yyymm_to_date)
    raw[RATE_COL] = pd.to_numeric(raw[RATE_COL], errors="coerce")
    monthly = (
        raw.groupby("date")[RATE_COL]
        .mean()
        .rename("rf_rate_pct")
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )
    return monthly


def rf_rate_for_date(date: pd.Timestamp, monthly: pd.DataFrame) -> float:
    """給定任意交易日，回傳「當月」的無風險利率代理值（%）。若查無當月
    資料（例如超出快取涵蓋範圍），回傳最近一筆已知值並由呼叫端自行判斷
    是否要丟棄該筆觀測——本函式不做外推假設之外的靜默容錯。"""
    target = pd.Timestamp(year=date.year, month=date.month, day=1)
    exact = monthly[monthly["date"] == target]
    if not exact.empty:
        return float(exact["rf_rate_pct"].iloc[0])
    prior = monthly[monthly["date"] < target]
    if prior.empty:
        raise ValueError(f"{date}早於無風險利率序列涵蓋範圍，無法回傳近似值")
    return float(prior.sort_values("date").iloc[-1]["rf_rate_pct"])


if __name__ == "__main__":
    print("=== 抓取/讀取央行五大銀行利率CSV ===")
    monthly = load_risk_free_rate_series()
    print(f"月頻無風險利率代理序列筆數: {len(monthly)}")
    print(f"涵蓋範圍: {monthly['date'].min().date()} ~ {monthly['date'].max().date()}")
    print("\n最近6筆:")
    print(monthly.tail(6).to_string(index=False))

    print("\n=== 交叉核對：TRAIN/VAL期間涵蓋度 ===")
    train_end = pd.Timestamp("2020-12-31")
    val_end = pd.Timestamp("2024-12-31")
    in_train = monthly[monthly["date"] <= train_end]
    in_val = monthly[(monthly["date"] > train_end) & (monthly["date"] <= val_end)]
    print(f"TRAIN(<=2020-12-31)月數: {len(in_train)}")
    print(f"VAL(2021-01~2024-12)月數: {len(in_val)}")

    print("\n=== rf_rate_for_date()測試 ===")
    sample_date = pd.Timestamp("2022-06-15")
    print(f"{sample_date.date()} 對應無風險利率代理值: {rf_rate_for_date(sample_date, monthly):.4f}%")
