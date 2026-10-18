# -*- coding: utf-8 -*-
"""新聞／官方事件重要度（importance，0～10）v0。

2026-10-18 總司令【先.一一〇】9 裁示：權重表照 先.一〇九-41 草案當 v0；App 不用固定門檻收合，
改成每個區塊顯示分數最高的 5 則、其餘收進「看全部 N 則」；events.json 的官方重大訊息一起納入（5～9 分）。

權重表 v0（數字是草案拍板值，改動要另經裁示）：
- 新聞（data/news.json，大眾媒體 RSS）：基礎 2＋標題有點名代號 1＋標題關鍵字最高一項
  （併購 4／財測 3／訂單 3／財報 2／法說 2），上限 10。實際分布約 2～7。
- 官方事件（data/events.json，TWSE／TPEx 重大訊息等）：基礎 4＋類型
  （重大訂單／併購 5、財務／停復牌 4、增減資／訴訟／處分資產／法說會 3、月營收 2、除權息／人事／其他 1）→ 5～9。
  沒列到的類型當「其他」（1）。
同一套規則在 fetch_news_events.py（寫 news.json／news_by_code／events.json）與 split_events_by_code.py
（寫 events_by_code）共用，App 只讀欄位、不自己算。
"""
from __future__ import annotations

NEWS_BASE = 2
NEWS_CODE_BONUS = 1
NEWS_KEYWORDS = (("併購", 4), ("財測", 3), ("訂單", 3), ("財報", 2), ("法說", 2))
EVENT_BASE = 4
EVENT_TYPE_WEIGHT = {
    "重大訂單": 5, "併購": 5,
    "財務": 4, "停復牌": 4,
    "增減資": 3, "訴訟": 3, "處分資產": 3, "法說會": 3,
    "月營收": 2,
    "除權息": 1, "人事": 1, "其他": 1,
}
VERSION = "v0（2026-10-18 先.一一〇-9）"


def news_importance(item: dict) -> int:
    title = str(item.get("title") or "")
    kw = max((w for k, w in NEWS_KEYWORDS if k in title), default=0)
    return min(10, NEWS_BASE + (NEWS_CODE_BONUS if item.get("codes") else 0) + kw)


def event_importance(ev: dict) -> int:
    return min(10, EVENT_BASE + EVENT_TYPE_WEIGHT.get(str(ev.get("type") or "其他"), EVENT_TYPE_WEIGHT["其他"]))
