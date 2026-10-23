# -*- coding: utf-8 -*-
"""先.一三三-2（2026-10-23，DevQueue 20261023-103102）：個股網格／ML 價量兩份 FINAL 修訂草稿用的候選窗口涵蓋率。

零請求、只讀本機快取、不算任何報酬。判斷式完全沿用 var1018_v1_coverage_windows.coverage_all()（V1 定稿同一定義：
主定義＝官方確認停牌不算缺口，*_satfix＝週六補班交易日缺口用 bdate_range 計），只換候選窗口。
候選窗口只依「資料可得性」挑（上櫃官方日檔 2007-07 起、暖機期是否落在官方可佐證區），不看任何報酬。

跑法：cd research && python var1018_revision_coverage_windows.py
輸出：research/data/var1018_revision_coverage_windows.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import pandas as pd

import var1018_v1_coverage_windows as C
import var1018_v1_lowmem as L
import var1018_v1_prep as V

OUT = Path(__file__).parent / "data" / "var1018_revision_coverage_windows.json"
CAND = {
    # 個股網格（原 2007-01-02～2009-12-31）
    "GRID_A_20070702_20091231": ("2007-07-02", "2009-12-31"),   # 起點移 R1-b，同終點（30 個月）
    "GRID_B_20071001_20091231": ("2007-10-01", "2009-12-31"),   # 首次建格的 60 日暖機全落在官方可佐證區（27 個月）
    "GRID_C_20070702_20100630": ("2007-07-02", "2010-06-30"),   # 保留 36 個月、終點延到 2010-06
    # ML 價量（原 2006-01-02～2012-12-31，測試年 2008～2012）
    "ML_A_20080102_20121231": ("2008-01-02", "2012-12-31"),     # 只量測試期（訓練期缺口另揭露）
    "ML_B_20070702_20121231": ("2007-07-02", "2012-12-31"),     # 資料窗起點移 R1-b
    "ML_C_20090102_20121231": ("2009-01-02", "2012-12-31"),     # 測試年改 2009～2012
}


def main() -> int:
    C.WINDOWS = CAND  # coverage_all() 讀模組層級 WINDOWS；判斷式不變
    cands, dead = V.candidates()
    idx = L.build_index()
    print(f"官方精簡索引：{len(idx['day_status'])} 天；峰值 {L.peak_mb()} MB", flush=True)
    dl = pd.read_parquet(V.RAW / "TaiwanStockDelisting__ALL__1990-01-01__latest.parquet")
    dl["date"] = pd.to_datetime(dl["date"])
    ddate = dict(zip(dl["stock_id"], dl["date"]))
    del dl
    res = C.coverage_all(cands, dead, idx, ddate)
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"),
           "rule": "同 var1018_v1_coverage_windows.coverage_all()（V1 定稿定義），只換候選窗口；零請求、未算報酬",
           "peak_working_set_mb": L.peak_mb(), "windows": {}}
    for k, (a, b) in CAND.items():
        out["windows"][k] = {"t0": a, "end": b, **res[k]}
        print(k, json.dumps(out["windows"][k], ensure_ascii=False), flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
