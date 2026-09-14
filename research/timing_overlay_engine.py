"""Cybex.引擎：三個 on-window 執行時機改動（2026-09-15 開發佇列自走輪）。

`PENDING_QUEUE.md`【2026-09-07 Cowork 更正一】原話：「另外補測三個 on-window
引擎改動（Cybex 三個都通過，成本極低）：進場延遲確認、出場延遲確認、總開關
重新開啟確認期。」——原始 Cybex（加密貨幣）程式碼與確切參數不在本機可查範圍
（`C:\\Users\\user\\cybex_knowledge_export\\` 已查過，只有移植手冊摘要沒有這三個
機制的原始程式碼），依「拿判斷方法，不拿參數」的移植原則（`CLAUDE.md`七之三
開頭），本檔重新設計一套語意清楚、可獨立驗證的版本，不假裝還原 Cybex 原始數字。

**設計（把連續曝險轉成有「總開關」狀態機的版本，三個機制合一，可各自關閉）**：
1. 用固定門檔 `threshold`（預設 0.5，percentile-based exposure 的自然中點，
   不依資料調）把逐日連續曝險二值化成「原始狀態」on/off。
2. **進場延遲確認 `entry_delay`**：原始狀態要連續 N 天都是 on，才真的把開關
   切到 on（切換前維持前一個確認狀態）。
3. **出場延遲確認 `exit_delay`**：同理，原始狀態要連續 N 天都是 off 才切到
   off。
4. **總開關重新開啟確認期 `reopen_cooldown`**：開關一旦被切到 off，之後
   `reopen_cooldown` 個交易日內，無論原始狀態怎麼變，都強制鎖在 off，冷卻期
   過了才重新允許依 1-3 的規則切回 on。

輸出的「確認後曝險」＝開關 on 時用當天原始連續曝險值、off 時＝0（開關本身
二值化，但曝險力道保留原始連續值，不是把整個訊號都二值化）。

**gate 9（absorbing state 檢查）自動滿足**：`reopen_cooldown` 是固定天數倒數，
不依賴策略績效或任何外部條件，倒數到 0 必定解除，不存在「永遠不解除」的
風險——不需要另外逐筆稽核觸發/解除事件（結構上不可能卡死），但下面
`_self_test()` 仍印出一段模擬序列驗證冷卻期精確地在第 N 天解除。
"""
from __future__ import annotations

import numpy as np

DEFAULT_THRESHOLD = 0.5
DEFAULT_ENTRY_DELAY = 3
DEFAULT_EXIT_DELAY = 3
DEFAULT_REOPEN_COOLDOWN = 5


def apply_confirmed_switch(
    raw_exposure: np.ndarray,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    entry_delay: int = DEFAULT_ENTRY_DELAY,
    exit_delay: int = DEFAULT_EXIT_DELAY,
    reopen_cooldown: int = DEFAULT_REOPEN_COOLDOWN,
) -> np.ndarray:
    """把逐日連續曝險序列轉成「有進場/出場延遲確認＋重開冷卻期」的版本。

    `raw_exposure`：長度 n 的 1-D array，值域預期在 [0,1]（clip 過的百分位曝險），
    但函式本身不假設值域，只用 `threshold` 二值化。
    回傳同長度的 array：開關 off 時為 0.0，on 時原樣輸出 `raw_exposure[t]`。
    """
    raw_exposure = np.asarray(raw_exposure, dtype=float)
    n = len(raw_exposure)
    out = np.zeros(n, dtype=float)
    if n == 0:
        return out

    raw_state = (raw_exposure >= threshold).astype(int)
    state = int(raw_state[0])
    streak_dir: int | None = None
    streak_len = 0
    cooldown_remaining = 0

    for t in range(n):
        rs = int(raw_state[t])
        if rs == state:
            streak_dir = None
            streak_len = 0
        else:
            if streak_dir == rs:
                streak_len += 1
            else:
                streak_dir = rs
                streak_len = 1
            needed = entry_delay if rs == 1 else exit_delay
            if streak_len >= needed:
                if rs == 1 and cooldown_remaining > 0:
                    pass  # 冷卻期內禁止重開，已確認的進場訊號先擱置
                else:
                    old_state = state
                    state = rs
                    streak_dir = None
                    streak_len = 0
                    if old_state == 1 and state == 0:
                        cooldown_remaining = reopen_cooldown

        if cooldown_remaining > 0:
            cooldown_remaining -= 1

        out[t] = raw_exposure[t] if state == 1 else 0.0

    return out


SELECTION_SPEC_ENGINE_PARAMS = (
    "事前綁定（2026-09-15 開發佇列自走輪，Cybex.引擎）：threshold=0.5、"
    "entry_delay=3、exit_delay=3、reopen_cooldown=5（交易日）。三個數字是"
    "PENDING_QUEUE.md原話「成本極低」語境下的保守小值，不是掃描訊號表現後"
    "挑出的最佳點——本檔案本身不對這三個參數做任何網格搜尋。"
)


def _self_test() -> int:
    failures = []

    # 1) 全程on：輸出應等於原始曝險（開關從未關閉）。
    always_on = np.ones(10) * 0.8
    out = apply_confirmed_switch(always_on, entry_delay=3, exit_delay=3, reopen_cooldown=5)
    if not np.allclose(out, always_on):
        failures.append("全程on應原樣輸出")

    # 2) 全程off：輸出應全為0。
    always_off = np.zeros(10)
    out = apply_confirmed_switch(always_off, entry_delay=3, exit_delay=3, reopen_cooldown=5)
    if not np.allclose(out, 0.0):
        failures.append("全程off應全為0")

    # 3) 單日雜訊不該觸發切換（entry_delay=3時，只出現1天on訊號應被忽略）。
    noisy = np.array([0.0, 0.0, 0.9, 0.0, 0.0, 0.0])
    out = apply_confirmed_switch(noisy, entry_delay=3, exit_delay=3, reopen_cooldown=5)
    if not np.allclose(out, 0.0):
        failures.append(f"單日雜訊不該觸發進場確認，實際輸出={out}")

    # 4) 連續on訊號要滿entry_delay=3天才觸發切換：訊號從index2開始連續on，
    #    第3個連續on日(index4)當天觸發，同一天輸出即改用新狀態。
    seq = np.array([0.0, 0.0, 0.7, 0.7, 0.7, 0.7])
    out = apply_confirmed_switch(seq, entry_delay=3, exit_delay=3, reopen_cooldown=5)
    expected = np.array([0.0, 0.0, 0.0, 0.0, 0.7, 0.7])
    if not np.allclose(out, expected):
        failures.append(f"連續on訊號應在第3個確認日觸發切換，期望={expected}，實際={out}")

    # 5) 重開冷卻期：關閉後5天內即使原始訊號連續on，開關也必須維持off，
    #    冷卻期倒數期間on訊號的確認天數仍會持續累計（不會被冷卻期歸零），
    #    所以冷卻期一結束、只要當時累計天數已達entry_delay就立刻重開——
    #    這裡刻意設計成「冷卻期內on訊號幾乎不中斷」的情境，驗證重開時間點
    #    精確等於冷卻期結束（index7觸發關閉+reopen_cooldown=5 -> index12重開），
    #    而不是冷卻期又疊加一次entry_delay。
    raw = np.concatenate([
        np.full(5, 0.9),   # t0-4 on
        np.full(3, 0.1),   # t5-7 off訊號(第7天觸發關閉，同時啟動5天冷卻)
        np.full(10, 0.9),  # t8-17 on訊號，冷卻期t7-11鎖住，t12冷卻期結束立刻重開
    ])
    out = apply_confirmed_switch(raw, entry_delay=3, exit_delay=3, reopen_cooldown=5)
    off_state = np.isclose(out, 0.0)
    flip_off_index, reopen_index = 7, 12  # 觸發關閉的index、重開的index
    ok = (
        not off_state[:flip_off_index].any()
        and off_state[flip_off_index:reopen_index].all()
        and not off_state[reopen_index:].any()
    )
    if not ok:
        failures.append(
            f"重開冷卻期時序不符：off_state={off_state.astype(int).tolist()}，"
            f"期望index<{flip_off_index}全部on、index[{flip_off_index},{reopen_index})全部off、"
            f"index>={reopen_index}全部on"
        )

    if failures:
        print("=== timing_overlay_engine 自測失敗 ===")
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("=== timing_overlay_engine 自測全過（5項）===")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
