# -*- coding: utf-8 -*-
"""先.二十三-五 自測：adjust.py 的「台股物理合理性」守衛。

背景：yfinance 對 0050 在 2014-01-02 回傳 −75.06% 的假跌幅（37.186→9.273，恰為 4 倍），
而 `adjusted_price_series()` 原本只把 anomaly 記進警告檔、仍舊回傳壞資料。
用那份序列跑 2 倍槓桿會把淨值打成負數（先.二十二 T-B 首次執行即如此）。

本自測檢查守衛的四件事：①抓得到物理上不可能的日報酬 ②不誤殺合法的漲跌停序列
③只對台股四位數代號生效、不影響美股 ④守衛自身失敗時 fail open（不拋例外）。
不呼叫任何網路 API。
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import adjust  # noqa: E402

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def frame(prices):
    return pd.DataFrame({"date": pd.date_range("2014-01-01", periods=len(prices)),
                         "close": prices})


# ① 真實事故重現：37.186 → 9.273（−75.06%，恰為 4 倍）
check("抓到 0050 2014-01-02 的 −75% 假跌幅",
      adjust._yf_series_physically_impossible(frame([37.0, 37.186, 9.273, 9.3]), "0050"))

# ② 不誤殺：連續漲停／跌停（±10%）是合法的，不得觸發
limit_up = [10.0 * (1.10 ** i) for i in range(8)]
limit_dn = [10.0 * (0.90 ** i) for i in range(8)]
check("連續漲停(+10%)不誤判", not adjust._yf_series_physically_impossible(frame(limit_up), "2330"))
check("連續跌停(-10%)不誤判", not adjust._yf_series_physically_impossible(frame(limit_dn), "2330"))
check("平盤序列不誤判", not adjust._yf_series_physically_impossible(frame([20.0] * 10), "0050"))

# ③ 只對台股四位數代號生效
check("美股代號(SPY)不受影響", not adjust._yf_series_physically_impossible(frame([100.0, 25.0]), "SPY"))
# 2026-10-10（先.五十七-B4）：守衛擴大到台股 ETF 代號；槓桿／反向（L／R 結尾）門檻 ±21%
check("槓桿 ETF(00631L) 單日 +18% 在 ±20% 範圍內不誤判",
      not adjust._yf_series_physically_impossible(frame([100.0, 118.0, 120.0]), "00631L"))
check("槓桿 ETF(00631L) 單日 −75% 判不可能（舊版只認四位數，這裡會漏）",
      adjust._yf_series_physically_impossible(frame([100.0, 25.0, 26.0]), "00631L"))
check("一般 ETF(00646) 單日 −50% 判不可能",
      adjust._yf_series_physically_impossible(frame([100.0, 50.0, 51.0]), "00646"))
check("一般 ETF(0050) 單日 +9% 不誤判",
      not adjust._yf_series_physically_impossible(frame([100.0, 109.0, 110.0]), "0050"))
check("四位數代號的 −50% 仍判不可能",
      adjust._yf_series_physically_impossible(frame([100.0, 50.0, 51.0]), "2454"))

# ④ 守衛自身失敗 → fail open，不拋例外
for name, bad in (("缺 close 欄", pd.DataFrame({"date": [1, 2]})),
                  ("空表", pd.DataFrame({"date": [], "close": []})),
                  ("close 全為文字", pd.DataFrame({"date": [1, 2, 3], "close": ["a", "b", "c"]})),
                  ("close 含 0 與負值", frame([0.0, -1.0, 5.0]))):
    try:
        r = adjust._yf_series_physically_impossible(bad, "0050")
        check(f"守衛自身失敗 fail open（{name}）→ 回 {r}，未拋例外", r is False)
    except Exception as e:  # noqa: BLE001
        check(f"守衛自身失敗 fail open（{name}）→ 拋了 {type(e).__name__}", False)

n_fail = sum(1 for _, ok in results if not ok)
print(f"合計 {len(results)} 項，失敗 {n_fail}")
sys.exit(1 if n_fail else 0)
