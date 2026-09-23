# -*- coding: utf-8 -*-
"""驗.一第4點續（剩餘16支）批次1——用新引擎(compounding修正)+新量尺
（0050含息總報酬基準+Newey-West HAC+Dimson beta，尺.一 commit已把這些
設成portfolio_backtest_v2.alpha_significance()/buy_and_hold_index_pct()
的預設值）重算已有checkpoint可續跑架構的3支腳本：
  - margin_utilization_regime_portfolio_v1（#120，原判定FAIL）
  - odd_lot_imbalance_portfolio_v1（#232，原判定FAIL）
  - short_sale_utilization_portfolio_v1（#133，原判定PASS第2關非最終結案）

三支腳本共用`run_one()`checkpoint可續跑機制（"real"清空後只重算真實訊號
單次回測，cost_returns/random_finals維持讀舊快取，不受benchmark/alpha
量尺影響，不必重算）。checkpoint的"real"欄位已在本輪先清空並備份
（*_checkpoint.pre_engine_fix_backup.json）。

跑法：python research/run_detached.py submit --name audit_16remaining_batch1
--timeout-min 40 --expect research/data/margin_utilization_regime_portfolio_v1_results.csv
-- python -u research/audit_16remaining_batch1.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).parent
SCRIPTS = [
    "margin_utilization_regime_portfolio_v1.py",
    "odd_lot_imbalance_portfolio_v1.py",
    "short_sale_utilization_portfolio_v1.py",
]


def main() -> None:
    for name in SCRIPTS:
        print(f"\n========== 執行 {name} ==========", flush=True)
        proc = subprocess.run(
            [sys.executable, "-u", str(HERE / name)],
            cwd=str(HERE),
            capture_output=False,
        )
        print(f"---------- {name} exit={proc.returncode} ----------", flush=True)


if __name__ == "__main__":
    main()
