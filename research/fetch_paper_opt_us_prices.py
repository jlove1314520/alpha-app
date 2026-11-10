# -*- coding: utf-8 -*-
"""先.一五四-1d 甲①（已定案（Cowork 11/10）：照甲執行）：紙上優化軌美股成員（F15／F16）每日價格抓取。

外部請求（照 C:\\alpha\\CLAUDE.md「美股篩選資料源」一節補登）：
  - yfinance 每日最多 1 次批次 `download(248 檔＋SPY＋VTI＋IEF, period=5d, auto_adjust=True)`（VTI／IEF 2026-11-11 先.一五八-1 加，請求次數不變）；
    第一次執行（本機還沒有任何報酬）改 period=3mo 一次，補 F15 需要的 20 日波動暖身。
  - 同一個台北日期已抓過就零請求；失敗保留上一版、不重試。yfinance 非 Yahoo 官方、未公布上限。
宇宙：research/data/us_stratified_universe_sample.csv usable==True（248 檔，同 reaudit_optimized_batch2_us_lowvol.py）。
  **存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。** 這份宇宙是「今天還在」的名冊，偏樂觀。
存法：只存「日報酬」不存價位——auto_adjust 遇到除息會整段回溯改價位，存價位再拼接會在接縫處造出假跳空；
  報酬在同一次下載的視窗內算，回溯改價不影響報酬。新視窗與舊資料重疊的日期以新值覆蓋。
  另存 closes（每次下載視窗內的還原收盤，最新一次覆蓋），只給 F16 換股日算 B/M 分母用。
另外把當天 data/fx.json 的 USD/TWD 牌告匯率依其資料日期記進同一檔（零請求），給美股成員換匯用。
輸出（只在本機，research/data 不進 repo）：research/data/paper_opt/us_returns.json
用法：python research/fetch_paper_opt_us_prices.py [--force]
十二節：失敗只印警告、exit 0。非投資建議。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UNIVERSE_CSV = HERE / "data" / "us_stratified_universe_sample.csv"
OUT = HERE / "data" / "paper_opt" / "us_returns.json"
FX = ROOT / "data" / "fx.json"
TW = timezone(timedelta(hours=8))


def tickers() -> list[str]:
    import pandas as pd
    u = pd.read_csv(UNIVERSE_CSV)
    ids = u[u["usable"] == True]["stock_id"].astype(str).tolist()  # noqa: E712
    # 先.一五八-1（收件匣 042）：加 VTI／IEF 給 F2 危機閘門用；同一次批次下載，請求次數不變
    return sorted(set(t.replace(".", "-") for t in ids)) + ["SPY", "VTI", "IEF"]


def load() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"returns": {}, "fx_usd_twd": {}, "fetch_log": []}


def record_fx(d: dict) -> None:
    try:
        fx = json.loads(FX.read_text(encoding="utf-8")).get("usd_twd") or {}
        if fx.get("rate") and fx.get("date"):
            d["fx_usd_twd"][fx["date"]] = float(fx["rate"])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 讀 data/fx.json 失敗：{e}")


def backfill_fx_from_git(d: dict, n: int = 400) -> None:
    """零請求：從 git 歷史裡 data/fx.json 各版本還原每日牌告匯率（只補沒有的日期）。"""
    import subprocess
    try:
        hs = subprocess.run(["git", "log", f"-n{n}", "--format=%H", "--", "data/fx.json"], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=60).stdout.split()
        added = 0
        for h in hs:
            t = subprocess.run(["git", "show", f"{h}:data/fx.json"], cwd=str(ROOT), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=30).stdout
            try:
                fx = json.loads(t).get("usd_twd") or {}
            except Exception:  # noqa: BLE001  單一版本壞掉就略過
                continue
            if fx.get("rate") and fx.get("date") and fx["date"] not in d["fx_usd_twd"]:
                d["fx_usd_twd"][fx["date"]] = float(fx["rate"])
                added += 1
        print(f"git 歷史還原匯率 {added} 天（共 {len(d['fx_usd_twd'])} 天）")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] git 歷史還原匯率失敗：{e}")


def main() -> int:
    force = "--force" in sys.argv[1:]
    today = datetime.now(TW).strftime("%Y-%m-%d")
    d = load()
    record_fx(d)
    if len(d["fx_usd_twd"]) < 20:
        backfill_fx_from_git(d)
    if not force and any(x.get("tw_date") == today for x in d["fetch_log"]):
        print(f"{today} 已抓過，零請求")
        OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return 0
    period = "5d" if d["returns"] else "3mo"
    tick = tickers()
    import pandas as pd
    import yfinance as yf
    log = {"tw_date": today, "at": datetime.now(TW).isoformat(timespec="seconds"), "period": period,
           "n_tickers": len(tick), "requests": 1}
    try:
        df = yf.download(tick, period=period, auto_adjust=True, progress=False, threads=True)
        px = df["Close"].copy()
        px.index = pd.to_datetime(px.index).tz_localize(None)
        R = px.pct_change(fill_method=None).iloc[1:]
        n_new = 0
        for ts, row in R.iterrows():
            ds = ts.strftime("%Y-%m-%d")
            vals = {k: round(float(v), 8) for k, v in row.items() if pd.notna(v)}
            if not vals:
                continue
            if ds not in d["returns"]:
                n_new += 1
            d["returns"][ds] = vals
        # F16 的 B/M 分母要價位：每次下載視窗內的還原收盤照存（以最新一次下載覆蓋；只拿來在換股日算 B/M，不拿來算報酬）
        d.setdefault("closes", {})
        for ts, row in px.iterrows():
            cl = {k: round(float(v), 6) for k, v in row.items() if pd.notna(v)}
            if cl:
                d["closes"][ts.strftime("%Y-%m-%d")] = cl
        log.update(ok=True, rows=len(R), new_dates=n_new, last=max(d["returns"]) if d["returns"] else None,
                   n_with_price=int(px.iloc[-1].notna().sum()))
        print(f"抓到 {len(R)} 個交易日報酬（新日期 {n_new}），最後 {log['last']}，最後一天有價 {log['n_with_price']} 檔")
    except Exception as e:  # noqa: BLE001
        log.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
        print(f"[warn] yfinance 下載失敗（保留上一版、不重試）：{e}")
    d["fetch_log"] = (d["fetch_log"] + [log])[-200:]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"[warn] fetch_paper_opt_us_prices 失敗：{e}")
        sys.exit(0)
