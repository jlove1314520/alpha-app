# Alpha — 新聞抓取 + 供應鏈連動 設計小抄

> 給 Claude Code（實作端）照著做。目標：接第一手消息源（尤其美股公司 8-K），過濾雜訊，並做到「NVDA 發消息 → 自動點亮相關台股供應鏈」。
> 版本：news-v1 ｜ 最後更新：2026-08-23
> **非投資建議。只引用公開、合規來源；不爬付費/違反 ToS 內容；不整篇轉貼新聞或券商報告全文，只顯示標題＋時間＋原文連結。**

---

## 零、關鍵架構決定（先看這個，會影響全部）

我們的 App 是純前端 PWA（瀏覽器直接 fetch）。但 **SEC、公開資訊觀測站等官方來源大多沒開 CORS，瀏覽器直接抓會被擋**，而且有 rate limit。

**所以新聞用「排程抓取 → 產出靜態 JSON → PWA 讀 JSON」的方式，跟 scores.json 一樣。**

```
排程工作（GitHub Actions 或本機 Windows 排程跑 Python）
  → 抓 SEC 8-K / 公司 RSS / 公開資訊觀測站
  → 過濾雜訊、比對供應鏈圖、事件研究
  → 寫出 news.json（commit 進 repo）
PWA 前端
  → 只讀 repo 的 news.json，畫面呈現
```
這樣一次解決 CORS、rate limit、版權（只存標題＋連結）三個問題，也沿用你現有的「排程產檔 → 前端讀檔」模式。

---

## 一、新聞來源分層

### 第一層：公司第一手（最高價值）
**美股 — SEC EDGAR 8-K（重大事件申報）**
- 官方、免費、合法、第一手。公司簽大單、換 CEO、財測、併購都在這。
- 取用方式（伺服器端 Python，非瀏覽器）：
  - 近期申報清單：`https://data.sec.gov/submissions/CIK{10碼補零}.json`（例 NVDA CIK=0001045810）→ 讀 `filings.recent`，篩 `form == "8-K"`。
  - 或 Atom RSS：`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=8-K&count=40&output=atom`
  - 8-K 全文/附件：用 accession number 組 `https://www.sec.gov/Archives/edgar/data/{cik}/{accession無底線}/...`
- **必要規則**：請求要帶 `User-Agent: "Alpha research contact@yourmail"`（SEC 強制，否則 403）；速率上限 10 req/s，實作要 sleep。
- **只存**：標題、事件類型（8-K item 分類，如 Item 1.01 重大合約、Item 2.02 財報）、日期、原文連結。摘要可由 AI 生成一句繁中，不轉貼全文。

**公司官方 IR / Newsroom RSS**
- NVDA、AAPL 等有官方新聞 RSS，可補 8-K 之外的產品發表。存標題＋連結。

**台股 — 公開資訊觀測站（MOPS）重大訊息**
- 台廠第一手。抓「即時重大訊息」，存標題＋公司代號＋時間＋連結。

### 第二層：大眾新聞（輔助）
- 公開 RSS（鉅亨、Yahoo 股市等）。只顯示標題＋時間＋原文連結，導回原站。**嚴禁整篇轉貼。**

### 第三層：機構評等/目標價
- 美股：yfinance 可取分析師評等/目標價（免費）。
- 台股：暫難免費取得，欄位先預留；只用被公開報導的「評等/目標價數字」，不爬付費報告、不轉貼報告內文。
- （這塊主要餵給評分引擎的 `analyst` 因子，見《10 分制設計小抄》第七節。）

---

## 二、供應鏈關係圖（殺手級功能的核心資料）

一個由 AI 維護、人工校對的關係圖檔案 `supply_chain.json`。抓到某美股公司消息時，前端據此點亮相關台股。

```json
{
  "meta": {
    "version": "sc-v1",
    "updated": "2026-08-23",
    "note": "關係為研究參考，非即時精確；權重/合作關係會變動，需定期校對。"
  },
  "hubs": {
    "NVDA": { "name": "NVIDIA", "cik": "0001045810", "theme": "AI 伺服器 / GPU / CoWoS" },
    "AAPL": { "name": "Apple",  "cik": "0000320193", "theme": "iPhone / 消費電子" }
  },
  "links": {
    "NVDA": [
      { "code": "2330", "name": "台積電",   "role": "先進製程晶圓代工/CoWoS", "tier": 1, "confidence": "high" },
      { "code": "2317", "name": "鴻海",     "role": "AI 伺服器組裝",          "tier": 1, "confidence": "high" },
      { "code": "2382", "name": "廣達",     "role": "AI 伺服器/主機板",       "tier": 1, "confidence": "high" },
      { "code": "6669", "name": "緯穎",     "role": "資料中心伺服器",         "tier": 1, "confidence": "high" },
      { "code": "3231", "name": "緯創",     "role": "AI 伺服器",              "tier": 1, "confidence": "high" },
      { "code": "2376", "name": "技嘉",     "role": "GPU 伺服器/顯卡",        "tier": 1, "confidence": "med"  },
      { "code": "2308", "name": "台達電",   "role": "伺服器電源",             "tier": 1, "confidence": "high" },
      { "code": "3017", "name": "奇鋐",     "role": "散熱模組",               "tier": 2, "confidence": "high" },
      { "code": "3324", "name": "雙鴻",     "role": "散熱模組",               "tier": 2, "confidence": "med"  },
      { "code": "2345", "name": "智邦",     "role": "網通/交換器",            "tier": 2, "confidence": "med"  },
      { "code": "2449", "name": "京元電",   "role": "封裝測試",               "tier": 2, "confidence": "med"  },
      { "code": "3443", "name": "創意",     "role": "ASIC 設計服務",          "tier": 2, "confidence": "med"  },
      { "code": "3661", "name": "世芯-KY",  "role": "ASIC 設計服務",          "tier": 2, "confidence": "med"  },
      { "code": "3711", "name": "日月光投控","role": "封裝測試",              "tier": 2, "confidence": "high" }
    ],
    "AAPL": [
      { "code": "2330", "name": "台積電",   "role": "A/M 系列晶片代工", "tier": 1, "confidence": "high" },
      { "code": "2317", "name": "鴻海",     "role": "iPhone 組裝",      "tier": 1, "confidence": "high" },
      { "code": "3008", "name": "大立光",   "role": "鏡頭",             "tier": 1, "confidence": "high" },
      { "code": "3406", "name": "玉晶光",   "role": "鏡頭",             "tier": 2, "confidence": "med"  },
      { "code": "6269", "name": "台郡",     "role": "軟板 FPC",         "tier": 2, "confidence": "med"  },
      { "code": "4958", "name": "臻鼎-KY",  "role": "軟板 FPC",         "tier": 2, "confidence": "med"  }
    ]
  }
}
```

**欄位規則：**
- `tier`：1＝直接主要供應商、2＝次級/題材相關。
- `confidence`：high/med/low，AI 對這條關係的把握度；low 的在畫面上要弱化或標「待確認」。
- `role`：這家台廠在該供應鏈扮演什麼（散熱、代工、組裝…）。
- **重要**：這張圖是研究參考，關係會變（訂單轉單、供應商更換）。要定期校對，且畫面上要標「供應鏈關係僅供參考」。

**維護方式**：初版由 AI 依公開資訊建（如上），之後每季校對。不要寫死在程式裡，要獨立成 `supply_chain.json` 好更新。

---

## 三、雜訊過濾 / 割韭菜偵測（事件研究）

避免「消息出來時股價早漲完，追進去就套」。對每則有明確標的的新聞計算：
```
run_before = (news日收盤 − news前5日收盤) / news前5日收盤
vol_spike  = news當日量 / 近20日均量
```
判定寫進該則新聞的 `signal` 欄位：
- `run_before > 0.15`（發布前已先漲逾 15%）→ `"caution"`，warning：「⚠️ 消息發布前股價已上漲 X%，恐已反映，追高風險。」
- 消息**前**就爆量（前 1~2 日 `vol_spike > 2`）→ 加註「疑似提前反映/內線味」。
- 消息後才啟動、發布前未大漲 → `"fresh"`，可視為題材尚未反映。

（與《10 分制設計小抄》的 `catalyst` 因子與 `news_warning` 共用同一套邏輯。）

---

## 四、新聞相關性/重要性過濾（分辨有用 vs 沒用）

不是每則都推給使用者。每則打一個 `importance`（0~10）：
- 來源權重：8-K 官方 > 公司 IR > 大眾新聞。
- 事件類型權重：重大合約/財測/併購 > 一般產品新聞 > 人事。
- 是否連動到我們追蹤的供應鏈（有連動加分）。
- `importance < 4` 的預設收合，不洗版。

---

## 五、news.json 產出格式（PWA 讀這個）

```json
{
  "meta": { "generated_at": "2026-08-23T14:30:00+08:00", "source_count": 5,
            "disclaimer": "非投資建議；僅標題與連結，內文請見原站。" },
  "items": [
    {
      "id": "nvda-8k-20260820",
      "time": "2026-08-20T21:05:00Z",
      "source": "SEC 8-K",
      "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/...",
      "hub": "NVDA",
      "title_zh": "NVIDIA 申報 8-K：與雲端客戶簽署資料中心大額合約",
      "ai_summary": "屬 Item 1.01 重大合約，可能拉動 AI 伺服器與 CoWoS 上游需求。",
      "importance": 9,
      "signal": "fresh",
      "warning": null,
      "linked_tw_stocks": [
        { "code": "2330", "name": "台積電", "role": "CoWoS/代工", "tier": 1 },
        { "code": "2382", "name": "廣達",   "role": "AI 伺服器",  "tier": 1 },
        { "code": "3017", "name": "奇鋐",   "role": "散熱",       "tier": 2 }
      ]
    }
  ]
}
```

---

## 六、實作步驟與驗收

1. 建 `docs/` 放本規格與《10 分制設計小抄》，一起進 git。
2. 寫 `news_fetch.py`：抓 SEC 8-K（帶 User-Agent、限速）＋台股 MOPS ＋公開 RSS。
3. 建 `supply_chain.json`（用第二節初版），寫比對邏輯：新聞 hub → linked_tw_stocks。
4. 事件研究與 importance 計分，產出 `news.json` commit 進 repo。
5. 排程：先用本機 Windows 排程或 GitHub Actions，每日/盤後跑一次（先不用即時）。
6. PWA 前端：今日頁/市場頁讀 news.json，重要新聞置頂，點供應鏈標的可跳個股頁。
7. 全頁標「資料時間」「非投資建議」「供應鏈關係僅供參考」。

**驗收清單：**
- [ ] SEC 請求有帶 User-Agent 且限速，不會 403。
- [ ] 只存標題/摘要/連結，無整篇轉貼。
- [ ] supply_chain.json 獨立可更新，關係有 confidence。
- [ ] 割韭菜偵測 `signal`/`warning` 正常。
- [ ] news.json 符合第五節格式，前端能點供應鏈標的跳轉。
- [ ] 台股分析師目標價欄位預留、標示來源限制。
```
