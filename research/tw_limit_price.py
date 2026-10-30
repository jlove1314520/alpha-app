# -*- coding: utf-8 -*-
"""轉接殼（收件匣 032，2026-10-30）：官方漲跌停價規則已併進 `research/official_limit.py`，本檔不再有自己的實作。

只為了舊文件（模擬 J／N PREREG 修訂 R1 等）引用的 `tw_limit_price.limit_prices` 名稱仍可用；新程式一律 `import official_limit`。
要改規則或填 `TICK_1000_TO_1_EFFECTIVE`，改 `official_limit.py`。
"""
from official_limit import (  # noqa: F401
    LIMIT_10PCT_FROM, MIN_TICK, TICK_1000_TO_1_EFFECTIVE, VERIFIED_FROM, limit_prices, limit_rate, tick_size,
)
