# -*- coding: utf-8 -*-
"""先.一百-4（2026-10-15）：App 顯示用回補檔不得被研究端讀取的守門自測。
掃 research/ 底下所有 .py（含子目錄；不含 research/validation/holdout.py 本身的清單定義），
出現 research/validation/holdout.py::DISPLAY_ONLY_DATA_FILES 任何一個檔名就 FAIL。
scripts/ 底下（build_research.py、backfill_*.py 這些 App 顯示端）不在檢查範圍。
另外自測守門本身：餵一段含檔名的假程式，確認會被抓到。用法：python scripts/selftest_display_only_files.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from validation.holdout import DISPLAY_ONLY_DATA_FILES  # noqa: E402

SELF = (ROOT / "research" / "validation" / "holdout.py").resolve()
# 單獨列名放行（每一筆都要有裁示或 [自行裁量] 出處；只放行列出的檔名，不放寬守門本身）
ALLOW = {
    # 先.一一八-2b [自行裁量]：模擬 G 前向紙上追蹤只拿回補檔補官方營收缺月（2024-12～2025-04）當 SUE 分母；判定只看 2027 起報酬
    "research/paper_7_revsurprise_tracker.py": {"revenue_backfill.json"},
}


def hits(text: str) -> list[str]:
    return [n for n in sorted(DISPLAY_ONLY_DATA_FILES) if n in text]


res = []
res.append(("守門能抓到假程式裡的檔名", hits('open("data/revenue_backfill.json")') == ["revenue_backfill.json"]))
bad = []
for p in sorted((ROOT / "research").rglob("*.py")):
    if p.resolve() == SELF or "__pycache__" in p.parts:
        continue
    try:
        h = hits(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        continue
    h = [n for n in h if n not in ALLOW.get(p.relative_to(ROOT).as_posix(), set())]
    if h:
        bad.append(f"{p.relative_to(ROOT)}：{','.join(h)}")
res.append((f"research/ 底下沒有程式引用 App 顯示用回補檔（{len(DISPLAY_ONLY_DATA_FILES)} 個檔名）" + ("" if not bad else "；" + "；".join(bad[:5])), not bad))
# 先.一二五-1（2026-10-21，總司令核准 先.一二三-1 甲案）：stock_detail.json 的 financials.quarters 會帶
# 回補檔衍生的季度（source＝q1_from_backfill／official_cum_minus_backfill，落在 holdout 期間）。
# research/ 裡讀 stock_detail.json 的只准是下列上線評分／稽核／回補工具（都不是回測）；新出現的讀取者一律 FAIL，
# 要放行先確認它不是回測、或已濾掉上面兩種 source，再列名並附出處。
STOCK_DETAIL_READERS_OK = {
    "research/audit_e_pe_diagnosis.py",            # 稽核工具，比對 EPS
    "research/backfill_price_history_gaps.py",     # 補價格缺口，只讀代號清單
    "research/backfill_stock_financials_gap_2025.py",  # App 顯示端回補工具
    "research/build_coverage_dashboard.py",        # 覆蓋率儀表板
    "research/build_stock_financials_history.py",  # App 顯示端回補工具
    "research/generate_scores_future.py",          # 上線評分（App 今日榜單）
    "research/generate_scores_live.py",            # 上線評分
    "research/generate_scores_momentum.py",        # 上線評分
    "research/live_factors.py",                    # 上線評分因子
    "research/run_momentum_future_board_pit_backtest.py",  # 只在註解提到資料形狀，不開檔
    "research/tpex_3insti_client.py",              # 只在說明文字提到
    "research/validation/holdout.py",              # 守門定義本身（DISPLAY_ONLY_DERIVED_SOURCES 說明）
}
res.append(("守門能抓到新的 stock_detail.json 讀取者", "research/x_backtest.py" not in STOCK_DETAIL_READERS_OK))
new_readers = []
for p in sorted((ROOT / "research").rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    rel = p.relative_to(ROOT).as_posix()
    try:
        if "stock_detail.json" in p.read_text(encoding="utf-8", errors="replace") and rel not in STOCK_DETAIL_READERS_OK:
            new_readers.append(rel)
    except OSError:
        continue
res.append(("research/ 沒有新的 stock_detail.json 讀取者（含回補衍生季度，回測不得讀）"
            + ("" if not new_readers else "；" + "；".join(new_readers[:5])), not new_readers))
# 先.一三二-0a（2026-10-23，收件匣 020）：holdout 期間的限定讀取資料夾（模擬 I 252 日回看）只准單獨列名的程式提到。
from validation.holdout import ALLOWED_HOLDOUT_READERS, RESTRICTED_LOOKBACK_DIRS  # noqa: E402
LOOKBACK_DEFINERS = {"research/validation/holdout.py", "scripts/selftest_display_only_files.py"}  # 定義與守門本身
res.append(("限定讀取資料夾的讀取者都在 ALLOWED_HOLDOUT_READERS（單獨列名）",
            all(r in ALLOWED_HOLDOUT_READERS for rs in RESTRICTED_LOOKBACK_DIRS.values() for r in rs)))
res.append(("守門能抓到假程式提到限定資料夾", any(d in 'open("research/data/paper_9_lookback/x.json")' for d in RESTRICTED_LOOKBACK_DIRS)))
lb_bad = []
for base in ("research", "scripts"):
    for p in sorted((ROOT / base).rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in LOOKBACK_DEFINERS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for d, readers in RESTRICTED_LOOKBACK_DIRS.items():
            if d in text and p.name not in readers:
                lb_bad.append(f"{rel}：{d}")
res.append(("holdout 限定讀取資料夾（" + "、".join(RESTRICTED_LOOKBACK_DIRS) + "）只有列名程式提到"
            + ("" if not lb_bad else "；" + "；".join(lb_bad[:5])), not lb_bad))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
nb = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {nb}")
sys.exit(1 if nb else 0)
