# -*- coding: utf-8 -*-
"""先.九十五-R11：抓證交所「發行量加權股價指數歷史資料」MI_5MINS_HIST 1999-01～2010-12 每日開盤／最高／最低／收盤指數
（research/DATA_GAP_PLAN.md #13：2010 前每日開盤價，甲類已查證可得、尚未抓）。只補資料，不寫 PREREG、不登記試驗、不回測。

端點：https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?date=YYYYMM01&response=json（一次回一整個月）。
robots.txt（2026-10-14 查）：User-agent * 只禁 /epaper/、/FTSE/，其餘 Allow；官方未公布次數上限。
與 data/rate_limit_state.json 共用節流（來源名 twse_rwd，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試）。
每月存一個原始 JSON 到 research/data/taiex_open_hist/YYYYMM.json，已抓的月份不重抓；
回應不是合法 JSON 或 stat 不是 OK → 停抓（不猜格式）。

用法：python research/fetch_taiex_open_hist.py [--until HH:MM]   （台北時間到點就停，留斷點給下一輪）
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from backfill_price_history_gaps import _rate_limit_record_block, _rate_limit_wait_or_raise  # noqa: E402

SRC = "twse_rwd"
URL = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST"
OUT = HERE / "data" / "taiex_open_hist"
BLOCK = {402, 403, 428, 429}
UA = "alpha-research/1.0 (personal research; daily-bar backfill)"


def months():
    for y in range(1999, 2011):
        for m in range(1, 13):
            yield f"{y}{m:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", help="台北時間 HH:MM 到點就停（不送新請求）")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    n_req = n_new = 0
    todo = [ym for ym in months() if not (OUT / f"{ym}.json").exists()]
    print(f"尚缺 {len(todo)} 個月（共 144）", flush=True)
    for ym in todo:
        if a.until and datetime.now().strftime("%H:%M") >= a.until:
            print(f"到 {a.until}，停止；下一輪從 {ym} 續", flush=True)
            break
        try:
            _rate_limit_wait_or_raise(SRC)
        except RuntimeError as e:
            print(f"節流拒絕：{e}", flush=True)
            return 2
        r = requests.get(URL, params={"date": f"{ym}01", "response": "json"}, timeout=60, headers={"User-Agent": UA})
        n_req += 1
        if r.status_code in BLOCK:
            _rate_limit_record_block(SRC, r.status_code, "MI_5MINS_HIST")
            print(f"HTTP {r.status_code}，封鎖 2 小時，停止（斷點 {ym}）", flush=True)
            return 2
        try:
            j = r.json()
        except ValueError:
            print(f"{ym}：回應不是 JSON（HTTP {r.status_code}，前 80 字：{r.text[:80]!r}），停止", flush=True)
            return 3
        if j.get("stat") != "OK" or not j.get("data"):
            print(f"{ym}：stat={j.get('stat')!r}、data {len(j.get('data') or [])} 列，停止（不猜格式）", flush=True)
            return 3
        (OUT / f"{ym}.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        n_new += 1
        print(f"{ym}：{len(j['data'])} 個交易日，欄位 {j.get('fields')}", flush=True)
    left = sum(1 for ym in months() if not (OUT / f"{ym}.json").exists())
    print(f"本次請求 {n_req} 次、新存 {n_new} 個月；尚缺 {left} 個月", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
