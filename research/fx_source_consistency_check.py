"""`fx_twd_gate.py`（研究端，FinMind `TaiwanExchangeRate` spot_sell）與
`.github/scripts/fetch_fx.py`（生產端，央行 FTDOpenData015 銀行間收盤）兩個
匯率來源的一致性檢查——只量測差異，不改 `fx_twd_gate.build_fx_series()`。

為什麼不直接換掉：`fx_twd_gate`（#32）的匯率口徑（spot_sell）是第1關前事前綁定
並已登記判定的；被 `adr_premium_assembly` 等腳本沿用，直接換來源會靜默改變
已登記試驗的輸入。先量差異，再由結果決定是否值得換。

holdout：央行 CSV 含 holdout 期間資料，這裡一律截斷在 `VAL_END`（含）之前。
"""
from __future__ import annotations

import io
import ssl
import sys

import numpy as np
import pandas as pd
import requests

from fx_twd_gate import build_fx_series, N_SIGNAL_DAYS
from validation.holdout import VAL_END

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CBC_FX_URL = ("https://www.cbc.gov.tw/public/data/OpenData/"
              "%E5%A4%96%E5%8C%AF%E5%B1%80/FTDOpenData015.csv")


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    # 只關 VERIFY_X509_STRICT（央行中繼CA缺SKI），主機名稱與CA鏈驗證維持開啟
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def build_cbc_fx_series() -> pd.DataFrame:
    s = requests.Session()
    s.mount("https://", _StrictOffAdapter())
    r = s.get(CBC_FX_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), dtype=str)
    df = df.iloc[:, :2]
    df.columns = ["date", "rate"]
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    df = df.dropna()
    df = df[(df["rate"] > 0) & (df["date"] <= pd.Timestamp(VAL_END))]
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def main() -> None:
    fm = build_fx_series().rename(columns={"rate": "fm"})
    cb = build_cbc_fx_series().rename(columns={"rate": "cbc"})
    print(f"FinMind spot_sell: {len(fm)}列 {fm['date'].min().date()}~{fm['date'].max().date()}")
    print(f"央行 FTDOpenData015: {len(cb)}列 {cb['date'].min().date()}~{cb['date'].max().date()}")
    m = fm.merge(cb, on="date", how="inner")
    print(f"共同日期 {len(m)}（FinMind獨有 {len(fm)-len(m)}、央行獨有 {len(cb)-len(m)}[央行含2008起，僅FinMind起點2015後才算缺口]）")
    only_cb = cb[cb["date"] >= fm["date"].min()].merge(fm, on="date", how="left")
    print(f"2015後央行有、FinMind無的日期數：{int(only_cb['fm'].isna().sum())}")
    d = m["fm"] - m["cbc"]
    print(f"水位差(FinMind-央行) 平均 {d.mean():.4f}  絕對最大 {d.abs().max():.4f}  標準差 {d.std():.4f}")
    lv = np.corrcoef(m["fm"], m["cbc"])[0, 1]
    ch_fm = m["fm"] / m["fm"].shift(N_SIGNAL_DAYS) - 1
    ch_cb = m["cbc"] / m["cbc"].shift(N_SIGNAL_DAYS) - 1
    ok = ch_fm.notna() & ch_cb.notna()
    cc = np.corrcoef(ch_fm[ok], ch_cb[ok])[0, 1]
    sign = (np.sign(ch_fm[ok]) == np.sign(ch_cb[ok])).mean()
    print(f"水位相關 {lv:.6f}；{N_SIGNAL_DAYS}日變動率相關 {cc:.4f}；變動率同號比例 {sign:.4f}")
    print(f"{N_SIGNAL_DAYS}日變動率差 絕對最大 {(ch_fm[ok]-ch_cb[ok]).abs().max():.4f}")


if __name__ == "__main__":
    main()
