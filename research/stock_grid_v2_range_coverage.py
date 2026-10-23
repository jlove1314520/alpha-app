# -*- coding: utf-8 -*-
"""先.一三三-2f（2026-10-24，DevQueue 20261024-023102）：網格變形②「只在區間市啟動」PREREG 草稿用的涵蓋率查核。

零請求、只讀本機快取、不算任何報酬。資料定義與判斷式完全沿用 `var1018_v1_r2_coverage.py`（V1 修訂 R2／網格 R1 同一定義），
只把窗口換成變形②草稿的驗證段 2010-01-04～2014-12-31，並另列含暖機（2009-09-01 起）的窗口。
輸出：research/data/stock_grid_v2_range_coverage.json
跑法：cd research && python stock_grid_v2_range_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import var1018_v1_r2_coverage as R  # noqa: E402

R.WINDOWS = {
    "GRID_V2_20100104_20141231": ("2010-01-04", "2014-12-31"),
    "GRID_V2_WARMUP_20090901_20141231": ("2009-09-01", "2014-12-31"),
}
R.OUT = Path(__file__).parent / "data" / "stock_grid_v2_range_coverage.json"

if __name__ == "__main__":
    raise SystemExit(R.main())
