# -*- coding: utf-8 -*-
"""前瞻選股台帳的回填腳本（2026-08-28新增，B24第一步，骨架/尚未完整實作）。

跟`build_picks_ledger.py`（負責「快照」）分工明確：這支腳本只負責【回填】
——對`data/picks_ledger.json`裡每個快照的每一檔股票，檢查是否到了
T+5/T+20/T+60/T+120交易日，到了就查當時的收盤價+大盤指數，算出報酬率跟
超額報酬填進`returns.t5`(或t20/t60/t120)，**只寫還沒填過的欄位，已經填過
的欄位永遠不再更動**（鐵律：「只能事前快照，嚴禁事後補建」的延伸——回填
本身是被容許的『事後』動作，但同一個(snapshot, T+N)只能被回填一次，寫過
就不能因為之後想「調整」而改動，那樣會失去前瞻驗證的公信力）。

**這輪只搭骨架，尚未完整實作（使用者原話：「設計...骨架，之後每日排程
執行」，可以先設計不用今晚就做完）**——原因：
1. 「T+N交易日」的計算需要一份可靠的「台股交易日曆」（排除週末+國定假日），
   這個repo目前沒有現成的交易日曆資料源（見CLAUDE.md已知地雷：
   `is_tw_trading_window()`目前用星期幾+時間粗略判斷，不是精確日曆）。
   骨架先用「自然日往後數，找price_history.json裡實際存在的下一個交易日」
   這個做法近似（`_trading_days_after()`），比憑空猜測日曆更可靠，但還沒
   跑過真實案例驗證。
2. `data/price_history.json`是90天滾動視窗（見B23的深度/缺口問題）——
   T+120交易日回填時，snapshot當時的進場價已經存在快照本身裡（不受滾動
   視窗影響），但如果backfill腳本要另外查「大盤在T+120那天的收盤」，只要
   backfill當下market_tw.json/price_history.json有那天的資料就行（那時候
   那天已經是「最近」的資料，不受90天視窗限制——不是回頭查很久以前的
   歷史，是查backfill執行當下的「現在」）。
3. 尚未決定「大盤超額報酬」要用什麼基準運算（簡單相減 vs 對數報酬），
   B16/B24 PIT回測那邊已有既有的報酬率計算慣例可以參考統一，這裡先留
   TODO，之後回測骨架成形時一併對齊。

**之後要做的（下一輪或後續輪次）**：
- 實作`_trading_days_after(anchor_date, n)`：从price_history.json任一檔
  流動性夠的股票（如加權指數成分股）的實際交易日序列往後數N個交易日，
  找出對應的日曆日期。
- 實作`_lookup_price_on(code, date)`：查`price_history.json`該股票在指定
  日期的adj_close（或最接近的下一個交易日，資料缺失時的合理退讓）。
- 實作`_lookup_taiex_on(date)`：查`market_tw.json`或另建歷史序列取得大盤
  在指定日期的收盤。
- 掛進`.github/workflows/market.yml`，每日排程執行（在
  `build_picks_ledger.py`快照之後、commit之前，同一個step順序）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "picks_ledger.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"

# T+N交易日視窗名稱 → 交易日數（不是日曆天數）
RETURN_WINDOWS = {"t5": 5, "t20": 20, "t60": 60, "t120": 120}


def _trading_days_after(anchor_date: str, n: int, trading_calendar: list[str]) -> str | None:
    """TODO（骨架，尚未完整驗證）：從一份已知的實際交易日清單（例如某檔
    流動性充足股票在price_history.json裡的date序列，近似當作台股交易日曆）
    裡，找anchor_date之後第n個交易日。anchor_date當天不算，從下一個交易日
    開始數第1天。找不到（超出目前資料涵蓋範圍）就回傳None，呼叫端應該
    跳過、留到之後這個範圍的資料存在了再回填，不能用日曆天數估算頂替。"""
    try:
        idx = trading_calendar.index(anchor_date)
    except ValueError:
        return None
    target_idx = idx + n
    if target_idx >= len(trading_calendar):
        return None  # 還沒到那個交易日，之後資料累積夠了再回填
    return trading_calendar[target_idx]


def main():
    if not LEDGER_PATH.exists():
        print(f"{LEDGER_PATH} 不存在，沒有快照可以回填，結束")
        return
    print("update_picks_ledger_returns.py 目前只是骨架（見模組docstring），"
          "尚未實作實際回填邏輯，這輪不做任何寫入。")
    # TODO：讀LEDGER_PATH，對每個snapshot的每個尚未回填的returns.tN，
    # 用_trading_days_after()+_lookup_price_on()+_lookup_taiex_on()算出
    # return_pct/excess_vs_taiex_pct，只在原本是null時才寫入，寫過的
    # 欄位不再更動。


if __name__ == "__main__":
    main()
