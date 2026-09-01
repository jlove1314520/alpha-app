# HYPOTHESIS_QUEUE_PROTOCOL.md — 假設佇列自動排程操作規則

**你是誰、為什麼在讀這份檔案：** 你是被 Windows 工作排程器（`AlphaHypothesisQueue`
任務）喚醒一次的 Claude Code headless 執行個體（`claude -p`，無人在場、無對話
記憶）。你不記得任何一輪之前發生過什麼——你唯一知道的就是這個 repo 現在的檔案
內容。**這份協定文件本身就是你的記憶。** 讀它、照做、離開。

**這條軌道存在的理由（2026-09-01 新增）**：`HYPOTHESIS_QUEUE.md` 佇列
（Weinstein→CTA→PEAD→carry→…）原本完全沒有自動化，只靠互動 session 手動接手，
結果 Weinstein 結案後空窗約 68 小時沒人接續（後來靠一次背景 fork 補上 CTA/PEAD
兩條，都 FAIL）。這條排程軌道就是為了終結「無人接手就停」——跟同機器上的
`AlphaMarathon`（TW/US/FUT 三軌）是完全獨立的排程，**用獨立的具名鎖，不要跟
三軌互相等待或共用鎖檔，兩者互不阻塞**。

---

## 0. 第一步：永遠先做這三件事

1. **讀 `C:\alpha\CLAUDE.md`（專案根目錄）跟 `research/CONSTITUTION.md`**——凍結區
   規則（`alpha-data\alpha.db`／`fetch.py`／`parsers.py`／`config.py` 絕對不能碰）、
   驗證紀律鐵律。這些規則不會因為你是無人值守的執行個體就失效，反而更要嚴格
   遵守，因為沒有人在旁邊即時發現你做錯事。
2. **`git pull` + `git status` 確認乾淨**：如果發現不是你這輪產生的殘留變更
   （例如三軌排程器或 GitHub Actions 留下的），**記錄下來、不觸碰、不納入你的
   commit**——這條 repo 同時有好幾個自動化來源在寫，誤觸別人的東西比什麼都不做
   更糟。
3. **嘗試取得具名鎖檔**：`cd C:\alpha\alpha-app\research && python marathon_lock.py acquire --name hypothesis_queue`。
   - 回傳 exit code 0（印出 `LOCK_ACQUIRED`）→ 繼續下面的步驟。
   - 回傳非 0（印出 `LOCK_HELD by <pid> since <timestamp>`）→ **上一輪還在跑或
     卡住了，不要並行執行**。什麼都不做，直接結束這一輪（這是正常、健康的行為，
     不是錯誤，不需要記錄到任何 log）。
   - 鎖檔會自動判斷「陳舊」（>25 分鐘沒更新）並允許接手，細節見 `marathon_lock.py`
     docstring。如果這次 `acquire()` 的輸出是 `LOCK_STALE`（不是乾淨的
     `LOCK_ACQUIRED`）：記下這件事，這輪結束時寫心跳要順便註明「上一輪疑似失敗
     （陳舊鎖檔被回收）」。

**做完這一輪所有事之後，無論成功或失敗，最後一定要**：
`python marathon_lock.py release --name hypothesis_queue`。**用 try/finally 的
精神做這件事**——中途任何一步出錯，還是要想辦法釋放鎖，不要卡死接下來所有輪次。

---

## 1. 挑下一條未結案的假設

讀 `research/HYPOTHESIS_QUEUE.md`「排隊順序總結」章節，**依那個順序**找第一條
狀態不是「已結案（PASS/FAIL）」的假設——不得跳著挑、不得因為某條看起來更有趣
就插隊。同時檢查每個條目自己的「狀態」欄位是否已寫「已結案」，兩處對得上才算
真的結案（曾經發生過條目本身寫了結案、但「排隊順序總結」或第100行附近的舊提示
字沒同步更新的情況——你如果看到這種不一致，**先把不一致修正掉**，再往下決定
挑哪一條，不要被過時的提示字誤導）。

**如果佇列裡已經沒有未結案的假設（全部 PASS 或全部 FAIL）**：不要空轉等待，也
不要不做事就收工。依 `C:\alpha\alpha-app\CLAUDE.md` 最高投資原則，回顧目前已經
死掉的假設有沒有共同模式（**寫這份文件時，Weinstein/CTA/PEAD 三條全部死於
「表面總報酬漂亮，拆解後主要是 beta 曝險、alpha 不顯著」這個共同模式**——這三條
全部是「選股票/選標的」型的純多頭假設，缺一個「什麼時候該降曝險」的機制，正是
`CLAUDE.md`「regime 閘門是強制 overlay」原則要求的方向），設計一條**經濟機制上
真正不同**的新假設軸（不是同一個死掉機制換皮），優先方向是 regime/擇時型。
比照 `HYPOTHESIS_QUEUE.md` 既有條目格式（經濟理由 + 具體假設定義 + 已知相關
背景 + 狀態）寫進佇列，這輪工作單位到此為止，下一輪從新加的這條開始跑第 1 關。

---

## 2. 執行方式：延續既有腳本，或先搭地基

- **如果這條假設已經有可重跑的腳本**（像 `cta_momentum_12m.py`／
  `pead_portfolio_v1.py` 那樣，前一輪已經寫過、只是還沒走完全部關卡）：讀懂
  既有程式碼跟目前跑到哪一關，接續往下跑，不要重寫一份新的。
- **如果完全沒開始過**（例如 carry 需要全新的 `TaiwanStockDividend` 資料工程、
  目前完全沒有對應腳本）：這一輪先把地基做好——資料源接上 + 第1關 sanity——
  不用強求一次做完全部 9 關。**跟三軌馬拉松同一個精神：一輪只做一個有界工作
  單位，做完就收工讓下一次觸發接續，不要在單次無人值守呼叫裡硬做到天荒地老**
  （`--max-budget-usd` 是預算煞車，但流程設計上本來就該分批）。

**GATE_SEQUENCE（完整援用 `HYPOTHESIS_QUEUE.md` 最上面的定義，不得跳關）**：
1. sanity → 2. 隨機控制組（≥100 draws）→ 3. 參數密集高原 → 4. 成本/稅/滑價
敏感度(1x/2x/3x) → 5. leave-one-out → 6. 逐年一致性≥5/6 → 7. 樣本外
（train/val）→ 8. 前向paper → 9. 下檔保護證明（`CLAUDE.md` 最高投資原則額外
要求，凌駕以上關卡）。

**快殺標準**（只能用便宜且決定性的證據，禁止「直覺沒肉」判死）：結構性不可能、
資料不可及（查證過真的沒有免費/合規來源）、觀測層級就無訊號（單測便宜關卡
percentile 遠低於門檻）、已被控制組拆穿之偽影家族換皮——完整定義見
`HYPOTHESIS_QUEUE.md`。

**判定標準要跟既有已結案案例同一把尺**（`portfolio_multifactor_v2`／
`weinstein_stage2_v2`／`cta_momentum_12m`／`pead_portfolio_v1` 都用過）：隨機
控制組 percentile 表面過關不夠，**alpha 顯著性（p 值）+ beta 拆解**才是最終
判準——總報酬贏買進持有、但拆解後主要是 beta 曝險、alpha 不顯著，一樣判 FAIL，
不能只看表面數字。

**資料源禮儀**：批次抓取沿用 `fetch.py` 既有的節流/重試/斷路器模式，不要重新
發明；429/403 要有 backoff 跟停損，避免撞到 TWSE/FinMind 封鎖（`CLAUDE.md`
已知地雷章節有記錄這些坑）。

**determinism 前置檢查**：如果這條假設可能受快取/隨機種子影響，先確認可重現
（借用 `determinism_self_test.py` 的精神），不要在不穩定的地基上判定 PASS/FAIL。

**絕對不碰 holdout**：任何資料抓取都必須經過既有框架的 `VAL_END` 截斷路徑。
每一輪收工前確認 `is_holdout_consumed()` 仍是 `False`。

---

## 3. 每輪結束前的檢查清單

1. `is_holdout_consumed()` 是 `False`。
2. **心跳（硬性步驟，不能省略）**：在 `research/MARATHON_LOG.md` **最上面**
   （header 說明文字之後、第一筆既有條目的正上方——插進去，不是接在其他條目
   下面，這份檔案宣稱「最新的寫最上面」就要真的做到）插入一筆新的
   `## <這輪實際的日期時間，用系統時間，不要憑印象> — <這輪做了什麼一句話> — <結果/判定一句話>`。
   **不管這輪做了什麼（就算只是確認佇列已空、新增一條假設），都要留這一筆**。
   如果距離上一筆心跳超過約 30 分鐘還沒做完一整關，也要先寫一行「仍在跑X關、
   預估還要多久」，不能靜默。
3. 這條假設有新判定的話（PASS/FAIL/CHEAP_PASS/EXPERIMENTAL），同步更新：
   - `research/HYPOTHESIS_QUEUE.md` 該條目的「狀態」欄，**以及**「排隊順序
     總結」章節跟任何舊的「佇列狀態：接續#N」提示字——這些地方沒同步更新
     就等於留了地雷給下一輪誤判。
   - `research/TRIALS_LEDGER.md` 新增一列。
   - FAIL → `research/STRATEGY_GRAVEYARD.md`（誠實記具體死因 + 明確寫「不
     泛化成XXX沒用」聲明，跟 CTA/PEAD 兩則的寫法同一個標準）。
   - PASS → 進監控台：跑 `python research/generate_strategies_json.py`
     重新產生 `data/strategies.json`，不要手改 JSON。
4. **三個停下條件**（跟三軌馬拉松/CTA-PEAD 這次完全一樣的定義）：
   (a) 要不要把隨機控制組 draws 數拉到 1000、(b) 要不要投入 survivorship-free
   全宇宙、(c) 任何不可逆操作/花錢的動作。遇到任一種：把問題完整寫進
   `MARATHON_LOG.md` + `HYPOTHESIS_QUEUE.md` 對應條目，commit+push，然後這次
   呼叫正常收工（不空等——下次排程觸發是全新無記憶的 instance，屆時使用者
   如果已經回應就能接著做，沒回應就繼續停在同一個問題上，不會重複問）。
5. `git status` 確認要 commit 的檔案清單合理（不要帶到別的 session/workflow
   留下的殘留變更）。
6. `git add`（限定檔案）→ `git commit`（繁體中文，簡短說明這輪做了什麼）→
   `git fetch origin main` → `git rebase origin/main`（這個 repo 還有其他
   自動化來源在推 main，push 前一定要 rebase 降低被拒機率，衝突就
   `git rebase --abort` 放棄這次推送並在心跳寫「commit 完但 push 失敗」，
   不要用 `--force`）→ `git push`。push 失敗可以重試幾次，短暫等待，不要
   無限重試。
7. `python marathon_lock.py release --name hypothesis_queue`。
8. 結束。**不要在這一輪結束後又開始下一個工作單位**——下一次排程觸發自然會
   被喚醒接續。

---

## 4. 這份文件本身怎麼維護

跟 `MARATHON_PROTOCOL.md` 同一個精神：如果你在某一輪發現這份協定有漏洞、講得
不夠清楚、或有更好的做法，可以直接編輯這份文件本身，但要在編輯處註明日期跟
理由，不要悄悄改掉別人依賴的行為。
