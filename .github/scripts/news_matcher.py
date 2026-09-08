# -*- coding: utf-8 -*-
"""新聞→個股 精確比對（題材萃取一.1，2026-09-08）。

**為什麼要重做**：舊規則只認「標題裡的四位數」，實測 179 則新聞標到 6 筆，
**其中 5 筆是錯的**：

    2505 國揚  ← 「台積電撐盤攻 2505元」      那是股價
    2030 彰源  ← 「2030年 台灣產能占比」      那是年份
    2023 燁輝  ← 「創 2023年 以來最大」       那是年份（2 筆）
    0050 元大台灣50 ← 「全換 0050」           這筆才是對的

精確率 **1/6 = 16.7%**。**錯的標記比沒有標記更糟**——
使用者看到「國揚有新聞」會去點，點進去發現是台積電股價，
那不只是沒幫助，是損害信任。

**總司令裁示：精確比對，非模糊猜測；同名歧義一律標記歧義不採用，寧缺勿錯。**

三道規則：
1. **四位數代號**：後面不得接單位字（元/年/點/億/萬/月/日/％/倍…），
   且必須在官方在市名冊內。這一條擋掉上面全部四筆假陽性。
2. **公司名稱**：用 `company_info.json` 的官方名稱與簡稱建字典（約 2,837 檔）。
   **只做精確子字串比對，不做模糊匹配。**
3. **歧義排除**：一個名稱若同時對應多個代號、或本身是另一個公司名的子字串、
   或落在通用詞黑名單（如「中國」「台灣」「大同」這種同時是公司名又是常用詞），
   一律**標記歧義不採用**。

比對範圍含**標題與內文**（內文由呼叫端提供，可為空）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# 四位數後面接這些字元時，那是數量／時間／價格，不是股票代號。
# 這一條就擋掉了實測 5 筆假陽性裡的 4 筆。
_UNIT_AFTER = "元年點億萬月日％%倍檔張股人次筆件坪度℃碼米噸台家"
# 前面接這些也不是代號（例如「逾450點」「約2030」）
_UNIT_BEFORE = "第約逾近超破漲跌至明今去前隔次來自於"

# 通用詞黑名單：這些是合法公司簡稱，但同時是高頻常用詞，
# 在新聞文字裡出現多半不是在講那家公司。寧缺勿錯。
GENERIC_NAME_BLACKLIST = {
    "中國", "台灣", "中華", "統一", "聯合", "大成", "永光", "第一", "國票",
    "大眾", "台新", "新光", "全國", "農林", "中興", "力和", "東元", "中鋼",
    "台南", "南港", "大時", "亞洲", "國建", "京城", "萬泰", "三洋", "宏泰",
}


def load_company_names() -> tuple[dict, set]:
    """回傳 (name → code, 歧義名稱集合)。

    歧義的三種來源，任一命中就不採用：
      (a) 同一個名稱對到多個代號
      (b) 名稱是另一個公司名的子字串（例如「台光」vs「台光電」）
      (c) 落在通用詞黑名單
    """
    p = ROOT / "data" / "company_info.json"
    try:
        companies = json.loads(p.read_text(encoding="utf-8")).get("companies") or {}
    except (OSError, json.JSONDecodeError):
        return {}, set()

    raw: dict[str, set] = {}
    for code, info in companies.items():
        if not isinstance(info, dict):
            continue
        nm = (info.get("name") or "").strip()
        # 太短的名稱（1~2 字）誤判率極高，直接不用
        if len(nm) < 3:
            continue
        raw.setdefault(nm, set()).add(code)

    ambiguous = set(GENERIC_NAME_BLACKLIST)
    for nm, codes in raw.items():
        if len(codes) > 1:
            ambiguous.add(nm)              # (a) 一名多碼
    names = sorted(raw)
    for i, a in enumerate(names):
        for bname in names:
            if a != bname and a in bname:
                ambiguous.add(a)           # (b) 是別人的子字串
                break

    name2code = {nm: sorted(codes)[0] for nm, codes in raw.items()
                 if nm not in ambiguous and len(codes) == 1}
    return name2code, ambiguous


def load_active_codes() -> set:
    p = ROOT / "data" / "listed_universe.json"
    try:
        return set(json.loads(p.read_text(encoding="utf-8")).get("active") or [])
    except (OSError, json.JSONDecodeError):
        return set()


_BRACKETS_AFTER = ")）]】》」"
_BRACKETS_BEFORE = "(（[【《「"


def match_codes_by_number(text: str, active: set) -> set:
    """規則 1：四位數代號，排除單位／年份／價格語境。

    2026-09-09 補強：**括號包住的年份會穿過第一版的檢查。**
    實測踩到「…預計可於今年第4季至明(2027)年起開始貢獻產能…」——
    `2027` 後面緊鄰的是 `)` 不在單位字表裡，於是被當成大成鋼(2027)，
    整句「南亞針對銅箔基板廠進行製程優化」被歸到大成鋼名下。

    但**不能一律拒絕括號內的數字**——「台積電 (2330)」正是最標準的寫法。
    差別在括號**外面**接的是什麼：`(2027)年` 是年份，`(2330)` 才是代號。
    所以改成「跳過括號字元後再看單位字」。
    """
    hits = set()
    for m in re.finditer(r"(?<!\d)(\d{4})(?!\d)", text or ""):
        code = m.group(1)
        if code not in active:
            continue
        # 往後跳過連續的右括號，再看下一個實體字元
        i = m.end()
        while i < len(text) and text[i] in _BRACKETS_AFTER:
            i += 1
        after = text[i:i + 1]
        # 往前跳過連續的左括號，再看前一個實體字元
        j = m.start()
        while j > 0 and text[j - 1] in _BRACKETS_BEFORE:
            j -= 1
        before = text[max(0, j - 1):j]
        if after and after in _UNIT_AFTER:
            continue                       # 2505元、2030年、(2027)年
        if before and before in _UNIT_BEFORE:
            continue                       # 逾450、約2030、明(2027)
        hits.add(code)
    return hits


def match_codes_by_name(text: str, name2code: dict, active: set | None = None) -> set:
    """規則 2＋3：精確名稱比對，歧義的已在字典建立時排除。

    `active` 給定時同樣要求命中的代號在官方在市名冊內——
    實測踩到：「加權指數」會比到 `TAIEX`，那是指數不是個股，
    題材成員只能是股票，混進指數會讓後續的權重分攤失去意義。
    """
    t = text or ""
    hits = {code for nm, code in name2code.items() if nm in t}
    if active:
        hits &= active
    return hits


def match_article(title: str, body: str, name2code: dict, active: set) -> dict:
    """回傳 {codes, by_number, by_name}。codes 是聯集。"""
    text = (title or "") + "\n" + (body or "")
    by_num = match_codes_by_number(text, active)
    by_name = match_codes_by_name(text, name2code, active)
    return {
        "codes": sorted(by_num | by_name),
        "by_number": sorted(by_num),
        "by_name": sorted(by_name),
    }


if __name__ == "__main__":
    import sys
    for s in (sys.stdout,):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    n2c, amb = load_company_names()
    act = load_active_codes()
    print(f"可用名稱字典 {len(n2c)} 筆、判定歧義排除 {len(amb)} 筆、在市名冊 {len(act)} 檔")
