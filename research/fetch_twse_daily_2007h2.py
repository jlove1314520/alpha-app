"""上市 2007H2 其餘交易日官方日檔原文補抓（給 probe_twse_daily_x_marks.py 核對「漲跌(+/-)」欄 X 標記）。

- 端點：www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALLBUT0999&response=json
  （同 var1018_v1_official_fill.py／var1018_v1_reduction_events.py，官方未公布上限）
- 交易日：本機 research/data/taiex_open_hist/2007MM.json（MI_5MINS_HIST 加權指數月檔）2007-07～12 的日期，
  扣掉 research/data/raw/v1_resume_day/twse/ 已有的恢復買賣日。
- 節流：共用 rate_limit_state 來源名 twse_mi_index（跨行程鎖、同源 ≥3 秒），
  402/403/428/429 即封鎖 2 小時並停止，不重試。
- 原始回應存 research/data/raw/twse_daily_2007h2/YYYYMMDD.json，已存的不重抓；
  --deadline HH:MM（本機時間）到了就停止送新請求，下次執行從沒抓的日期續。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402
from var1018_v1_official_fill import BLOCK, SOURCES, UA  # noqa: E402

TAIEX = HERE / "data" / "taiex_open_hist"
RESUME = HERE / "data" / "raw" / "v1_resume_day" / "twse"
OUT = HERE / "data" / "raw" / "twse_daily_2007h2"


def trading_days_2007h2() -> list[str]:
    days = set()
    for m in range(7, 13):
        j = json.loads((TAIEX / f"2007{m:02d}.json").read_text(encoding="utf-8"))
        for r in j.get("data") or []:
            mm = re.match(r"\s*(\d+)/(\d+)/(\d+)", str(r[0]))
            if mm:
                days.add(f"{int(mm[1]) + 1911}{int(mm[2]):02d}{int(mm[3]):02d}")
    return sorted(days)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", help="HH:MM，到了就停止送新請求")
    a = ap.parse_args()
    dl = None
    if a.deadline:
        h, m = map(int, a.deadline.split(":"))
        dl = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
    have = {f.stem for f in RESUME.glob("*.json")}
    todo = [d for d in trading_days_2007h2() if d not in have and not (OUT / f"{d}.json").exists()]
    print(f"待抓 {len(todo)} 天", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = SOURCES["twse"]
    sent = ok = 0
    for d in todo:
        if dl and datetime.now() >= dl:
            print(f"到截止時間 {a.deadline}，停在 {d}（下次從這天續）", flush=True)
            break
        _rate_limit_wait_or_raise(cfg["rl"])
        sent += 1
        r = requests.get(cfg["url"], params=cfg["params"](d), timeout=60, headers={"User-Agent": UA})
        if r.status_code in BLOCK:
            _rate_limit_record_block(cfg["rl"], r.status_code, f"fetch_twse_daily_2007h2 {d}")
            print(f"HTTP {r.status_code}，{cfg['rl']} 封鎖 2 小時，停止（已抓的保留）", flush=True)
            break
        try:
            js = r.json()
        except ValueError:
            print(f"⚠️ {d} HTTP {r.status_code} 回應不是 JSON，略過（不存檔，下次再試）", flush=True)
            continue
        if js.get("stat") != "OK" or not js.get("tables"):
            print(f"⚠️ {d} stat={js.get('stat')!r}，不存檔", flush=True)
            continue
        (OUT / f"{d}.json").write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
        ok += 1
    left = len([d for d in todo if not (OUT / f"{d}.json").exists()])
    print(f"送出 {sent} 次、存檔 {ok} 天、尚缺 {left} 天", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
