"""單一事實來源：佇列深度下限與補件目標（2026-09-20總司令裁示【Q4前視
與#23無法重現】四）。

**背景**：`CLAUDE.md`（規則本身）、`scripts/dev_queue_runner.py`（
DevQueue自走軌道的動態prompt生成）、`research/MARATHON_CONTINUATION_
PROMPT.txt`／`research/HYPOTHESIS_QUEUE_CONTINUATION_PROMPT.txt`
（marathon/hypothesis_queue兩個自走軌道讀取的靜態prompt檔）過去各自
用文字硬寫「門檻12、補到20」這兩個數字，2026-09-19總司令把門檻從5
改成12時，只有部分位置同步更新，另外兩份`CONTINUATION_PROMPT.txt`
停留在舊版「門檻5」整整五輪都沒被發現——這正是「規則寫在CLAUDE.md，
提示詞檔是另一份拷貝，兩者會不同步」的具體案例。

**往後任何地方要用到這兩個數字，一律從這裡`import`，不得再各自硬寫
字面值**：
- `scripts/dev_queue_runner.py`的動態prompt生成已改用這裡的常數。
- 兩份`CONTINUATION_PROMPT.txt`是靜態文字檔，無法在「被外部排程讀取
  的當下」動態import——改用`research/sync_continuation_prompts.py`
  在這裡的常數改變時重新產生，把「三處手動同步」降成「改一個常數＋
  跑一支腳本」。
- `scripts/audit_preflight.py`新增稽核比對：定期掃描上述檔案裡實際
  寫的數字，跟這裡的常數比對，不一致就alert——這是最後一道防線，
  就算有人忘記跑`sync_continuation_prompts.py`，稽核也會抓到。
"""

MIN_QUEUE_DEPTH = 12  # `- [ ]`項目數低於這個門檻就要補件
TARGET_QUEUE_DEPTH = 20  # 補件時一次補到這個數量

# 2026-09-23總司令裁示【稽核解封＋S2對等比較＋凍結regime家族】凍結.一：
# 從STRATEGY_GRAVEYARD.md抽取補件時，不得來自「已累積>=5次FAIL的機制
# 家族」——理由：每多一筆同家族試驗都墊高全專案的多重比較(Bonferroni)
# 門檻，一個已經證明系統性不work的家族不該繼續消耗試驗預算。
# 解凍條件：只有總司令另行裁示才能解凍，執行者不得自行判斷「這次應該
# 不一樣」就補入。
FROZEN_MECHANISM_FAMILIES = {
    "regime_擇時": (
        "regime/擇時降曝險家族：7次覆蓋層(binary趨勢濾網#243/#244、已實現"
        "波動度#247、回撤斷路器#246等)+E-c移動停損/E-d MA200(#359/#360)+"
        "cbi/vix/hy等macro regime訊號#76-#81+常備.2~5，全數FAIL。"
        "常備.6/常備.7(DGBAS總經regime)已於本次裁示同步標記凍結，"
        "不計入補件來源。"
    ),
}

