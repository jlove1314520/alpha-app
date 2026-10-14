# -*- coding: utf-8 -*-
"""先.九十五-1：抓 0050 官方每日結算淨值（NAV），供 core_tilt 第 0 階段改用 NAV 當基準。

來源（三來源查證見 research/PIT_MKTCAP_RULES_FIX.md 先.九十五-1 節）：元大投信 ETF 網站
「歷史淨值走勢」頁（www.yuantaetfs.com/tradeInfo/comparison/0050/NAVhistory，robots.txt Allow: /）
背後的 etfapi.yuantaetfs.com/ectranslation/api/trans，FuncId=ETFNAV/GetFluctuateValue（結算淨值；
同站 GetComparison 是 13:30 估計淨值，不用）。一次查一整年；2013～VAL_END 年份共約 12 次請求。
官方未公布次數上限；與 data/rate_limit_state.json 共用節流（來源名 yuanta_etfapi，同源間隔 ≥3 秒，
402/403/428/429 封鎖 2 小時不重試）。已抓年份存 research/data/raw/yuanta_nav_0050/，不重抓。
只抓到 VAL_END，不碰 holdout。輸出 research/data/etf0050_nav_daily.csv（research/data/ 已 gitignore）。
用法：python research/fetch_0050_nav.py
"""
from __future__ import annotations

import json
import ssl
import sys
import uuid
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from validation.holdout import VAL_END  # noqa: E402

SRC = "yuanta_etfapi"
URL = "https://etfapi.yuantaetfs.com/ectranslation/api/trans"
PAGE = "/tradeInfo/comparison/0050/NAVhistory"
RAW = HERE / "data" / "raw" / "yuanta_nav_0050"
OUT = HERE / "data" / "etf0050_nav_daily.csv"
BLOCK = {402, 403, 428, 429}
START_YEAR = 2013


class _StrictOffAdapter(requests.adapters.HTTPAdapter):
    """etfapi 憑證鏈缺 Subject Key Identifier（同央行端點地雷，見 .github/scripts/fetch_fx.py）：
    只關 ssl.VERIFY_X509_STRICT，主機名稱與 CA 信任鏈驗證維持開啟，不是 verify=False。"""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _params(y: int) -> dict:
    # 這些是網頁本身公開的固定參數（commonParameterList），不是金鑰；DeviceId 是網頁自己產生的隨機 uuid
    return {"APIType": "ETFBackstage", "CompanyName": "YUANTAFUNDS", "PageName": PAGE, "DeviceId": str(uuid.uuid4()),
            "FuncId": "ETFNAV/GetFluctuateValue", "AppName": "ETF", "Device": "4", "Platform": "ETF",
            "stk_cd": "0050", "SDATE": f"{y}0101", "EDATE": min(f"{y}1231", VAL_END.replace("-", ""))}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    sess.mount("https://", _StrictOffAdapter())
    n_req = 0
    for y in range(START_YEAR, int(VAL_END[:4]) + 1):
        f = RAW / f"{y}.json"
        if f.exists():
            continue
        _rate_limit_wait_or_raise(SRC)
        # 不帶 Referer、不偽裝（CLAUDE.md 取得方式鐵律）；UA 與本專案其他官方網站 rwd 腳本相同
        r = sess.get(URL, params=_params(y), timeout=90, headers={"User-Agent": "Mozilla/5.0"})
        n_req += 1
        if r.status_code in BLOCK:
            _rate_limit_record_block(SRC, r.status_code, "GetFluctuateValue")
            print(f"HTTP {r.status_code}，封鎖 2 小時，停止", flush=True)
            return 1
        try:
            js = r.json()
        except ValueError:
            print(f"{y} 回傳不是 JSON，停止", flush=True)
            return 1
        if js.get("ResultCode") != 0 or not js.get("Data"):
            print(f"{y} ResultCode={js.get('ResultCode')} {js.get('ResultMsg')}，停止", flush=True)
            return 1
        f.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
        print(f"{y}: {len(js['Data'])} 天", flush=True)
    rows = []
    for f in sorted(RAW.glob("*.json")):
        for d in json.loads(f.read_text(encoding="utf-8"))["Data"]:
            day = d["UPDATE_T"][:10]   # 淨值日（TRAN_DATE 在這支 API 是 0001-01-01）
            if day <= VAL_END and d.get("NOW_NAV"):
                rows.append((day, float(d["NOW_NAV"]), d.get("NOW_PRICE"), d.get("OS_UNIT")))
    df = pd.DataFrame(rows, columns=["date", "nav", "close", "units"]).drop_duplicates("date").sort_values("date")
    df.to_csv(OUT, index=False)
    print(f"請求 {n_req} 次；{len(df)} 天（{df['date'].iloc[0]}～{df['date'].iloc[-1]}）→ {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
