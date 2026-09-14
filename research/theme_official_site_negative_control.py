# -*- coding: utf-8 -*-
"""題材七 待辦3：負對照組實測（2026-09-15）。

背景：`theme_official_site_matcher.py` 的 main 區塊待辦清單第3項——用
明確與七大題材（半導體供應鏈123個子題材）無關的公司，跑 v1/v2 規則，
期望命中0。本檔案是那一步的實測腳本，用真實官網句子（非杜撰）。

三家負對照組公司（`data/company_official_domains_seed.json`）：
  1216 統一（食品業）、2542 興富發（營建業）、2603 長榮（航運業）。

**本輪過程中的意外發現（比原定任務更重要）**：查證 2542 興富發時，
種子清單原記錄的 official_domain『sunfar.com.tw』經WebFetch實測回傳SSL
憑證錯誤，WebSearch三方交叉查證後確認那其實是『順發3C』的網域，與
興富發建設無關——已在 `company_official_domains_seed.json` 更正為
`highwealth.com.tw`，並記錄教訓（見該檔 meta.correction_2026-09-15）。

**方法**：每家公司用一句從官方網域（或官方內容經WebSearch二次確認來源）
取得的真實業務描述句，用該公司自己的網域組一個假造URL（因為這些公司
首頁本身不含明確題材相關句子，此處測試重點是「句子內容即使被拿去跑
123個題材關鍵詞比對，也不該命中任何一個」，不是測host比對本身——
host比對已由驗收案例的 mpi.com.tw/kyec.com.tw 兩個正反例覆蓋過）。

**本輪過程中的第二個意外發現（比原定任務更重要，會影響下一輪接管線的人）**：
第一版測試直接把三句話餵給 `classify_sentence_v1_original()`／
`classify_sentence_v2_with_positive_signal()`，發現**兩個函式都不檢查句子
是否含題材關鍵詞**——它們只檢查host/路徑/反向排除詞/正向供應語意，這代表
它們的正確使用前提是「呼叫端已經先用關鍵詞比對確認這句話跟某個題材有關」，
這兩個函式本身只負責「這個來源夠不夠格當A級證據」，不負責「這句話講的是
不是這個題材」。**這個使用前提在matcher.py目前的docstring/函式簽名裡完全
沒寫清楚**——如果下一輪接管線時直接對『任何官網句子』呼叫這兩個函式，
不先做關鍵詞比對，會把任何一句官網文字都判成A級證據，是一個嚴重的介面
誤用風險，已在下面`run()`的判定邏輯與本檔案docstring明確記錄，供下一輪
接管線時當作函式呼叫順序的硬性前提。

**第三個發現（原定任務本身的結果）**：123個題材關鍵詞比對顯示，1216統一
命中『food食品』題材關鍵詞「食品」、2542興富發命中『construction營建』
題材關鍵詞「營造」——這**不是誤判**，是正確結果，因為批次三/四已經把
食品、營建本身納入123個追蹤題材（見PENDING_QUEUE.md題材三批次三/四）。
`PENDING_QUEUE.md`原文「5家明確與七大題材無關的公司（食品/營建/航運）」
寫於18→123題材擴充**之前**，當時食品/營建/航運確實跟半導體供應鏈題材
無關；擴充之後食品/營建本身變成合法題材，這句原文的前提已經過時。
**真正有意義的負對照組指標**：這3家公司的句子除了命中自己本業所屬的
題材外，有沒有**意外命中其他120個不相關題材**（例如統一的句子有沒有
不小心命中「探針卡」「CoWoS」之類半導體詞）——實測結果：0個意外命中，
這才是本輪負對照組驗證真正成立的結論。
"""

from __future__ import annotations

import json
from pathlib import Path

from theme_official_site_matcher import (
    classify_sentence_v1_original,
    classify_sentence_v2_with_positive_signal,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 三句皆為 2026-09-15 用 WebFetch/WebSearch 實際取得的官方網域內容，逐字引用，
# 未改寫（WebFetch 對 uni-president.com.tw 首頁本身抓不到完整業務句，改用
# WebSearch 交叉確認來源為官網內容摘要；highwealth.com.tw 直接 WebFetch 被
# 403 擋下，改用 WebSearch 摘要，來源標注於 note）。
NEGATIVE_CONTROL_CASES = [
    dict(
        stock_id="1216",
        name="統一",
        official_domain="uni-president.com.tw",
        sentence=(
            "統一企業1967年8月25日創立於台南永康，深耕台灣超過五十年。"
            "除致力食品製造本業以外，更透過多元資源整合綜效，"
            "全面提供消費者食衣住行育樂多采多姿新體驗。"
        ),
        source_note="2026-09-15 WebSearch交叉確認，來源為統一企業官網公司簡介摘要",
    ),
    dict(
        stock_id="2542",
        name="興富發",
        official_domain="highwealth.com.tw",
        sentence=(
            "興富發集團對產業具有強烈的使命感，長期在建築營造本業精進，"
            "追求設計規劃與工程技術的提升，作品從北到南、從首購到換屋；"
            "從2房到別墅；從豪宅到辦公室。"
        ),
        source_note="2026-09-15 WebSearch交叉確認，來源為興富發官網about.php內容摘要（直接WebFetch被403擋下）",
    ),
    dict(
        stock_id="2603",
        name="長榮",
        official_domain="evergreen-marine.com",
        sentence=(
            "整合長榮集團旗下的海運公司，以單一品牌提供全球貨主完善的運送服務"
        ),
        source_note="2026-09-15 WebFetch直接取得，來源為evergreen-marine.com「我們的服務」頁面",
    ),
]


# 這3家公司自己本業所屬的題材id——命中這些不算false positive（是正確結果，
# 見上面docstring第三個發現）。其餘120個題材若被命中才是真正的負對照組警訊。
OWN_INDUSTRY_THEME_IDS = {
    "1216": {"food"},
    "2542": {"construction"},
    "2603": {"container_shipping", "bulk_shipping"},
}


def run() -> bool:
    with open(DATA_DIR / "seed" / "theme_keywords.json", encoding="utf-8") as f:
        theme_data = json.load(f)
    themes = theme_data["themes"]

    all_clean = True
    print("=== 題材七 待辦3：負對照組實測（3家公司 x 123題材關鍵詞）===\n")

    for case in NEGATIVE_CONTROL_CASES:
        sentence = case["sentence"]
        domain = {case["official_domain"]}
        stock_id = case["stock_id"]
        own_themes = OWN_INDUSTRY_THEME_IDS.get(stock_id, set())

        all_hits = []
        cross_theme_hits = []
        for theme_id, theme in themes.items():
            for kw in theme["keywords"]:
                if kw and kw.lower() in sentence.lower():
                    all_hits.append((theme_id, theme["name"], kw))
                    if theme_id not in own_themes:
                        cross_theme_hits.append((theme_id, theme["name"], kw))

        # classify_sentence_v1/v2 本身不做關鍵詞比對（見上方docstring第二個
        # 發現），這裡只在「確實命中某題材關鍵詞」的情況下才呼叫，模擬正確
        # 的呼叫順序（呼叫端先關鍵詞比對，比對到才問這個來源夠不夠格）。
        for theme_id, theme_name, kw in all_hits:
            fake_url = f"https://www.{case['official_domain']}/about"
            v1_flag = classify_sentence_v1_original(fake_url, sentence, domain)
            v2_flag = classify_sentence_v2_with_positive_signal(fake_url, sentence, domain)
            tag = "本業合法題材" if theme_id in own_themes else "跨題材意外命中"
            print(f"    命中「{theme_name}」（{tag}，關鍵詞「{kw}」）"
                  f"　v1={v1_flag}　v2={v2_flag}")

        ok = len(cross_theme_hits) == 0
        all_clean = all_clean and ok

        print(f"[{'OK' if ok else 'FAIL'}] {stock_id} {case['name']}"
              f"（{case['official_domain']}）")
        print(f"  句子：{sentence}")
        print(f"  來源：{case['source_note']}")
        print(f"  全部題材命中數：{len(all_hits)}　"
              f"跨題材意外命中數（負對照組真正指標）：{len(cross_theme_hits)}\n")

    print(f"結論：3家負對照組公司皆無跨題材意外命中＝{all_clean}")
    print("（原定計畫5家，本輪seed清單實際核實3家（食品/營建/航運各一）；"
          "PENDING_QUEUE.md原文『與七大題材無關』寫於18→123題材擴充之前，"
          "擴充後食品/營建本身已是合法題材，命中自己本業題材不算失敗，"
          "見本檔案docstring第三個發現；不足的2家與更嚴謹的跨題材對照"
          "留給下一輪視需要再補）")
    return all_clean


if __name__ == "__main__":
    result = run()
    raise SystemExit(0 if result else 1)
