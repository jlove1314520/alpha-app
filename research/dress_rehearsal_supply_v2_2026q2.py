"""紙.二 2026Q2 真實資料彩排（先.八-二，總司令 2026-10-01【先.八】二）。

**這不是回測，不算報酬，不是紙.二正式記錄。** 目的只有一個：用真實資料把
paper_supply_v2.py 的主流程（run()）在「期限 2026-08-14、換股日 2026-08-17」
這個歷史上已經發生過的季度上實際跑一次，看單一輪次（與排程每小時呼叫一次
完全相同的呼叫方式、相同的 REFRESH_BUDGET 預算）能走到哪一步，藉此在
2026-11-16 真正上線前先看到問題。

硬規則（對應裁示原文）：
- 只輸出：財報覆蓋率、價格覆蓋率、可計分檔數、落後池檔數、選出檔數、
  使用備援來源檔數、耗用 FinMind 次數與時間。
- 不得輸出任何 2026-08-17 之後的價格、淨值或報酬。
- 不得寫入 research/data/paper_supply_v2_log.jsonl（用不存在的暫存路徑＋
  dry=True 雙重保險，執行後驗證兩個暫存路徑確實仍不存在）。
- 彩排程式結束後刪除暫存結果，只留統計於 PROGRESS.md（本腳本不產生任何
  暫存結果檔案，統計直接印到標準輸出，由執行者複製進 PROGRESS.md）。

作法：直接呼叫 paper_supply_v2.run()（不複製貼上其內部邏輯），只在程序
記憶體內暫時把 FIRST_PERIOD／FIRST_REBALANCE 從 2026Q3／2026-11-16 換成
2026Q2／2026-08-17（純 Python 物件覆寫，不改寫 paper_supply_v2.py 原始碼、
不寫入任何檔案），讓 run() 把 2026Q2 當成「待處理期別」。budget 用與正式
排程相同的 REFRESH_BUDGET（200），因為「跑一次」要跟正式排程每小時呼叫
一次的呼叫方式完全一樣，這樣彩排結果才能回答「正式排程單一輪次會發生
什麼事」這個問題。
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paper_supply_v2 as v2  # noqa: E402
import finmind_client as fc  # noqa: E402  只用來在外層包一層計數器，不改動其邏輯

TARGET_PERIOD = pd.Period("2026Q2", freq="Q")
EXPECT_DEADLINE = pd.Timestamp("2026-08-14")
EXPECT_REBALANCE = pd.Timestamp("2026-08-17")
DUMMY_LOG = v2.DATA / "DRESS_REHEARSAL_2026Q2_log_DO_NOT_COMMIT.jsonl"
DUMMY_STATE = v2.DATA / "DRESS_REHEARSAL_2026Q2_state_DO_NOT_COMMIT.json"


class _Tee(io.TextIOBase):
    """同時寫進真正的 stdout（讓背景執行時仍看得到即時進度）與記憶體緩衝區
    （事後從裡面 regex 解析 run() 既有的 print 行，不用修改 paper_supply_v2.py）。"""

    def __init__(self, real):
        self.real = real
        self.buf = io.StringIO()

    def write(self, s):
        self.real.write(s)
        self.buf.write(s)
        return len(s)

    def flush(self):
        self.real.flush()


def main() -> int:
    # --budget 僅供互動視窗自我測試用（驗證控制流程不花太多時間），正式彩排一律用預設值
    # v2.REFRESH_BUDGET（與正式排程相同），結果摘要裡的「budget_used」會如實記錄這次用的是哪個值。
    budget = v2.REFRESH_BUDGET
    for a in sys.argv[1:]:
        if a.startswith("--budget="):
            budget = int(a.split("=", 1)[1])
    assert not DUMMY_LOG.exists(), f"暫存路徑 {DUMMY_LOG} 不應預先存在"
    assert not DUMMY_STATE.exists(), f"暫存路徑 {DUMMY_STATE} 不應預先存在"

    d = v2.deadline(TARGET_PERIOD)
    assert d == EXPECT_DEADLINE, f"2026Q2 期限算出 {d.date()}，與裁示原文 2026-08-14 不符，停止彩排"
    print(f"[彩排] 2026Q2 法定期限 D={d.date()}（與裁示原文一致）")

    orig_period, orig_rebalance = v2.FIRST_PERIOD, v2.FIRST_REBALANCE
    v2.FIRST_PERIOD = TARGET_PERIOD
    v2.FIRST_REBALANCE = EXPECT_REBALANCE
    print(f"[彩排] 暫時覆寫（僅程序記憶體，未寫檔）FIRST_PERIOD={v2.FIRST_PERIOD}／"
          f"FIRST_REBALANCE={v2.FIRST_REBALANCE.date()}（原值 {orig_period}／{orig_rebalance.date()} 執行結束後已還原）")

    call_count = [0]
    orig_fetch = fc._fetch

    def _counting_fetch(*a, **kw):
        call_count[0] += 1
        return orig_fetch(*a, **kw)

    now = datetime.now(timezone(timedelta(hours=8)))
    t0 = time.time()
    tee = _Tee(sys.stdout)
    orig_stdout = sys.stdout
    sys.stdout = tee
    fc._fetch = _counting_fetch
    try:
        src = v2.LiveSource()
        res = v2.run(src, now, log_path=DUMMY_LOG, state_path=DUMMY_STATE,
                     budget=budget, dry=True, verbose=True)
    finally:
        sys.stdout = orig_stdout
        fc._fetch = orig_fetch
        v2.FIRST_PERIOD, v2.FIRST_REBALANCE = orig_period, orig_rebalance
    elapsed = time.time() - t0
    captured = tee.buf.getvalue()

    log_touched = DUMMY_LOG.exists()
    state_touched = DUMMY_STATE.exists()
    if log_touched:
        DUMMY_LOG.unlink()
    if state_touched:
        DUMMY_STATE.unlink()

    stmt_cov = res.get(f"settled_{TARGET_PERIOD}")
    px_cov = res.get(f"px_ready_{TARGET_PERIOD}")
    sim = res.get("sim")

    # 「2026Q2：已產生訊號 S 檔（存活 A、可計分 Z、落後池 P）」只有真的走到 build_signal 才會出現；
    # FinMind 呼叫次數改用 _counting_fetch 的實際計數（涵蓋 run() 內部 spent 計數器之外的日曆／
    # 事件表前置呼叫，比只解析 print 行裡「本輪...呼叫 N 次」更完整誠實）。
    n_finmind_calls = call_count[0]
    sig_m = re.search(r"已產生訊號 (\d+) 檔（存活 (\d+)、可計分 (\d+)、落後池 (\d+)）", captured)
    fb_m = re.search(r"(\d+) 檔 FinMind 無可用價格，改用 yfinance 備援", captured)
    reached_signal = sig_m is not None

    summary = {
        "notice": "紙.二 2026Q2 真實資料彩排 — 非回測、非正式紙.二記錄、不算報酬",
        "period": str(TARGET_PERIOD),
        "deadline_D": str(d.date()),
        "rebalance_R": str(EXPECT_REBALANCE.date()),
        "run_status": res.get("status"),
        "budget_used（REFRESH_BUDGET，與正式排程相同）": budget,
        "財報覆蓋率": stmt_cov,
        "價格覆蓋率": px_cov,
        "可計分檔數": int(sig_m.group(3)) if sig_m else None,
        "落後池檔數": int(sig_m.group(4)) if sig_m else None,
        "選出檔數": int(sig_m.group(1)) if sig_m else None,
        "使用備援來源檔數": int(fb_m.group(1)) if fb_m else 0,
        "耗用FinMind次數": n_finmind_calls,
        "耗用時間秒": round(elapsed, 1),
        "log_file_touched（應為False）": log_touched,
        "state_file_touched（應為False）": state_touched,
        "備註": (
            "res['status']=='ok' 但未產生 sim 結果，代表本輪在 2026Q2 的覆蓋率門檻前就被擋下"
            "（財報或價格覆蓋率 < 80%，依 paper_supply_v2.py 既有規則記 skipped_data_unready，"
            "沿用既有持股、不補算），因此「可計分檔數／落後池檔數／選出檔數／使用備援來源檔數」"
            "本輪無法產出數字（production 的 build_signal 從未被呼叫到）。這本身就是彩排要找的問題，"
            "非程式錯誤：paper_supply_v2 的 STMT_START=2024-01-01／PRICE_START=2025-01-01 快取命名空間"
            "在本輪執行前完全是空的（0 個既有檔案），單一輪 REFRESH_BUDGET=200 預算下，"
            "財報覆蓋率只能從 0 筆漲到遠低於 80% 門檻的水準（詳見下方印出的覆蓋率數字）。"
            if not reached_signal else
            "本輪覆蓋率已達門檻、有實際呼叫 build_signal，以下統計為本輪實際結果。"
        ),
    }
    print("\n[彩排統計摘要]")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
