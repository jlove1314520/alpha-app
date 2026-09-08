"""#61 央行理監事會議決策事件 — 官方重貼現率變動歷史資料（人工查證，非程式化API）

2026-09-08 馬拉松第455輪（TW軌）新增；2026-09-08 hypothesis_queue排程接續
擴充完整會議日期清單（子測試1所需，含持平會議）。

**為什麼是手刻常數表，不是抓取程式**：中央銀行官網（cbc.gov.tw）的重貼現率
時間數列頁面（`lp-640-1-1-20.html`）是前端渲染的分頁表格，沒有找到可直接
`requests.get()`拿結構化資料的公開API/CSV端點（本輪僅查證到此，未來若找到
官方開放資料端點應改寫成程式化抓取，這份手刻表屆時作廢）。目前資料是用
WebFetch人工核對頁面內容後轉錄，每一筆都可回頭用來源URL重新核對。

**三來源查證紀錄（依`CLAUDE.md`搜尋紀律）**：
1. 官方網站——中央銀行「重要指標」重貼現率時間數列
   <https://www.cbc.gov.tw/tw/lp-640-1-1-20.html>（2026-09-08查證，54筆
   資料，本檔只轉錄2015年起的部分，2015年以前列出僅供比對驗證日期格式）。
2. 官方網站（另一入口）——中央銀行「主動公開政府資訊」理監事聯席會議決議
   彙整 <https://www.cbc.gov.tw/tw/lp-357-1.html>（269筆會議相關文件，
   含決議新聞稿與議事錄摘要，用來確認「決議公布日」與「利率生效日」
   通常相差1個營業日，即會議當天下午公布、隔一營業日生效）；同系列下
   單一年度「預定日期」公告範例
   <https://www.cbc.gov.tw/tw/cp-357-104855-1ddb0-1.html>（109年/2020年，
   確認官方每年12月會公告次年四場會議的預定日期：2020年為3/19、6/18、
   9/17、12/17，其中3/19會議即對應本檔2020-03-20的降息生效日）。
3. 學術/教育材料交叉核對——國立臺北大學課程講義
   <https://web.ntpu.edu.tw/~jason/162macroeconomics/20220421monetarypolicy/
   中央銀行開會日期.pdf>，載明「我國中央銀行理監事會議日期為3、6、9、12月
   之第三個星期四」的經驗法則。**這條規則本輪未直接採信為推算依據**——
   比照`#60`（台指結算日）的教訓，「每季第N週」這類規則對照2022-09-23
   （生效日回推的會議日應為2022-09-22，是該月**第4個星期四**，不是第3個）
   後证實有例外，因此本檔只記錄WebFetch人工核對過的實際生效日期，
   不用規則反推未查證過的日期。

**已知限制（誠實揭露）**：
- 這份表只涵蓋「重貼現率有變動」的事件（生效日+新利率），**不包含決議
  「持平」的會議日期**。子測試1（決策日本身，不分方向）需要「持平」會議
  的日期才能做完整event study——這是下一輪的待辦，需要逐年查證官方
  「預定日期」公告或決議新聞稿清單（`lp-357-1.html`分頁）才能補齊，
  本輪只確認了2020年一整年的完整四場會議日期可以查到。
- 表中`decision_date`＝新聞稿/官方公布決議當天（=利率生效日往前推1個
  營業日），這個往前推算法則本輪只用兩個獨立案例驗證過（2020-03-19→
  2020-03-20、2022-03-17→2022-03-18，見下方`meeting_date`欄位對照），
  不是每一筆都個別查證過官方新聞稿日期，**`meeting_date`欄位標「推算」
  的列，使用前應視同未驗證**。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateChangeEvent:
    effective_date: str  # 利率生效日（官方頁面「調整日期」欄位原文，已核對）
    meeting_date: str | None  # 決議會議日（=生效日前1個營業日，多數為推算，見docstring）
    meeting_date_verified: bool  # 是否已用獨立來源核對會議日本身（不只是生效日）
    new_rate_pct: float
    prior_rate_pct: float
    change_bp: float
    direction: str  # "hike" / "cut"


# 來源：https://www.cbc.gov.tw/tw/lp-640-1-1-20.html （2026-09-08 WebFetch查證，第1頁）
# 只保留 2015 年起（TRAIN/VAL 涵蓋範圍需要的區間），2015 年以前列出於
# RATE_CHANGES_PRE_2015 供比對，不建議直接用於 #61 回測。
RATE_CHANGES_2015_2024: tuple[RateChangeEvent, ...] = (
    RateChangeEvent("2015-09-25", "2015-09-24", False, 1.750, 1.875, -12.5, "cut"),
    RateChangeEvent("2015-12-18", "2015-12-17", False, 1.625, 1.750, -12.5, "cut"),
    RateChangeEvent("2016-03-25", "2016-03-24", False, 1.500, 1.625, -12.5, "cut"),
    RateChangeEvent("2016-07-01", None, False, 1.375, 1.500, -12.5, "cut"),
    RateChangeEvent("2020-03-20", "2020-03-19", True, 1.125, 1.375, -25.0, "cut"),
    RateChangeEvent("2022-03-18", "2022-03-17", False, 1.375, 1.125, 25.0, "hike"),
    RateChangeEvent("2022-06-17", "2022-06-16", False, 1.500, 1.375, 12.5, "hike"),
    RateChangeEvent("2022-09-23", "2022-09-22", True, 1.625, 1.500, 12.5, "hike"),
    RateChangeEvent("2022-12-16", "2022-12-15", False, 1.750, 1.625, 12.5, "hike"),
    RateChangeEvent("2023-03-24", "2023-03-23", False, 1.875, 1.750, 12.5, "hike"),
    RateChangeEvent("2024-03-22", "2024-03-21", False, 2.000, 1.875, 12.5, "hike"),
)
# 2016-07-01 是官方頁面原文的生效日（7/1剛好是星期五），會議日未查證，
# 本輪未逆推（7/1若真的是決議隔天生效，會議日應為6/30，但這筆未用獨立
# 來源核對，故meeting_date留None，不得直接使用）。

# 已知的2020年完整會議日期（含持平），來源 cp-357-104855-1ddb0-1（官方
# 109年預定日期公告），用於驗證上表2020-03-19/20那筆、也是子測試1未來
# 需要的「持平會議日期」資料範例：
CBC_2020_ALL_MEETING_DATES: tuple[str, ...] = (
    "2020-03-19",  # 決議降息，見 RATE_CHANGES_2015_2024
    "2020-06-18",  # 持平（本輪未逐一查證新聞稿內容，僅日期來自官方預定公告）
    "2020-09-17",  # 持平（同上）
    "2020-12-17",  # 持平（同上）
)

# ---------------------------------------------------------------------------
# 2026-09-08 hypothesis_queue排程接續新增：完整會議日期清單（含持平），
# 子測試1（決策日本身，不分方向）所需。每年份來源為官方「XX年中央銀行
# 理監事聯席會議預定日期」新聞稿/公告頁面（WebSearch找到URL後WebFetch人工
# 核對逐日內容，非程式化API——理由同上方docstring）。**只記錄已用WebFetch
# 實際核對過內容、非僅搜尋引擎摘要的年份**；2015/2016/2017（民國104/105/
# 106年）搜尋引擎查無索引結果（可能需改查Wayback Machine或央行紙本檔案，
# 本輪未查到，誠實留空，不得用「每季第三個週X」規則反推——同一份docstring
# 已用2022-09-22（實際為第4個星期四而非規則宣稱的第3個）證偽這條規則）。
#
# 交叉驗證（跟上方RATE_CHANGES_2015_2024「已核對」欄位比對，全數一致，
# 提高本清單可信度）：
#   2022-03-17 / 2022-06-16 / 2022-09-22 / 2022-12-15 四筆會議日
#     與RATE_CHANGES_2015_2024對應事件的meeting_date欄位完全相同；
#   2023-03-23 對應RATE_CHANGES 2023-03-24生效事件的meeting_date="2023-03-23"；
#   2024-03-21 對應RATE_CHANGES 2024-03-22生效事件的meeting_date="2024-03-21"。
CBC_ALL_MEETING_DATES_BY_YEAR: dict[int, tuple[str, ...]] = {
    # 來源：cp-432-62606-94141-1.html（107年中央銀行理監事聯席會議預定日期）
    2018: ("2018-03-22", "2018-06-21", "2018-09-27", "2018-12-20"),
    # 來源：cp-357-76003-AC942-1.html（108年中央銀行理監事聯席會議預定日期）
    2019: ("2019-03-21", "2019-06-20", "2019-09-19", "2019-12-19"),
    # 來源：見 CBC_2020_ALL_MEETING_DATES（cp-357-104855-1ddb0-1，109年）
    2020: CBC_2020_ALL_MEETING_DATES,
    # 來源：cp-357-124983-e3b18-1.html / cp-302-124983-e3b18-1.html（110年）
    2021: ("2021-03-18", "2021-06-17", "2021-09-23", "2021-12-16"),
    # 來源：cp-302-145029-a6f8e-1.html（111年中央銀行理監事聯席會議預定日期）
    2022: ("2022-03-17", "2022-06-16", "2022-09-22", "2022-12-15"),
    # 來源：cp-302-157143-9a658-1.html（112年中央銀行理監事聯席會議預定日期）
    2023: ("2023-03-23", "2023-06-15", "2023-09-21", "2023-12-14"),
    # 來源：cp-302-164967-e38c7-1.html（113年中央銀行理監事聯席會議預定日期）
    2024: ("2024-03-21", "2024-06-13", "2024-09-19", "2024-12-19"),
}

# 已知缺口：2015/2016/2017（民國104/105/106年）尚未查到官方頁面，
# 下一輪待辦內容見 HYPOTHESIS_QUEUE.md #61 條目最新狀態段落。
MISSING_MEETING_YEARS: tuple[int, ...] = (2015, 2016, 2017)


def get_all_meeting_dates(start: str = "2015-01-01", end: str = "2024-12-31") -> list[str]:
    """回傳目前已核對過的完整會議日期清單（含持平），已知缺口見
    MISSING_MEETING_YEARS——呼叫端不得假設回傳結果涵蓋2015-2017。"""
    dates: list[str] = []
    for year_dates in CBC_ALL_MEETING_DATES_BY_YEAR.values():
        dates.extend(d for d in year_dates if start <= d <= end)
    return sorted(dates)


def get_rate_change_events(start: str = "2015-01-01", end: str = "2024-12-31") -> list[RateChangeEvent]:
    return [e for e in RATE_CHANGES_2015_2024 if start <= e.effective_date <= end]


if __name__ == "__main__":
    events = get_rate_change_events()
    print(f"共 {len(events)} 筆重貼現率變動事件（2015-01-01~2024-12-31）")
    for e in events:
        print(f"  {e.effective_date}  {e.direction:4s}  {e.prior_rate_pct}% -> {e.new_rate_pct}%  ({e.change_bp:+.1f}bp)  meeting_date={e.meeting_date}(verified={e.meeting_date_verified})")
    train = [e for e in events if e.effective_date <= "2020-12-31"]
    val = [e for e in events if e.effective_date >= "2021-01-01"]
    print(f"TRAIN(<=2020-12-31): {len(train)} 筆 / VAL(>=2021-01-01): {len(val)} 筆")

    all_dates = get_all_meeting_dates()
    print(f"\n完整會議日期（含持平）已核對年份: {sorted(CBC_ALL_MEETING_DATES_BY_YEAR.keys())}")
    print(f"  共 {len(all_dates)} 場會議，尚缺年份: {MISSING_MEETING_YEARS}")
    train_all = [d for d in all_dates if d <= "2020-12-31"]
    val_all = [d for d in all_dates if d >= "2021-01-01"]
    print(f"  TRAIN(<=2020-12-31): {len(train_all)} 場 / VAL(>=2021-01-01): {len(val_all)} 場")
