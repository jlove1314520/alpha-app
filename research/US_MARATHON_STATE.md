# US_MARATHON_STATE.md — 美股軌斷點狀態（覆寫式）

**這份檔案只描述美股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `US_LOG.md`；候選判定看 `US_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

**最後更新：2026-08-24T04:05:00+08:00**（馬拉松第十一輪執行後）

**地基狀態：🟡 起步中，PIT資料源方向已確認可行（兩個獨立端點都驗證過，各有各的坑），存活者偏差方向已確認「兩個候選方法都不可靠」。第七輪發現一個重要的方法論教訓：`FRC` 這個下市案例第五輪其實從一開始就查錯了實體，「FDIC接管型下市不走Form 25」假設因此變弱。第十輪發現另一個方法論陷阱：XBRL company facts API 的比較期重複揭露問題；第十一輪去重後發現殘留離群值背後還有兩個獨立成因（pre-XBRL標記缺口、pre-IPO歷史資料，見下方）。** 價格資料（`USStockPrice`）的深度/更新頻率已驗證可用；股票名單（`USStockInfo`）的形狀已摸清但還不能直接拿來建構無偏差宇宙；**SEC EDGAR 申報日期 API 已實測驗證可用（submissions API + company facts API 兩個端點都測過）**（見下方）；**美股存活者偏差：`universe.py` 的價格列存在法、`USStockInfo` 快照增減法，這輪實測後都證實不可靠**（見下方，細節在 `DATA.md`「美股存活者偏差調查」小節）；**5檔已知下市股中，只有 TWTR/SIVB/BBBY 三檔的 CIK 已可信驗證（公司名稱＋申報型態都合理），SBNY 完全查不到候選，FRC 原本的候選被本輪推翻（同名不同實體）且沒找到替代候選**。仍然沒有美股版的 `universe.py`／`adjust.py`／`pit.py`／`factors.py`——**下一輪還是地基工作，還不能開始測因子**。

**已知資訊（避免重複調查）：**
- `USStockPrice`（FinMind）：免費，且**價格已經是還原股價**（`Adj_Close` 欄位，`DATA.md` 里程碑1已驗證），跟台股的還原股價地雷不對稱，美股這邊反而好處理，不需要自組還原邏輯。
- `USStockPrice` 歷史深度／更新頻率（2026-08-23 馬拉松第一輪已驗證，見 `DATA.md`「美股里程碑1」小節、`US_LOG.md`）：AAPL/MSFT 兩檔巨型股回溯到 1990-01-02，逐日更新無漏交易日，欄位 `date, stock_id, Adj_Close, Close, High, Low, Open, Volume`。**只測了兩檔長年掛牌巨型股，中小型股/近年上市股深度未驗證，不能假設全市場都一樣長。**
- `USStockInfo`（2026-08-23 已驗證，見 `DATA.md`）：**這是名單快照，`date` 欄位是 FinMind 抓取這份名單的時間戳，不是股票上市日**（跟 `TaiwanStockInfo` 同款地雷，`universe.py` 已經處理過台股版本，美股要用類似精神但不能照抄邏輯，資料形狀不完全一樣）。289 個快照、18396 檔 distinct stock_id（5470 檔是 ETF）、最新快照（2026-08-22）12429 列可當現存股票+ETF基準。
- **美股存活者偏差（2026-08-23 馬拉松第四輪已實測，見 `DATA.md`「美股存活者偏差調查」小節、`US_LOG.md`、`research/us_survivorship_probe.py`）**：用 5 檔已知下市/出事美股（TWTR、SIVB、SBNY、FRC、BBBY）測了兩個候選方法，**都不可靠**——(a) 台股用的「價格列存在=地面真相」方法：TWTR/SIVB/FRC 三檔完全 EMPTY（資料直接消失，不是保留到下市日），SBNY/BBBY 兩檔的資料時間軸跟已知下市事件對不上（疑似代號重用或原本認知的下市日不準確，這輪沒查證是哪一種）；(b) `USStockInfo` 快照增減法：TWTR 289 個快照裡只出現過 1 次卻實際活躍交易到 2022 年，證明快照本身覆蓋率就不完整，跟下市無關。**結論：不能盲目用「有資料=活著」判斷美股上下市，代號重用（ticker reuse）是美股特有、台股沒有的陷阱，比「完全沒資料」更危險（會沉默地把兩家公司的歷史接成一條假的連續序列）。**
- **SEC EDGAR 公開 JSON API（2026-08-23 馬拉松第三輪已實測驗證，見 `DATA.md`「美股 PIT 資料源調查」小節、`US_LOG.md`、`research/sec_edgar_probe.py`）**：`data.sec.gov/submissions/CIK{cik}.json` 對 AAPL/MSFT/PLTR 三檔都 200 OK，`filingDate`/`reportDate` 欄位確實存在。10-K/10-Q 的 filingDate−reportDate 天數差：AAPL平均33.1天、MSFT平均27.5天、PLTR平均41.5天（範圍34–57天，明顯比兩檔大型股寬——**這是新發現，設計保守預設值時不能只看大型股**）。`www.sec.gov/files/company_tickers.json`（ticker→CIK對照）也驗證可用。歷史回溯用 `filings.files[]` 分頁機制可以拿到（AAPL回溯到1994年），但這輪只確認分頁指標存在，沒有實際抓分頁內容。這是既有資料源清單「美股財報（SEC EDGAR）」的公開文件依據，凍結區`alpha-data/fetch.py`裡如果有類似邏輯，只能參考不能照抄。
- **SEC EDGAR Form 25 下市核實（2026-08-23 馬拉松第五輪已實測，見 `DATA.md`「美股存活者偏差調查（續）」小節、`US_LOG.md`、`research/sec_edgar_delisting_probe.py`）**：`TWTR`（25-NSE 2022-10-28）、`SIVB`（25-NSE 2023-05-02，另有 2017-2018 一組較早的申報，疑似不同證券類別下市，未分辨）確認為真下市，跟第四輪憑記憶的日期大致吻合。`BBBY` 現行 `company_tickers.json` 把 ticker 指向 CIK 1130713（公司名「NEIGHBORHOOD INTELLIGENCE, INC.」，不是 Bed Bath & Beyond）——**獨立確認代號重用是真的，且連 SEC 自己現行的 ticker 對照表都會被重用代號誤導，之後任何用「ticker→CIK/身分」單一對照表的設計都要考慮這個陷阱**。
- **`SBNY` 正確 CIK 仍未查到（2026-08-24 馬拉松第六輪已嘗試，見 `DATA.md`「美股存活者偏差調查（再續）」小節、`US_LOG.md`）**：排除了兩個錯誤候選（1288776=Google、1288784=無關的 CO 小型銀行控股公司「Signature Bank Corp」），用 `browse-edgar` 公司名稱搜尋跟 `efts.sec.gov` 全文檢索（含逐頁掃完 2023-03-01～2023-06-30 全部 200 筆 Form 25-NSE 申報實體）都找不到任何名稱含「Signature」的申報實體。**發現：`browse-edgar` 的公司名稱搜尋在沒有精確符合時會自動跳到字母排序最近的單一公司（不是回傳候選清單），之後要查公司名稱優先用 `efts.sec.gov` 全文檢索的 entity 聚合，不要用 `browse-edgar` 名稱搜尋做探索式查詢。**`FALLBACK_CIK["SBNY"]` 是 `None`，腳本註解標記「已知錯誤待查，不要用猜的」。
- **`FRC` 的原本候選 CIK（1132979）第七輪已推翻——同名不同實體（2026-08-24 馬拉松第七輪已實測，見 `DATA.md`「美股存活者偏差調查（再再續）」小節、`US_LOG.md`、`research/sec_edgar_frc_cik_probe.py`）**：`filings.files[]` 確認是空陣列，`filings.recent`（43筆）就是這個 CIK 的完整申報記錄，不是視窗截斷——**但這 43 筆全部是 `SC 13G`／`SC 13G/A`＋1筆`40-6B/A`，完全沒有 10-K／10-Q／8-K**，不合理是一家 NYSE 掛牌十幾年、資產破 2000 億美元銀行控股公司的申報型態，**第五輪只核對公司名稱、沒核對申報型態，很可能從一開始就查錯了 CIK**（推測 1132979 是 FRC 旗下信託/財富管理部門以機構投資人身分揭露持股用的 CIK，不是 FRC 自己申報年報用的公司 CIK）。三管齊下找正確 CIK 都失敗：`browse-edgar` 名稱搜尋跳到 CIK 770975「FIRST REPUBLIC BANCORP INC」但那是**另一家舊公司**（申報止於2008，本身有一筆真的2005年Form 25，是早於2010年那次真正IPO的另一實體——第三個踩到「同名不同實體」陷阱，前兩個是BBBY／SBNY）；`efts.sec.gov` 全文檢索限定Form 25-NSE＋2023-04-01～2023-08-31（FRC接管日窗口）沒找到任何相關實體；`entityName=First Republic Bank`＋Form 10-K 只找到2筆不相干的抵押貸款證券化信託。**2010-2023年那個真正在NYSE掛牌的FRC對應的正確CIK，仍未找到，這是開放問題。**`FALLBACK_CIK["FRC"]` 已改成 `None`，腳本註解已同步更新標記「已知很可能是錯誤實體，不要用猜的」。
- **「FDIC 接管型下市不走標準 Form 25」假設：第七輪後應視為變弱，不是變強**：第六輪原本把 `SBNY`（查不到候選CIK）＋`FRC`（查到候選但查不到Form 25）當成兩個獨立支持證據。第七輪發現 `FRC` 的候選CIK從一開始就是錯誤實體，所以「FRC真的查不到Form 25」這個結論從來沒有被真正驗證過——只驗證了「一個同名但不相干的13G申報實體查不到Form 25」。**目前這個假設只剩 `SBNY` 一個懸而未決的資料點（連候選CIK都沒有，無法重新查證），不再是兩個獨立確認。**如果要繼續驗證，需要先找到正確的 FRC CIK 才能真正檢驗這個假設，或改用 SEC EDGAR 以外的資料源（FDIC BankFind Suite、Nasdaq官方停牌公告）。
- 美股成本模型：完全沒有（`validation/costs.py` 目前只有台股手續費/證交稅邏輯）。
- **XBRL company facts API（`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`）已實測驗證，見 `DATA.md`「美股 PIT 資料源調查（續）」小節、`US_LOG.md` 第十輪、`research/sec_edgar_xbrl_facts_probe.py`。可用，但發現重要陷阱：這是「每個資料點」層級不是「每次申報」層級，同一財報期間（`end`）會因為比較期揭露在多次申報裡重複出現（AAPL 74個`end`日期裡71個/96%被超過一次申報引用），天真算 `filed-end` 會嚴重高估PIT gap（實測出現772/1034天離群值）。另外發現XBRL concept名稱隨時間/公司不穩定（`Revenues`只回溯到2016年，`EarningsPerShareDiluted`回溯到2007年，PLTR甚至沒有`Revenues`這個concept）。
- **修正後（取最小filed分組）的gap統計已實測，見 `DATA.md`「美股 PIT 資料源調查（再續）」小節、`US_LOG.md` 第十一輪、`research/sec_edgar_xbrl_facts_dedup_probe.py`（第十輪的原始探測腳本 `sec_edgar_xbrl_facts_probe.py` 保留不動，這是新增的獨立腳本）。**去重後中位數大幅改善且貼近submissions API水準（AAPL EPS median=32天、MSFT=28天、PLTR=40天，vs. submissions API第三輪測到的AAPL平均33.1天/MSFT平均27.5天），證明去重邏輯本身是對的**，但max幾乎沒變（AAPL 759天、MSFT 1034天）——**去重是必要但不充分的修正，還有兩類無法用去重消除的殘留離群值**：(1) AAPL/MSFT離群值全部集中在`end`落在2007–2009年之間，追查發現是**XBRL強制標記生效前**的財報期間，原始申報沒有被XBRL標記，min(filed)撿到的是後來（例如2010年）10-K「五年精選財務數據」表格重新揭露的日期，不是真正的原始揭露日——**這是資料源結構性缺口，不是去重邏輯能解決的問題，未來設計美股版`pit.py`要把`end`早於公司XBRL強制生效門檻（概略~2009年中，確切日期依申報人規模分級未查證）的資料點標記為「PIT gap不可信」**；(2) PLTR離群值全部落在其2020年9月IPO之前的期間，這是**真實的結構性事實（上市前無法對外申報），不是資料陷阱**，回測時只要確保上市前不把該公司納入宇宙即可，理論上不需要額外修正邏輯，但這輪沒有驗證`universe.py`延伸到美股後是否真的自然處理這點。

**下一輪建議工作單位（只做其中一項，不要一次全做）：**
1. **找 2010-2023 年真正掛牌 NYSE:FRC 的正確 CIK**：SEC EDGAR 內部已窮盡三種查法都失敗（見上方），下一步可能要跳出 SEC EDGAR——候選來源：FDIC BankFind Suite 公開資料庫、Nasdaq 官方停牌/下市公告、或查 FRC 2023 年之前歷年公開新聞稿/財報裡引用的 CIK/SEC 檔案編號。第一次嘗試新來源前要先確認公開可讀、不需登入（符合協定第3節規則）。
2. **驗證「FDIC 接管型下市不走 Form 25」假設，或改用非 SEC 資料源查 `SBNY` 下市日**：跟上面第1項可能殊途同歸，但這項專注在 SBNY（連候選CIK都沒有，可能需要完全不同的查法起點）。
3. ~~重算 XBRL company facts 的修正後 PIT gap~~ ✅ 第十一輪（2026-08-24凌晨）已完成，新寫 `sec_edgar_xbrl_facts_dedup_probe.py`。去重後中位數大幅改善（AAPL/MSFT/PLTR分別32/28/40天，貼近submissions API水準），但發現兩類無法用去重消除的殘留離群值：pre-XBRL標記缺口（AAPL/MSFT，`end`落在2007–2009年）、pre-IPO歷史資料（PLTR，`end`早於2020年9月上市）。完整見 `DATA.md`「美股 PIT 資料源調查（再續）」小節、`US_LOG.md` 本輪記錄。**還沒查`EarningsPerShareDiluted`以外的concept是否有同樣問題，也還沒查各公司確切的XBRL強制標記生效日期**，留給下一輪視優先序決定要不要接。
4. 中小型股/近期上市股的 `USStockPrice` 歷史深度抽測（本輪只測了 AAPL/MSFT 兩檔巨型股，不能假設全市場都一樣深）。
5. 把 `sec_edgar_probe.py` 的邏輯正式包裝成一個可重用的 fetch 函式，目前只是探測腳本，還不是可以被其他程式呼叫的模組。

**Holdout 狀態：✅ 未被使用**（跟主線共用同一套機制）。

---

## 下一步

見上方「下一輪建議工作單位」，一次只做一項。
