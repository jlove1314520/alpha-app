# Alpha 選股引擎 — 10 分制評分設計小抄

> 這是給 Claude Code（實作端）照著做的規格文件。目標：把目前那種看不懂的「+0.x~1.x 複合分數」換成**總分 10 分、每項滿分 10 分、可攤開解釋**的評分制。
> 版本：scoring-v2 ｜ 最後更新：2026-08-23
> **非投資建議。所有分數只是資料整理與排序，不代表買賣訊號。資料為盤後/延遲資料。**

---

## 一、核心原則（先看懂再寫）

1. **每個因子各自算分 → 正規化到 0–10 → 加權平均成總分（滿分 10）。**
2. **正規化用「橫斷面百分位」，不用 z 分數。** 因為財報比率分布極度偏斜（少數公司 PE 上千），z 分數會被離群值拉爆；百分位天生有界、直覺（前 10% ≈ 9~10 分）。
3. **每一項都要存下「分數 + 一句白話理由 + 原始數據」。** 這就是使用者要的「為什麼值得這個分數」，個股報告頁直接讀這裡。
4. **缺資料要誠實。** 某因子沒資料時，不要塞 0（會冤枉好公司），改用「重新分配權重」處理（見第四節），並記錄 `coverage`（資料完整度）。
5. **成長股不能被本益比一票否決。** 估值因子必須成長調整（PEG / PS），且「成長性」另設獨立因子。

---

## 二、正規化公式（每個因子都照這個做）

對某一個因子，在**某一天、跨全市場 universe**：

```
步驟 1｜算原始值 raw_i           每檔股票 i 的因子原始值（例：EPS 年增率）
步驟 2｜去極值 winsorize         把 raw 裁切在第 1 / 第 99 百分位之間，壓制離群值
步驟 3｜百分位 pct_i            pct_i = rank(raw_i) / (N - 1)     → 落在 0~1
步驟 4｜方向調整                 「越大越好」的因子：keep pct
                               「越小越好」的因子（如 PE、負債比）：pct = 1 - pct
步驟 5｜縮放                    score_i = round(pct_i * 10, 1)    → 0.0 ~ 10.0
```

**方向表（哪些是「越小越好」要反轉）：**
- 越大越好：EPS 年增、營收年增、法人買超、動能、成長率、目標價隱含報酬、供應鏈題材強度
- 越小越好（要反轉）：本益比 PE、股價淨值比 PB、股價營收比 PS、負債比、目標價分歧度

**特例：有明確門檻意義的因子可用絕對分數**（非必須，先全部用百分位也行）。例：營收年增 >30% 直接給滿分區。若採用，理由裡要寫清門檻。

---

## 三、因子清單（起始版，引擎可自行增減）

| 因子 key | 中文名 | 原始指標（範例） | 方向 | 起始權重 |
|---|---|---|---|---|
| `earnings_growth` | 財報成長 | EPS 年增、稅後淨利成長 | 大好 | 0.18 |
| `revenue_momentum` | 營收動能 | 月營收 YoY、MoM、近 3 月趨勢 | 大好 | 0.18 |
| `growth_quality` | 成長性/未來性 | 營收 CAGR、毛利率趨勢、所屬賽道 | 大好 | 0.12 |
| `chips` | 籌碼 | 近 N 日三大法人買超 ÷ 股本 | 大好 | 0.14 |
| `technical` | 技術型態 | 價格 vs 均線、動能、量能 | 大好 | 0.10 |
| `valuation_adj` | 估值(成長調整) | PEG、PS、相對同業 PE | 小好* | 0.12 |
| `analyst` | 機構觀點 | 目標價隱含報酬、券商家數、調升趨勢、分歧度 | 混合 | 0.08 |
| `catalyst` | 題材/事件 | 供應鏈連動、缺貨潮、8-K 事件 | 大好 | 0.08 |

\* `valuation_adj` 用 PEG 而非純 PE：`PEG = PE ÷ 盈餘年成長率(%)`。PEG < 1 便宜、> 2 偏貴。這樣 AI 成長股（PE 30、成長 40%、PEG 0.75）會被判為便宜，不會被殺錯。

**權重加總必須 = 1.0。** 權重可由引擎依回測/市場狀態調整，但每次要把當下用的權重寫進 scores.json（見第五節），使用者才知道這次是怎麼算的。

---

## 四、總分計算與缺資料處理

**正常情況（所有因子都有資料）：**
```
total_score = Σ (factor_score_k × weight_k)      # 因為 Σweight=1，結果自然落在 0~10
```

**缺資料情況（某些因子算不出來）：**
不要給 0。改成「只用有資料的因子，並把權重重新正規化」：
```
可用因子集合 A = {有資料的因子}
total_score = Σ_{k∈A} (factor_score_k × weight_k) ÷ Σ_{k∈A} weight_k
coverage    = Σ_{k∈A} weight_k          # 0~1，代表這個分數建立在多少比例的資料上
```
規則：`coverage < 0.5` 的股票，在排行榜要標「資料不足，分數僅供參考」，且預設不進前段推薦。

---

## 五、scores.json 確切欄位格式（實作端照這個產出）

```json
{
  "meta": {
    "engine_version": "scoring-v2",
    "generated_at": "2026-08-23T14:30:00+08:00",
    "data_asof": "2026-08-22",
    "market": "TW",
    "universe_size": 3196,
    "disclaimer": "非投資建議；資料為盤後/延遲資料。"
  },
  "weights": {
    "earnings_growth": 0.18,
    "revenue_momentum": 0.18,
    "growth_quality": 0.12,
    "chips": 0.14,
    "technical": 0.10,
    "valuation_adj": 0.12,
    "analyst": 0.08,
    "catalyst": 0.08
  },
  "stocks": [
    {
      "code": "2330",
      "name": "台積電",
      "industry": "半導體",
      "rank": 1,
      "total_score": 8.6,
      "coverage": 1.0,
      "data_asof": "2026-08-22",
      "summary": "獲利與營收雙動能強，估值以成長調整後仍不算貴，法人持續買超。",
      "factors": {
        "earnings_growth": {
          "score": 9.2,
          "percentile": 0.92,
          "raw": { "eps_yoy": 0.34 },
          "reason": "EPS 年增 34%，居全市場前 8%。"
        },
        "valuation_adj": {
          "score": 7.5,
          "percentile": 0.75,
          "raw": { "pe": 22.0, "eps_growth": 0.24, "peg": 0.92, "ps": 8.1 },
          "reason": "本益比 22 倍看似不低，但盈餘成長 24%、PEG 0.92，相對成長仍屬便宜。"
        },
        "chips": {
          "score": 8.0,
          "percentile": 0.80,
          "raw": { "inst_net_20d_shares": 45120000, "pct_of_float": 0.017 },
          "reason": "近 20 日三大法人合計買超約 4.5 萬張，佔流通股本 1.7%。"
        },
        "analyst": {
          "score": 6.5,
          "percentile": 0.65,
          "raw": {
            "target_mean": 1050, "price": 900, "implied_return": 0.167,
            "n_brokers": 12, "dispersion": 0.06, "revision_1m": "up"
          },
          "reason": "12 家券商平均目標價 1050（隱含 +16.7%），分歧度低、近一月多被調升，可信度較高。"
        },
        "catalyst": {
          "score": 8.5,
          "percentile": 0.85,
          "raw": {
            "supply_chain_of": ["NVDA"],
            "event": "NVDA 8-K：資料中心新單",
            "event_date": "2026-08-20",
            "price_run_before_news": 0.03
          },
          "reason": "NVDA 8-K 揭露資料中心新單，屬其上游供應鏈；消息發布前股價僅先漲 3%，尚未反映完畢。"
        }
      },
      "flags": ["供應鏈:NVDA"],
      "news_warning": null
    },
    {
      "code": "3006",
      "name": "晶豪科",
      "rank": 88,
      "total_score": 5.1,
      "coverage": 0.62,
      "data_asof": "2026-08-22",
      "summary": "營收轉強但缺乏機構覆蓋，分數建立在部分資料上。",
      "factors": { "revenue_momentum": { "score": 7.2, "percentile": 0.72, "raw": { "rev_yoy": 0.21 }, "reason": "月營收年增 21%。" } },
      "flags": [],
      "news_warning": "⚠️ 近期利多發布前股價已上漲 18%，恐已反映，追高風險。"
    }
  ]
}
```

**欄位規則：**
- `total_score` / 每項 `score`：一律 0.0~10.0，一位小數。
- `percentile`：0~1，兩位小數。
- `raw`：放原始數字，供報告頁展開與稽核用。
- `reason`：一句繁體中文白話，這是「為什麼這個分數」的來源，**必填**。
- `coverage`：0~1，缺資料時 < 1。
- `flags`：字串陣列，供排行榜快速標籤（供應鏈連動、缺貨潮…）。
- `news_warning`：若事件研究判定「可能已反映/割韭菜」，放警語字串；否則 `null`。
- `summary`：整檔一句總評，排行榜列表用。

---

## 六、事件研究（過濾割韭菜新聞）判定邏輯

當某檔股票有新聞/事件時，計算是否「已反映」：
```
run_before = (news_day_close − close_5d_before_news) / close_5d_before_news
vol_spike  = news_day_volume / avg_volume_20d
```
判定：
- `run_before > 0.15`（新聞前已先漲逾 15%）→ `news_warning = "⚠️ 利多發布前股價已上漲 X%，恐已反映"`
- 事件前 1~2 日已爆量（`vol_spike` 在新聞「前」就 > 2）→ 加註「疑似消息面提前反映」
- `run_before` 小、新聞後才啟動 → 視為「尚未反映」，`catalyst` 因子加分

---

## 七、機構目標價（analyst 因子）評估邏輯

不是照單全收，AI 要當懷疑論者：
- `implied_return = (target_mean − price) / price` → 隱含報酬，越高越好
- `dispersion`（目標價標準差 ÷ 平均）→ **越小越可信**（反向計分）
- `n_brokers` → 家數越多越可信（可設門檻，如 < 3 家不採計）
- `revision_1m`（近一月調升/調降趨勢）→ **調升趨勢比目標價絕對值更有預測力**，權重要高
- 資料來源：美股用 yfinance（Yahoo）；**台股目標價暫難免費取得，欄位先預留、來源後補；只用被公開報導的評等/目標價數字，不爬付費報告、不轉貼報告全文。**

---

## 八、實作驗收清單

- [ ] scores.json 產出符合第五節格式，`total_score` 與各項 `score` 皆 0~10。
- [ ] 每個因子都有 `reason`（繁中白話），個股報告頁能展開顯示。
- [ ] 排行榜同時顯示代號＋公司名稱＋總分（讀條）。
- [ ] 缺資料走「重新分配權重」，並標 `coverage` 與警語。
- [ ] `weights` 寫進 meta，使用者看得到這次怎麼加權。
- [ ] `valuation_adj` 用 PEG，不用純 PE，成長股不被殺錯。
- [ ] `news_warning` 事件研究邏輯到位。
- [ ] 全頁標「資料時間」與「非投資建議」。
```
