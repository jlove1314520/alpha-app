"""稽核二.一：回補 data/stock_detail.json 季報斷層（2025Q1～2026Q1 五季，共754檔）。

背景（根因，見PENDING_QUEUE.md稽核二.一條目與本檔案下方print的診斷）：
1. `.github/scripts/update_stock_financials.py`（每日排程）只打TWSE官方
   `t187ap06_L_ci`/`t187ap07_L_ci`，這兩個端點**只回傳「最新一期」全市場
   快照**，沒有歷史區間查詢參數——它從2026-08-27才開始跑，第一次執行時
   TWSE的「最新一期」已經是2026Q2，所以它從一開始就只會抓到2026Q2，
   抓不到2025Q1~2026Q1這五季（這五季在它開始跑之前就已經「過期」了，
   官方端點不提供回溯）。
2. `research/build_stock_financials_history.py`（2026-08-27一次性回補）
   讀的是research端FinMind歷史parquet本機快取（`research/data/raw/
   TaiwanStockFinancialStatements__{code}__*.parquet`），但**只有2330
   一檔**在2025-08-27之後有人手動測試過抓到`2025-01-01__latest`這個
   快取檔（102列，涵蓋2025Q1~2026Q2六季），其餘2296檔的FinMind快取
   都停在`2010-01-01__2024-12-31`——也就是說「回補歷史」這件事，
   實際上只對一檔股票做過，其餘從未執行。這不是外部限制，是這件事
   還沒有人手動做完整個市場。

本腳本要做的事：對這754檔（外加日後可能變動的名單，動態算）**逐檔**打
FinMind `TaiwanStockFinancialStatements`（損益表）+`TaiwanStockBalanceSheet`
（資產負債表）的`start_date=2025-01-01`區間，寫進`research/data/raw/`
parquet快取（跟build_stock_financials_history.py讀的路徑完全一致），
之後只要重跑`build_stock_financials_history.py`就會merge進
`data/stock_detail.json`。

**為什麼不直接用MOPS官方查詢頁**：2026-09-15稽核（`docs/DATA_SOURCE_MAP.md`
「🔴走不通：MOPS公開查詢頁」段落）已查證`mopsov.twse.com.tw/robots.txt`
對非bingbot的User-Agent一律`Disallow: /`，且總司令2026-09-15已裁示「立刻
停掉四支既有生產程式對mopsov.twse.com.tw的存取，我們已為同一條紅線放棄
ic.tpex、分點資料、驗證碼繞道，自己記錄的紅線不能自己踩」。改用FinMind
是因為：(a) FinMind本身就是把MOPS官方申報資料整理成結構化API的**已授權
第三方服務**（不是繞過驗證/登入牆/機器人封鎖去抓官方網站），(b) 這正是
`build_stock_financials_history.py`已經在用、且已被稽核.二接受的同一個
資料源（一致性），(c) CLAUDE.md「各市場一律使用該市場的原生資料源」一節
容許「FinMind僅作歷史補充」，這正是歷史補充的場景（每日排程主來源仍是
TWSE官方，FinMind只補這五季缺口）。

**為什麼不算holdout污染**：`research/finmind_client.py`的`load_dev()`/
`load_full_history()`holdout cap（VAL_END=2024-12-31）是為了保護「策略
回測」不能用到樣本外資料，這裡的用途是`data/stock_detail.json`——**App
個股頁即時顯示的當前基本面資料**，不是任何策略的回測輸入，這條規則的
保護對象不適用。直接呼叫`finmind_client._fetch()`（內部primitive，一般
研究程式碼不該直接用，這裡是刻意的例外，見finmind_client.py檔頭），
沿用跟`update_stock_financials.py`/`build_stock_financials_history.py`
同樣的定位。

**節流**：`_fetch()`內建跨process共用3秒節流（`data/rate_limit_state.json`）
與428/403斷路器，本腳本不額外加節流，但用`--batch-size`/`--offset`分批，
避免單次執行時間過長（一批200檔=400次請求≈20分鐘，可分批跨cycle續跑，
已抓過的(code,dataset)組合會命中parquet快取秒回，重跑同一批不會重打）。

**2026-09-15 17:16 cycle（cycle_id=20260915-171602）實測踩到的坑，記在這裡
避免下一輪重踩**：
1. 本輪對剩餘634檔（offset 120起）重跑時，在處理到第~150檔時FinMind回
   HTTP 402「Requests reach the upper limit」，`_fetch()`已依既有機制把
   `data/rate_limit_state.json`標記封鎖2小時（`blocked_until`），此後
   `_throttle()`會直接RuntimeError不再發出請求——這是CLAUDE.md「取得方式
   鐵律」要求的行為（額度用完就誠實拒絕，不排隊不重試），**不要在封鎖
   期間重跑這支腳本**，會全部落在`err`分類，浪費時間也不會拿到資料。
   封鎖起點2026-09-15 17:18:54 UTC（=台北01:18:54次日，注意`blocked_at`
   是UTC），解封約在封鎖起點+2小時。下一輪要續跑前，先讀
   `data/rate_limit_state.json`確認`blocked_until`已過。
2. **這次一共只成功回補149檔**（累計120+149=269/754），累計進度可從
   `backfill_stock_financials_gap_2025.log.json`裡`status=="fetched"`的
   code數清點，但**該log.json本身在本輪執行期間被同working directory
   內另一個自走行程（IBKR quotes/hypothesis_queue排程，皆與devqueue共用
   同一個repo目錄，只各自鎖自己的track，不互相排斥檔案系統層級的寫入）
   刪除過一次**——這是本機同時跑好幾條自走軌道（devqueue/marathon/
   hypothesis_queue/ibkr_quotes/shioaji_quotes）共享同一個working
   directory的已知風險，未追蹤（untracked）檔案沒有任何保護，隨時可能被
   另一條軌道的清理動作波及。**因此log.json不可信任為累計進度的唯一
   依據**，真正的累計進度要用`find_gap_codes()`重新掃`data/
   stock_detail.json`現況（已经merge進去的才算數），或直接看parquet
   快取檔案的mtime。
3. 同一個風險也讓已完成但**尚未commit**的`data/stock_detail.json`merge
   結果被外部行程reset回HEAD舊值一次（見PENDING_QUEUE.md稽核二.一條目
   的完整記錄）——**merge完成後要立刻commit，不要拖到這一輪所有子任務
   都做完才一次commit**，未commit的視窗越長，被另一條軌道的git操作波及
   的機率越高。

用法：
    python research/backfill_stock_financials_gap_2025.py --batch-size 200 --offset 0
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import finmind_client  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
LOG_PATH = Path(__file__).parent / "backfill_stock_financials_gap_2025.log.json"

BACKFILL_START = "2025-01-01"

# 2026-09-15（總司令裁示「核准附三條件」）節流/上限/停損常數集中寫在這裡，
# 比照 .github/scripts/news_body_extract.py 的既有慣例（REQ_INTERVAL/
# MAX_PER_RUN/MAX_CONSECUTIVE_FAIL 同款命名），不靠隱含在 finmind_client
# 共用節流狀態裡的行為當唯一防線——這支腳本自己也要能在合理範圍內停手。
MAX_PER_RUN = 200          # 每輪處理上限（income+balance各一次請求=400次/輪，
                           # 跟finmind_client內建3秒節流換算約20分鐘/輪，可分批跨cycle續跑）
MAX_CONSECUTIVE_FAIL = 15  # 連續失敗這麼多檔（income+balance任一失敗都算）就停止本輪，
                           # 不硬跑到底——通常代表額度已被finmind_client的402斷路器攔下，
                           # 繼續跑只會全部落在err、浪費時間也不會拿到資料


def find_gap_codes() -> list[str]:
    """跟scripts/data_audit.py check_e_pe()的e_quarters_gap判定邏輯一致
    （複製,不import——跨repo/跨目錄不import是既有慣例，見其他腳本docstring），
    只取「不連續」（gap）不取「過期」（stale，見腳本檔頭第2點root cause分類，
    stale多半是金融股_bd/_fh/_ins/_mim分類，TWSE _ci端點本來就不涵蓋，
    不是這次回補的目標,是另一個未解決的已知限制）。"""
    payload = json.loads(STOCK_DETAIL_PATH.read_text(encoding="utf-8"))
    stocks = payload.get("stocks", {})
    now = datetime.now(timezone.utc)
    cur_q = (now.year, (now.month - 1) // 3 + 1)
    gap_codes = []
    for code, entry in stocks.items():
        if not code.isdigit():
            continue
        qs = ((entry.get("financials") or {}).get("quarters")) or []
        last4 = qs[-4:]
        if len(last4) < 4:
            continue
        seq = [(q.get("year"), q.get("quarter")) for q in last4]
        y, qq = seq[0]
        expected = []
        try:
            for _ in range(4):
                expected.append((y, qq))
                qq += 1
                if qq > 4:
                    qq, y = 1, y + 1
        except TypeError:
            continue
        last_q = seq[-1]
        try:
            stale = (cur_q[0] * 4 + cur_q[1]) - (last_q[0] * 4 + last_q[1]) > 3
        except TypeError:
            stale = True
        if stale:
            continue
        if expected and seq != expected:
            gap_codes.append(code)
    return sorted(gap_codes)


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"results": {}}


def _save_log(log: dict) -> None:
    log["updated_at"] = datetime.now(timezone.utc).isoformat()
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-run", type=int, default=MAX_PER_RUN,
                    help="本輪處理上限，預設用模組常數 MAX_PER_RUN")
    args = ap.parse_args()

    # 2026-09-15改用find_gap_codes()即時掃描決定這一輪要處理誰，不再用
    # --offset這種「假設上一輪處理了前N筆」的位置式續跑——上一輪log.json
    # 曾被同working directory另一自走行程刪除過一次（見檔頭2026-09-15
    # 17:16 cycle記錄），offset會失真；即時掃描data/stock_detail.json現況
    # 才是「已回補的不重打」的真正保證：已經merge進去、不再是gap的股票，
    # find_gap_codes()自然不會再回傳它。
    codes = find_gap_codes()
    total = len(codes)
    batch = codes[:args.max_per_run]
    print(f"季報斷層(gap)即時掃描結果：{total} 檔仍缺口，本輪處理前 {len(batch)} 檔")

    log = _load_log()
    results = log.setdefault("results", {})
    ok_income = ok_balance = err_count = 0
    consecutive_fail = 0
    processed = 0
    for i, code in enumerate(batch, 1):
        entry = results.setdefault(code, {})
        code_failed = False
        try:
            df = finmind_client._fetch("TaiwanStockFinancialStatements", code, BACKFILL_START, None)
            entry["income_rows"] = int(len(df))
            entry["income_status"] = "fetched"
            ok_income += 1
        except Exception as e:
            entry["income_status"] = f"error: {e}"[:300]
            err_count += 1
            code_failed = True
        try:
            df = finmind_client._fetch("TaiwanStockBalanceSheet", code, BACKFILL_START, None)
            entry["balance_rows"] = int(len(df))
            entry["balance_status"] = "fetched"
            ok_balance += 1
        except Exception as e:
            entry["balance_status"] = f"error: {e}"[:300]
            err_count += 1
            code_failed = True
        processed = i
        consecutive_fail = consecutive_fail + 1 if code_failed else 0
        if i % 10 == 0 or i == len(batch):
            print(f"  進度 {i}/{len(batch)}（{code}）：income_ok={ok_income} balance_ok={ok_balance} err={err_count}")
            _save_log(log)  # 每10檔存一次進度，中斷不會全部遺失
        if consecutive_fail >= MAX_CONSECUTIVE_FAIL:
            print(f"  連續失敗達 {consecutive_fail} 檔（門檻 {MAX_CONSECUTIVE_FAIL}），"
                  f"研判額度已被斷路器攔下，停止本輪，不繼續硬跑")
            break

    _save_log(log)
    print(f"本批完成：income成功 {ok_income}/{processed}、balance成功 {ok_balance}/{processed}、"
          f"錯誤 {err_count} 筆。即時掃描剩餘缺口（含本輪未觸及與未成功的）需下一輪重新"
          f"呼叫 find_gap_codes() 確認，不假設本輪處理的都成功merge。")


if __name__ == "__main__":
    main()
