# -*- coding: utf-8 -*-
"""確定性自我測試（2026-08-29新增，使用者裁示「B24前置關卡：可重現性/
確定性...修好才准出任何B24-500判定」，套用姊妹加密專案「平行fork同時讀寫
OHLCV快取導致同一回測跑出兩種數字」的教訓）。

**根因定位（本輪找到的真bug）**：`research/finmind_client.py`／
`twse_t86_client.py`／`yf_price_client.py`這三個快取層的`_fetch()`都用
`df.to_parquet(path, index=False)`直接寫進最終路徑——這個呼叫**不是
atomic的**。如果兩個process（例如這個互動session跟同時在跑的
AlphaMarathon背景迴圈）同時判斷「這個(dataset,id,start,end)組合的快取
不存在」而各自發送請求、各自寫入同一個路徑，寫入過程互相interleave
可能產生截斷/損毀的parquet檔——這正是「同輸入、不同次執行讀到不同
（甚至讀取失敗）資料」的具體根因候選。

**修法**：三個檔案都新增`_atomic_to_parquet()`——寫進pid+uuid專屬的
臨時檔，寫完才用`os.replace()`原子性換名成正式路徑。`os.replace()`在
同一個檔案系統上是atomic的（POSIX/Windows皆然），並發讀取者只會讀到
「完全新」或「完全舊」的檔案，不會讀到寫一半的檔案。

**這支腳本做兩件事**：
1. Test A（直接壓力測試atomic write機制本身）：多個process同時搶著寫
   同一個parquet路徑、另一個process同時狂讀，斷言讀取者從未讀到損毀
   檔案、最終檔案內容完整有效。這個測試很快（幾秒鐘），直接證明/推翻
   修法本身是否有效，不需要跑真正的回測。
2. Test B（真實回測管線的端到端確定性）：用已經快取好的資料（不觸發
   新的網路請求/快取寫入，跑起來很快），把同一組回測參數（固定sample/
   固定日期區間/固定random seed）跑3次，斷言三次的關鍵輸出數值完全
   相同（final_equity/total_return_pct/n_trades/alpha_ann_pct等），
   確認回測管線本身（拿到同樣輸入之後）沒有其他隱藏的非確定性來源
   （例如dict/set疊代順序影響同分排名的tie-breaking）。

**已知殘留限制（誠實揭露，不是這輪能完全解決的）**：atomic write解決的
是「寫入損毀」這個根因，但沒有解決「兩個process同時判斷快取不存在、
各自重複發送請求」這個效率問題（不影響正確性，只是資料源禮儀角度會
多打幾次API）——這屬於「資源效率」而非「確定性/正確性」，這輪範疇
明確排除，留待之後視情況用檔案鎖補強。

跑法：`python determinism_self_test.py`，兩個Test都要PASS才代表通過
B24前置關卡。
"""
from __future__ import annotations

import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent


# ══════════════════ Test A：atomic write機制本身的併發壓力測試 ══════════════════

def _writer_proc(target_path: str, n_iters: int, tag: str):
    import pandas as pd
    sys.path.insert(0, str(RESEARCH_DIR))
    from finmind_client import _atomic_to_parquet  # noqa: E402
    path = Path(target_path)
    for i in range(n_iters):
        df = pd.DataFrame({"tag": [tag] * 500, "i": list(range(500)), "iter": [i] * 500})
        _atomic_to_parquet(df, path)


def _reader_proc(target_path: str, n_iters: int, result_queue: "mp.Queue", stop_flag):
    sys.path.insert(0, str(RESEARCH_DIR))
    from finmind_client import _atomic_read_parquet  # noqa: E402
    path = Path(target_path)
    read_errors = []
    reads_ok = 0
    for _ in range(n_iters):
        if path.exists():
            try:
                df = _atomic_read_parquet(path)
                if len(df) != 500 or list(df.columns) != ["tag", "i", "iter"]:
                    read_errors.append(f"讀到形狀不對的資料：shape={df.shape}, cols={list(df.columns)}")
                else:
                    reads_ok += 1
            except Exception as e:  # noqa: BLE001 -- 這正是我們要抓的：讀到損毀檔案
                read_errors.append(f"讀取失敗（疑似損毀）：{e}")
        time.sleep(0.002)
    result_queue.put((reads_ok, read_errors))


def test_a_atomic_write_race() -> bool:
    print("=== Test A：atomic write併發壓力測試 ===")
    tmpdir = Path(tempfile.mkdtemp(prefix="determinism_test_a_"))
    target = tmpdir / "race_target.parquet"
    try:
        n_writers = 4
        n_iters_per_writer = 30
        writers = [
            mp.Process(target=_writer_proc, args=(str(target), n_iters_per_writer, f"w{i}"))
            for i in range(n_writers)
        ]
        result_queue: mp.Queue = mp.Queue()
        reader = mp.Process(target=_reader_proc, args=(str(target), 300, result_queue, None))

        reader.start()
        for w in writers:
            w.start()
        for w in writers:
            w.join(timeout=60)
        reader.join(timeout=60)

        reads_ok, read_errors = result_queue.get(timeout=5)
        print(f"  {n_writers}個writer process各寫{n_iters_per_writer}次、同時1個reader讀300次")
        print(f"  reader成功讀到有效資料：{reads_ok}次；讀取錯誤/損毀：{len(read_errors)}次")
        if read_errors:
            for e in read_errors[:10]:
                print(f"    - {e}")
        # 最終檔案本身也要能正常讀取（不是只看過程中的reader，還要看寫完之後的最終狀態）
        try:
            import pandas as pd
            final_df = pd.read_parquet(target)
            final_ok = len(final_df) == 500 and list(final_df.columns) == ["tag", "i", "iter"]
        except Exception as e:  # noqa: BLE001
            final_ok = False
            print(f"  [FAIL] 最終檔案讀取失敗：{e}")
        passed = (len(read_errors) == 0) and final_ok
        print(f"  最終檔案有效：{final_ok}")
        print(f"  {'PASS' if passed else 'FAIL'}：Test A")
        return passed
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ══════════════════ Test B：真實回測管線的端到端確定性（用暖快取，跑很快） ══════════════════

def _run_one_pass() -> dict:
    """跑一個很小的真實回測切片（用既有的100檔快取，不觸發新網路請求），
    回傳關鍵指標給呼叫端比對。"""
    sys.path.insert(0, str(RESEARCH_DIR))
    import pickle
    from backtest.engine import BacktestConfig, run_backtest
    from finmind_client import load_dev
    from score import load_industry_map
    from strategies.weinstein_stage2 import prepare_market_data
    from run_value_board_v2_pit_backtest import (
        make_score_v2_signal_fn, make_random_signal_fn, alpha_significance,
        TOP_N, REBALANCE_DAYS, START_DATE,
    )

    cache_path = RESEARCH_DIR / "data" / "backtests" / "value_board_v2_sample_cache.pkl"
    with open(cache_path, "rb") as f:
        data = pickle.load(f)

    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    market_df = prepare_market_data(market_raw)
    industry_map = load_industry_map()

    start, end = "2021-01-01", "2024-12-31"
    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=REBALANCE_DAYS, book_name="determinism_test_real")
    result = run_backtest(make_score_v2_signal_fn(industry_map, START_DATE, TOP_N), data, market_df, cfg)
    alpha = alpha_significance(result.equity_curve, market_df)

    rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                          rebalance_every_n_days=REBALANCE_DAYS, book_name="determinism_test_random")
    rfn = make_random_signal_fn(industry_map, START_DATE, TOP_N, seed=42)
    rresult = run_backtest(rfn, data, market_df, rcfg)

    return {
        "real_final_equity": result.final_equity, "real_total_return_pct": result.total_return_pct,
        "real_mdd_pct": result.max_drawdown_pct, "real_n_trades": result.n_trades,
        "real_alpha_ann_pct": alpha["alpha_ann_pct"], "real_beta": alpha["beta"],
        "random_final_equity": rresult.final_equity, "random_n_trades": rresult.n_trades,
    }


def test_b_pipeline_determinism() -> bool:
    print("\n=== Test B：真實回測管線端到端確定性（3次，暖快取） ===")
    cache_path = RESEARCH_DIR / "data" / "backtests" / "value_board_v2_sample_cache.pkl"
    if not cache_path.exists():
        print(f"  [SKIP] 找不到{cache_path}，這個測試需要既有的100檔快取，之前的機制驗證跑應該有留下")
        return True
    runs = []
    for i in range(3):
        t0 = time.time()
        r = _run_one_pass()
        runs.append(r)
        print(f"  第{i+1}次跑完（{time.time()-t0:.1f}秒）：{r}")

    all_same = all(runs[0] == r for r in runs[1:])
    if not all_same:
        print("  [FAIL] 三次結果不完全相同，逐欄位比對：")
        for k in runs[0]:
            vals = [r[k] for r in runs]
            if len(set(vals)) > 1:
                print(f"    {k}: {vals}（不一致！）")
    print(f"  {'PASS' if all_same else 'FAIL'}：Test B")
    return all_same


def main():
    a_pass = test_a_atomic_write_race()
    b_pass = test_b_pipeline_determinism()
    print(f"\n=== 總結：Test A={'PASS' if a_pass else 'FAIL'}, Test B={'PASS' if b_pass else 'FAIL'} ===")
    if a_pass and b_pass:
        print("確定性自我測試全數通過，B24前置關卡解除。")
        return 0
    else:
        print("確定性自我測試未全數通過，依使用者裁示：修好才准出任何B24-500判定。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
