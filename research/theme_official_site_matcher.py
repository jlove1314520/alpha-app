# -*- coding: utf-8 -*-
"""題材七：官網來源「來源出處 + 反向排除」比對邏輯（地基，未接管線）。

背景：PENDING_QUEUE.md【題材七】要求四條同時成立才給 A 級證據：
  1. 頁面 host 對得上公司官方網址（不是第三方子網域）
  2. 路徑排除 /news/ /press/ /investor/ /ir/ /csr/ /esg/ /careers/ /blog/
  3. 反向排除：句子含「客戶/供應商/合作夥伴/採用/導入/應用於/上游/下游/
     擁有/使用/配備/採購」一律不採
  4. 證據記 source_type: "official_site"

驗收案例（PENDING_QUEUE.md 原文）：
  - 2449 京元電 不得標成 探針卡（測試廠，是買探針卡的人）
  - 6223 旺矽   應標成 探針卡（是做探針卡的人）

本輪（2026-09-15）用真實官網頁面驗證上述四條規則，發現規則 3 的固定
反向排除詞清單**擋不住**京元電子官網「設備研發能力／垂直探針卡」頁面的
這句真實文字（來源：https://www.kyec.com.tw/zh-tw/Service/垂直探針卡）：

    「京元電子已成功開發垂直探針卡 (Vertical Probe Card) 且成功量產。」

這句話 host 對得上 kyec.com.tw、路徑不在排除清單、且不含反向排除清單
任何一詞，會被判定為 A 級證據，直接違反驗收案例「2449 不得標成 探針卡」。
根因：京元電子是為了降低自身測試成本而自製探針卡供內部使用，不是對外
銷售探針卡的業務——反向排除清單設計時只想到「客戶語氣」的句子（買家在
講自己買了什麼），沒想到「自製自用」的句子（廠商在講自己做了什麼，但
目的是內部使用，不是對外銷售）。

結論：規則 3 需要從「反向排除清單（黑名單）」加一道「正向供應語意
（白名單）」才夠嚴謹，不能只加詞到反向排除清單裡（那只是頭痛醫頭）。
本檔案先把地基（host比對/路徑排除/反向排除/正向供應語意）四個函式
獨立寫出來、附真實句子的單元測試，供下一輪接手時直接用，**不擴大到
259 家候選**（那需要另外的官網 URL 蒐集管線，company_info.json 目前
沒有官網欄位，仍是題材七尚未解決的另一個缺口，見本檔案 main 區塊的
待辦清單）。
"""

from __future__ import annotations

from urllib.parse import urlparse

# PENDING_QUEUE.md 原文排除路徑
EXCLUDED_PATH_SEGMENTS = (
    "/news/", "/press/", "/investor/", "/ir/",
    "/csr/", "/esg/", "/careers/", "/blog/",
)

# PENDING_QUEUE.md 原文反向排除詞（買家/使用者語氣）
REVERSE_EXCLUSION_WORDS = (
    "客戶", "供應商", "合作夥伴", "採用", "導入", "應用於",
    "上游", "下游", "擁有", "使用", "配備", "採購",
)

# 2026-09-15 本輪新增：正向供應語意詞（賣家語氣）。
# 加這一層是因為京元電子反例證明「不含反向排除詞」不等於「是賣家」——
# 自製自用的句子兩邊都不含，必須額外要求出現「對外供應」的積極語意，
# 才不會把「我自己做來自己用」誤判成「我是這個題材的供應商」。
POSITIVE_SUPPLY_WORDS = (
    "供應", "出貨", "銷售", "外銷", "接單", "營收占比", "主力產品",
    "主要產品", "領導廠商", "解決方案供應", "量產出貨",
)

# 2026-09-15 本輪新增：內部自用語意詞。即使含正向供應詞，若同句或緊鄰
# 明確講「供內部使用/自用/降低自身成本」，仍應排除——這是京元電子反例
# 的第二層防線（萬一句子剛好也含「量產」這類詞，但講的是自用）。
INTERNAL_USE_WORDS = (
    "供內部", "自用", "自製", "內部使用", "降低自身", "降低成本",
)


def host_matches_official(url: str, official_domains: set[str]) -> bool:
    """條件1：頁面 host 是否對得上公司官方網址（含子網域），排除第三方網域。"""
    host = urlparse(url).netloc.lower()
    host = host.split(":")[0]  # 去掉 port
    for dom in official_domains:
        dom = dom.lower().lstrip("www.")
        bare_host = host.lstrip("www.")
        if bare_host == dom or bare_host.endswith("." + dom):
            return True
    return False


def is_excluded_path(url: str) -> bool:
    """條件2：路徑是否命中排除清單（news/press/investor/ir/csr/esg/careers/blog）。"""
    path = urlparse(url).path.lower()
    return any(seg in path for seg in EXCLUDED_PATH_SEGMENTS)


def has_reverse_exclusion(sentence: str) -> bool:
    """條件3原版：句子是否含買家/使用者語氣詞。"""
    return any(w in sentence for w in REVERSE_EXCLUSION_WORDS)


def has_positive_supply_signal(sentence: str) -> bool:
    """2026-09-15新增：句子是否含賣家/供應方語氣詞。"""
    return any(w in sentence for w in POSITIVE_SUPPLY_WORDS)


def has_internal_use_signal(sentence: str) -> bool:
    """2026-09-15新增：句子是否明確講自用/內部使用（即使含正向供應詞也要擋）。"""
    return any(w in sentence for w in INTERNAL_USE_WORDS)


def classify_sentence_v1_original(
    url: str, sentence: str, official_domains: set[str]
) -> bool:
    """PENDING_QUEUE.md 原版四條規則（1,2,4 併入呼叫端，這裡只做 1+2+3）。

    回傳 True＝判定為 A 級證據（會被 build_themes.py 採用）。

    **使用前提（2026-09-15 負對照組實測發現，接管線時務必遵守）**：
    這個函式**不做關鍵詞比對**，只判斷「這個來源夠不夠格當A級證據」，
    不判斷「這句話講的是不是這個題材」。呼叫端必須先用題材關鍵詞
    （`data/seed/theme_keywords.json`）比對過這句話確實含某題材的關鍵詞，
    才呼叫這個函式問「這個來源可信嗎」。如果對任何官網句子（不管有沒有
    先做關鍵詞比對）直接呼叫這個函式，任何一句官網文字都會被判成A級證據
    （見`theme_official_site_negative_control.py`實測：長榮官網一句完全
    不含任何題材關鍵詞的句子，直接呼叫本函式仍回傳True）。
    """
    if not host_matches_official(url, official_domains):
        return False
    if is_excluded_path(url):
        return False
    if has_reverse_exclusion(sentence):
        return False
    return True


def classify_sentence_v2_with_positive_signal(
    url: str, sentence: str, official_domains: set[str]
) -> bool:
    """2026-09-15 提議的修正版：加正向供應語意 + 內部自用排除。

    四條規則的條件3改為：host對得上 + 路徑未排除 + 不含反向排除詞
    + **必須含正向供應語意詞** + 不含內部自用語意詞。
    """
    if not host_matches_official(url, official_domains):
        return False
    if is_excluded_path(url):
        return False
    if has_reverse_exclusion(sentence):
        return False
    if has_internal_use_signal(sentence):
        return False
    if not has_positive_supply_signal(sentence):
        return False
    return True


if __name__ == "__main__":
    # 真實查證案例（2026-09-15 用 WebFetch 實際讀取官網頁面取得，非杜撰）：
    cases = [
        dict(
            name="旺矽(6223) 應標成 探針卡",
            url="https://www.mpi.com.tw/probecard/about-mpi-pc/",
            sentence="旺矽科技探針卡事業群為國際晶圓級探針卡解決方案領導廠商，供應半導體晶圓測試之探針卡",
            official_domains={"mpi.com.tw"},
            expect=True,
        ),
        dict(
            name="京元電(2449) 反例一：自製自用句，不含反向排除詞，v1會誤判",
            url="https://www.kyec.com.tw/zh-tw/Service/垂直探針卡",
            sentence="京元電子已成功開發垂直探針卡 (Vertical Probe Card) 且成功量產。",
            official_domains={"kyec.com.tw"},
            expect=False,
        ),
        dict(
            name="京元電(2449) 反例二：含「擁有」，v1本來就會排除",
            url="https://www.kyec.com.tw/zh-tw/Service/垂直探針卡",
            sentence="本公司擁有自主開發及製作垂直探針卡的技術。",
            official_domains={"kyec.com.tw"},
            expect=False,
        ),
    ]

    print("=== v1（PENDING_QUEUE.md 原版規則）===")
    v1_pass = True
    for c in cases:
        got = classify_sentence_v1_original(c["url"], c["sentence"], c["official_domains"])
        ok = got == c["expect"]
        v1_pass = v1_pass and ok
        print(f"[{'OK' if ok else 'FAIL'}] {c['name']}: 判定={got} 預期={c['expect']}")

    print()
    print("=== v2（本輪新增：加正向供應語意 + 內部自用排除）===")
    v2_pass = True
    for c in cases:
        got = classify_sentence_v2_with_positive_signal(
            c["url"], c["sentence"], c["official_domains"]
        )
        ok = got == c["expect"]
        v2_pass = v2_pass and ok
        print(f"[{'OK' if ok else 'FAIL'}] {c['name']}: 判定={got} 預期={c['expect']}")

    print()
    print(f"結論：v1 通過驗收案例＝{v1_pass}（預期 False，證實原版規則有漏洞）")
    print(f"      v2 通過驗收案例＝{v2_pass}（加正向供應語意後是否補上這個漏洞）")
    print()
    print("下一輪待辦（本輪未做，範圍超出一個有界工作單位）：")
    print("  1. company_info.json 補公司官方網址欄位（來源：MOPS t187ap03_L 或公司年報）")
    print("     ——已有7家人工核實種子清單data/company_official_domains_seed.json可先參考")
    print("  2. 抓取管線：對 259 家 D 級候選逐一抓官網頁面（含 7 家連不上重試、")
    print("     3017 這類 JS 渲染站記 blocked_js_render 跳過，不裝無頭瀏覽器）")
    print("  3. 【2026-09-15已完成5/5家】負對照組見theme_official_site_negative_control.py：")
    print("     1216統一/2542興富發/2603長榮/5530龍巖/3130一零四跑123題材關鍵詞，")
    print("     跨題材意外命中=0（PASS）。過程中發現並更正兩個真實bug：")
    print("     (a) 種子清單2542的official_domain原誤植為無關第三方公司『順發3C』的網域；")
    print("     (b) 短英文縮寫關鍵詞（如「EG」）用naive substring比對會誤判英文借詞")
    print("     子字串（例如「Legacy」內含「eg」），已改用詞界正則修好，只影響")
    print("     negative_control.py自己的測試迴圈，未影響任何正式管線（因為待辦1")
    print("     的正式管線尚未建）。並確認classify_sentence_v1/v2的使用前提（呼叫端")
    print("     須先做關鍵詞比對，這兩個函式本身不做），已記錄進函式docstring。")
    print("     仍缺：更嚴謹的123個題材全面跨行業誤判掃描（待辦4的延伸範疇）。")
    print("  4. v2 的正向供應語意詞清單需要用更多真實案例擴充驗證，目前只驗證了 3 句")
