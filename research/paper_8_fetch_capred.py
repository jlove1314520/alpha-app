# -*- coding: utf-8 -*-
"""模擬 H 訓練面板補抓減資表（先.一二七-B2 第 3 段，[自行裁量] 選 (a)）。

只補 research/data/paper_8_train_panel/ 裡因「本機無快取 TaiwanStockCapitalReductionReferencePrice」失敗的檔；
cache key 與 adjust.py 走 load_dev 時完全相同（2010-01-01～2024-12-31，不碰 holdout）。
節流：finmind_client 共用 rate_limit_state（同源間隔、402/403/428/429 封鎖 2 小時不重試）；
另外自設上限：近一小時 FinMind 呼叫數達 HOURLY_SOFT_CAP 就停（留額度給其他排程）。
抓到的檔把面板失敗檔刪掉，下一次 build-panel 自動重算。
用法：python research/paper_8_fetch_capred.py --until HH:MM
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
sys.path.insert(0, str(RESEARCH))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import finmind_client as fc  # noqa: E402

TW = timezone(timedelta(hours=8))
PANEL_DIR = RESEARCH / "data" / "paper_8_train_panel"
DATASET = "TaiwanStockCapitalReductionReferencePrice"
START, END = "2010-01-01", "2024-12-31"
HOURLY_SOFT_CAP = 450  # 方案上限 600／小時，留 150 給其他排程


def failed_ids() -> list[str]:
    out = []
    for p in sorted(PANEL_DIR.glob("*.json")):
        err = json.loads(p.read_text(encoding="utf-8")).get("error") or ""
        if re.search(rf"無快取 {DATASET}/", err):
            out.append(p.stem)
    return out


def main(argv: list[str]) -> int:
    until = argv[argv.index("--until") + 1] if "--until" in argv else None
    ids = failed_ids()
    print(f"減資快取缺：{len(ids)} 檔；近一小時已用 {fc.calls_last_hour()} 次")
    n_ok = n_nonempty = 0
    for i, sid in enumerate(ids):
        if until and datetime.now(TW).strftime("%H:%M") >= until:
            print(f"到 {until} 停止；尚餘 {len(ids) - i} 檔，下一批從 {sid} 開始")
            break
        if fc.calls_last_hour() >= HOURLY_SOFT_CAP:
            print(f"近一小時呼叫數達 {HOURLY_SOFT_CAP}，停止；尚餘 {len(ids) - i} 檔")
            break
        try:
            df = fc._fetch(DATASET, sid, START, END)
        except Exception as e:  # noqa: BLE001
            print(f"  {sid}: 抓取失敗 {type(e).__name__}: {str(e)[:160]}——停止本批（不重試）")
            break
        n_ok += 1
        n_nonempty += int(not df.empty)
        (PANEL_DIR / f"{sid}.json").unlink()  # 刪失敗檔，build-panel 會重算
        if n_ok % 25 == 0:
            print(f"  進度 {n_ok}（非空 {n_nonempty}）{datetime.now(TW).strftime('%H:%M:%S')}")
    print(json.dumps({"fetched": n_ok, "nonempty": n_nonempty, "remaining": len(failed_ids())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
