# -*- coding: utf-8 -*-
"""題材規則單元測試（題材二驗收，2026-09-09）。

總司令指定的驗收案例都寫在這裡，**回歸時一眼看得出哪一條破了**。
用法：`python scripts/test_theme_rules.py`（回傳 0 全過、1 有失敗）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

FAILED = []


def check(name: str, got, want, note: str = ""):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {name}")
    if not ok:
        print(f"      得到 {got!r}，期望 {want!r}　{note}")
        FAILED.append(name)


def main() -> int:
    from news_body_extract import PATTERNS, pattern_hit
    from news_matcher import match_codes_by_number, load_active_codes
    from build_themes import _source_key

    active = load_active_codes()

    print("=== 題材二.3：關係方向要求（共現不算歸屬）===")
    # 總司令指定的測試案例：這句只是「台積電和光罩出現在同一句」，
    # 沒有任何「台積電做光罩」的關係陳述——**必須不命中**。
    case = "台積電攜ASML開發12吋光罩 專家：輝達GPU尺寸驅動"
    check("「台積電攜ASML開發12吋光罩」不得命中光罩題材",
          pattern_hit(case, ["光罩"], PATTERNS), None,
          "共現不算歸屬，需明確關係句型")
    # 對照組：這句有明確關係，應該命中
    check("「光罩廠」應命中（有明確關係）",
          pattern_hit("光罩廠台灣光罩今日表示", ["光罩"], PATTERNS) is not None, True)

    print("\n=== 題材二.2：同文轉載偵測 ===")
    a = "台積電攜ASML開發12吋光罩 專家：輝達GPU尺寸驅動"
    b = "台積電攜ASML開發12吋光罩　專家：輝達GPU尺寸驅動"      # 全形空白
    c = "台積電攜ASML開發12吋光罩（專家：輝達GPU尺寸驅動）"     # 加括號
    check("全形空白差異視為同一來源", _source_key(a), _source_key(b))
    check("括號差異視為同一來源", _source_key(a), _source_key(c))
    check("不同標題不是同一來源",
          _source_key(a) != _source_key("聯發科IC設計龍頭開高走低"), True)

    print("\n=== 代號比對：括號年份不得當成股票代號 ===")
    check("明(2027)年 → 不得命中 2027",
          sorted(match_codes_by_number("明(2027)年起開始貢獻產能", active)), [])
    check("台積電 (2330) → 應命中 2330",
          sorted(match_codes_by_number("台積電 (2330) 撐盤", active)), ["2330"])
    check("攻2505元 → 不得命中 2505",
          sorted(match_codes_by_number("台積電撐盤攻2505元", active)), [])
    check("2030年 → 不得命中 2030",
          sorted(match_codes_by_number("資策會預估至2030年台灣產能", active)), [])

    print("\n=== 題材六.4：Yahoo 版面雜訊必須產出 0 條題材句 ===")
    from news_body_extract import split_sentences, is_frame_noise
    noise = ("加入為 Google 偏好來源，將 Yahoo 設為首選來源，在 Google 上查看更多，"
             "熱門股 台積電 聯發科 鴻海 廣達 散熱 記憶體")
    sents = split_sentences(noise)
    hits = [s for s in sents if pattern_hit(s, ["散熱", "記憶體"], PATTERNS)]
    check("整段版面雜訊產出 0 條題材句", len(hits), 0,
          f"切出 {len(sents)} 句，其中命中句型 {len(hits)} 句")
    check("「加入為 Google 偏好來源」被判定為框架雜訊",
          is_frame_noise("加入為 Google 偏好來源"), True)
    check("「熱門股」側欄被判定為框架雜訊",
          is_frame_noise("熱門股 台積電 聯發科 散熱"), True)
    check("正常報導句不被誤判為雜訊",
          is_frame_noise("晶圓代工廠台積電今日表示先進封裝產能將擴充"), False)

    print()
    print("=== 題材八：A 級也要句型與反向排除（2026-09-10 總司令驗收案例）===")
    from build_themes import (evidence_keyword, kw_outside_company_name,
                              company_name_spans, load_patterns)
    pats = load_patterns()

    # 總司令原文指定的兩個反例。兩者「答案碰巧對，理由是錯的」——
    # 命中的都是子公司名稱裡的字，而那是租賃公告與公司債發行公告。
    bad1 = "代子公司上海易統食品貿易有限公司公告取得使用權資產"
    check("「代子公司上海易統食品貿易有限公司公告取得使用權資產」不得命中食品",
          evidence_keyword(bad1, ["食品"], pats), (None, None),
          "「食品」只出現在子公司名稱裡，那是名字不是業務事實")
    bad2 = "富邦金控代子公司富邦證券公告發行115年度第二次無擔保 普通公司債"
    check("「富邦金控代子公司富邦證券公告發行…公司債」不得命中金控",
          evidence_keyword(bad2, ["金控"], pats), (None, None),
          "「金控」出現在公司名稱片段中")

    # 正面案例：真正描述產品／擴產／接單的公告要照樣命中，
    # 否則這道防線就是把所有東西一起擋掉，那不叫修好。
    good1 = "本公司CoWoS產能擴充計畫說明"
    check("「CoWoS產能」應命中（真正描述產能）",
          evidence_keyword(good1, ["CoWoS"], pats)[0], "CoWoS")
    good2 = "本公司打入散熱供應鏈並取得客戶認證"
    check("「打入散熱供應鏈」應命中（真正描述接單）",
          evidence_keyword(good2, ["散熱"], pats)[0], "散熱")
    # 關鍵詞同時出現在公司名稱裡**與**名稱外時，名稱外那次算數
    good3 = "台灣食品股份有限公司公告食品產能擴產"
    check("關鍵詞在公司名稱外也出現過一次時仍應命中",
          evidence_keyword(good3, ["食品"], pats)[0], "食品",
          "只有「每一次出現都在名稱裡」才該擋")

    # 輔助函式本身的行為（壞掉時比整條規則好定位）
    check("「食品」在「上海易統食品貿易有限公司」中被判定為公司名稱片段",
          kw_outside_company_name("代子公司上海易統食品貿易有限公司公告", "食品"), False)
    check("「食品」在「食品產能擴產」中不算公司名稱片段",
          kw_outside_company_name("食品產能擴產", "食品"), True)
    check("公司名稱片段偵測得到至少一段",
          len(company_name_spans(bad1)) >= 1, True)

    # 純共現（有公司名稱以外的關鍵詞、但沒有句型）仍要擋——題材八.1
    check("純共現無句型不得命中（A 級比照 C 級）",
          evidence_keyword("台積電攜ASML開發12吋光罩", ["光罩"], pats), (None, None))

    print()
    if FAILED:
        print(f"✗ {len(FAILED)} 項失敗：{FAILED}")
        return 1
    print("✓ 全部通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
