# -*- coding: utf-8 -*-
"""30天執行品質五題計分卡（深讀五，2026-09-15新增）。

裁示五原文：「第一個30天只看執行品質五題（對帳30/30、中位滑價≤回測假設2倍、
成交率≥95%、零非預期停擺、kill演練過一次），不看損益。」這支檔案是把這五題
變成可以真正跑出結果的程式，而不是只停留在文件裡的一句話（比照
`research/candidate_report.py`「規則變成可執行的閘門」同一個精神）。

**現況誠實揭露**：`research/execution_logs.py`底下五本帳本目前全是空的
（尚無真實下單路徑會寫入），所以`compute_scorecard()`現在跑出來五題全部是
`INSUFFICIENT_DATA`——這是正確、誠實的結果，不是bug，**不得為了讓這裡顯示
PASS而塞入假資料**（違反`C:\\alpha\\alpha-app\\CLAUDE.md`「假資料一律不得
出現」）。等真的有券商下單API接進來、`execution_logs.py`開始被呼叫記錄真實
成交後，這支程式才會產出有意義的PASS/FAIL。

**第2題的回測假設基準**：讀`research/validation/costs.py`的
`DEFAULT_SLIPPAGE_BPS`（目前5.0bp，台股單腳，非經驗校準的預設值，見該檔
docstring）。比較的是`vs_signal_bp`的中位數（含決策到成交的整段價格漂移，
理由見`execution_logs.py`模組docstring），門檻＝`2 × DEFAULT_SLIPPAGE_BPS`。

跑法：
    python execution_quality_scorecard.py            # 印出30天五題計分卡
    python execution_quality_scorecard.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "validation"))

import execution_logs as el  # noqa: E402
from validation.costs import DEFAULT_SLIPPAGE_BPS as TW_BACKTEST_SLIPPAGE_BPS  # noqa: E402

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"

FILL_RATE_THRESHOLD = 0.95
RECONCILIATION_WINDOW_DAYS = 30
MIN_RECONCILIATION_DAYS_FOR_PASS = 30  # 「30/30」字面意思：要滿30天資料才能判PASS


def score_q1_reconciliation(window_days: int = RECONCILIATION_WINDOW_DAYS) -> dict:
    streak = el.reconciliation_streak(window_days=window_days)
    total, match = streak["total"], streak["match"]
    if total < MIN_RECONCILIATION_DAYS_FOR_PASS:
        return {"status": STATUS_INSUFFICIENT, "match": match, "total": total,
                "detail": f"目前只有{total}天對帳紀錄，未滿{MIN_RECONCILIATION_DAYS_FOR_PASS}天，無法判定"}
    status = STATUS_PASS if match == total else STATUS_FAIL
    return {"status": status, "match": match, "total": total,
            "detail": f"{match}/{total}天對帳無不符" if status == STATUS_PASS
            else f"{total - match}天對帳不符：{streak['mismatches']}"}


def score_q2_slippage(window_days: int = 30, backtest_bps: float = TW_BACKTEST_SLIPPAGE_BPS) -> dict:
    threshold = 2 * backtest_bps
    median, n = el.median_vs_signal_bp(window_days=window_days, dry_run=False)
    if median is None:
        return {"status": STATUS_INSUFFICIENT, "median_vs_signal_bp": None, "n": 0,
                "threshold_bp": threshold,
                "detail": "尚無真錢滑價紀錄（dry_run=False），無法判定"}
    status = STATUS_PASS if median <= threshold else STATUS_FAIL
    return {"status": status, "median_vs_signal_bp": median, "n": n, "threshold_bp": threshold,
            "detail": f"中位vs_signal_bp={median:.2f}，門檻={threshold:.2f}（回測假設{backtest_bps}bp的2倍）"}


def score_q3_fill_rate(window_days: int = 30) -> dict:
    rate, n = el.fill_rate(window_days=window_days, dry_run=False)
    if rate is None:
        return {"status": STATUS_INSUFFICIENT, "fill_rate": None, "n": 0,
                "detail": "尚無真錢下單嘗試紀錄（dry_run=False），無法判定"}
    status = STATUS_PASS if rate >= FILL_RATE_THRESHOLD else STATUS_FAIL
    return {"status": status, "fill_rate": rate, "n": n,
            "detail": f"成交率={rate:.1%}（{n}筆），門檻≥{FILL_RATE_THRESHOLD:.0%}"}


def score_q4_reliability(window_days: int = 30) -> dict:
    n_outage = el.unexpected_outage_count(window_days=window_days)
    all_outages = el._payloads(el.OUTAGE_LOG_PATH)
    if not all_outages:
        return {"status": STATUS_INSUFFICIENT, "unexpected_outages": 0,
                "detail": "尚無停擺紀錄——可能代表基礎設施尚未啟用真錢排程，不等於已驗證零停擺"}
    status = STATUS_PASS if n_outage == 0 else STATUS_FAIL
    return {"status": status, "unexpected_outages": n_outage,
            "detail": f"過去{window_days}天{n_outage}次非預期停擺"}


def score_q5_kill_drill(window_days: int | None = None) -> dict:
    drills = el._payloads(el.KILL_DRILL_LOG_PATH)
    if not drills:
        return {"status": STATUS_INSUFFICIENT, "detail": "尚未演練過kill switch"}
    passed = el.has_passing_drill(window_days=window_days)
    status = STATUS_PASS if passed else STATUS_FAIL
    return {"status": status, "n_drills": len(drills),
            "detail": "至少一次kill switch演練成功" if passed else f"{len(drills)}次演練皆未通過"}


def compute_scorecard(window_days: int = 30) -> dict:
    return {
        "q1_對帳": score_q1_reconciliation(window_days),
        "q2_滑價": score_q2_slippage(window_days),
        "q3_成交率": score_q3_fill_rate(window_days),
        "q4_可靠度": score_q4_reliability(window_days),
        "q5_kill演練": score_q5_kill_drill(),
    }


def all_passed(scorecard: dict) -> bool:
    return all(q["status"] == STATUS_PASS for q in scorecard.values())


def _self_test() -> int:
    import shutil
    import tempfile

    orig_log_dir = el.LOG_DIR
    orig_paths = (el.SLIPPAGE_LOG_PATH, el.ORDER_ATTEMPTS_LOG_PATH, el.RECONCILIATION_LOG_PATH,
                  el.OUTAGE_LOG_PATH, el.KILL_DRILL_LOG_PATH, el.ALL_LOG_PATHS)
    tmp = Path(tempfile.mkdtemp(prefix="alpha_scorecard_selftest_"))
    el.LOG_DIR = tmp
    el.SLIPPAGE_LOG_PATH = tmp / "slippage_log.jsonl"
    el.ORDER_ATTEMPTS_LOG_PATH = tmp / "order_attempts.jsonl"
    el.RECONCILIATION_LOG_PATH = tmp / "reconciliation_log.jsonl"
    el.OUTAGE_LOG_PATH = tmp / "outage_log.jsonl"
    el.KILL_DRILL_LOG_PATH = tmp / "kill_drill_log.jsonl"
    el.ALL_LOG_PATHS = (el.SLIPPAGE_LOG_PATH, el.ORDER_ATTEMPTS_LOG_PATH, el.RECONCILIATION_LOG_PATH,
                         el.OUTAGE_LOG_PATH, el.KILL_DRILL_LOG_PATH)

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    try:
        # 空狀態 -> 五題全部INSUFFICIENT_DATA，不得偽裝成PASS
        sc = compute_scorecard()
        for key, q in sc.items():
            check(f"空狀態{key}應為INSUFFICIENT_DATA", q["status"] == STATUS_INSUFFICIENT)
        check("空狀態all_passed應為False", all_passed(sc) is False)

        # 灌入30天全MATCH的對帳紀錄 -> q1應PASS
        for i in range(30):
            el.log_reconciliation(date=f"2026-08-{(i % 28) + 1:02d}", book="test", status="MATCH")
        q1 = score_q1_reconciliation()
        check("30天全MATCH應PASS", q1["status"] == STATUS_PASS and q1["total"] == 30)

        el.log_reconciliation(date="2026-09-15", book="test", status="MISMATCH")
        q1b = score_q1_reconciliation()
        check("加入一筆MISMATCH後應FAIL", q1b["status"] == STATUS_FAIL)

        # 滑價：中位數低於門檻 -> PASS；高於門檻 -> FAIL
        for _ in range(5):
            el.log_slippage(book="test", symbol="2330", side="BUY", signal_px=100.0,
                             intended_px=100.0, filled_px=100.05, qty=1000, fee_twd=1.0,
                             session="盤中逐筆撮合", dry_run=False)
        q2 = score_q2_slippage()
        check(f"低滑價應PASS（median={q2.get('median_vs_signal_bp')}）", q2["status"] == STATUS_PASS)

        for _ in range(5):
            el.log_slippage(book="test2", symbol="2330", side="BUY", signal_px=100.0,
                             intended_px=100.0, filled_px=110.0, qty=1000, fee_twd=1.0,
                             session="盤中逐筆撮合", dry_run=False)
        q2b = score_q2_slippage()
        check("混入高滑價後中位數應提高並判FAIL或仍PASS視門檻而定", q2b["median_vs_signal_bp"] is not None)

        # 成交率
        for _ in range(19):
            el.log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="FILLED", dry_run=False)
        el.log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="REJECTED", dry_run=False)
        q3 = score_q3_fill_rate()
        check("19/20=95%應PASS", q3["status"] == STATUS_PASS)

        el.log_order_attempt(book="test", symbol="2330", side="BUY", qty=1000, status="REJECTED", dry_run=False)
        q3b = score_q3_fill_rate()
        check("19/21<95%應FAIL", q3b["status"] == STATUS_FAIL)

        # 可靠度
        el.log_outage(duration_min=1, reason="測試預期", expected=True)
        q4 = score_q4_reliability()
        check("只有預期停擺應PASS", q4["status"] == STATUS_PASS)
        el.log_outage(duration_min=1, reason="測試非預期", expected=False)
        q4b = score_q4_reliability()
        check("出現非預期停擺應FAIL", q4b["status"] == STATUS_FAIL)

        # kill演練
        el.log_kill_drill(state_tested="halt_new", result="FAIL", note="測試失敗案例")
        q5 = score_q5_kill_drill()
        check("只有FAIL演練應判FAIL", q5["status"] == STATUS_FAIL)
        el.log_kill_drill(state_tested="halt_new", result="PASS", note="測試成功案例")
        q5b = score_q5_kill_drill()
        check("出現PASS演練後應判PASS", q5b["status"] == STATUS_PASS)

    finally:
        el.LOG_DIR = orig_log_dir
        (el.SLIPPAGE_LOG_PATH, el.ORDER_ATTEMPTS_LOG_PATH, el.RECONCILIATION_LOG_PATH,
         el.OUTAGE_LOG_PATH, el.KILL_DRILL_LOG_PATH, el.ALL_LOG_PATHS) = orig_paths
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"[FAIL] {len(failures)}項未過：{failures}")
        return 1
    print("[PASS] execution_quality_scorecard.py 自我測試全部通過（暫存目錄執行）")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        sys.exit(_self_test())
    scorecard = compute_scorecard()
    print(json.dumps(scorecard, ensure_ascii=False, indent=2))
    print(f"\n五題全過: {all_passed(scorecard)}")
