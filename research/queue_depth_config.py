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
