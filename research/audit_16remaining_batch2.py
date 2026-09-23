# -*- coding: utf-8 -*-
"""驗.一第4點續（剩餘16支）批次2——用新引擎(compounding修正)+新量尺
（0050含息總報酬基準+Newey-West HAC+Dimson beta）重算範圍確認後剩下的
2支：`run_value_board_v2_pit_backtest`（#93 baseline）／
`piotroski_fscore_gate_v1`（#94/#290/#291，piotroski的比較表要讀
run_value_board_v2_pit_backtest產生的baseline CSV，所以必須先跑前者
再跑後者，順序不可顛倒）。

**本輪（馬拉松第621輪）新增的前置修復**：這兩支腳本原本各自「自成一體
複製一份」`alpha_significance()`/`buy_and_hold_index_pct()`（docstring
自稱跟portfolio_backtest_v2.py逐行一致），尺.一只改了
portfolio_backtest_v2.py本體，margin/odd_lot/short_sale等候選因為是
直接`import portfolio_backtest_v2 as pbv2`才自動吃到修正，這兩支腳本
的複製版沒有自動更新，是一個獨立的既有bug（docstring承諾失效）。本輪
已修復`run_value_board_v2_pit_backtest.py`改成直接呼叫
`portfolio_backtest_v2`的版本（[自行裁量]記錄見`PENDING_QUEUE.md`
「驗.一第4點續」），`piotroski_fscore_gate_v1.py`透過
`from run_value_board_v2_pit_backtest import (..., alpha_significance, ...)`
間接沿用同一份修復，不需要再改。

**注意**：`run_value_board_v2_pit_backtest.main()`跑500檔流動性樣本、
TRAIN+VAL兩期各100次隨機對照draws，腳本docstring記錄實測約102秒/draw，
換算上限約200次×102秒≈5.7小時——這是已知的長工作，跨多輪馬拉松收成，
不在單一輪次25分鐘窗口內等待完成。

跑法：python research/run_detached.py submit --name audit_16remaining_batch2
--timeout-min 420 --expect research/data/piotroski_fscore_gate_v1_results.csv
-- python -u research/audit_16remaining_batch2.py
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
    "run_value_board_v2_pit_backtest.py",
    "piotroski_fscore_gate_v1.py",
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
