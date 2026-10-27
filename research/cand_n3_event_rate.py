# -*- coding: utf-8 -*-
"""候選 N3（重大訂單／得標公告後漂移，前向）事件抽取＋事件率量測（先.一三五-1c ①）。

草稿：docs/PREREG_DRAFT_ORDER_WIN_DRIFT_FORWARD.md §2（標題規則與排除字照草稿原文寫死；不用 type 分類欄）。
- 只讀 data/events.json 標題、在市名冊、休市日曆；**不讀任何價格、不算任何報酬、零外部請求**。
- 輸出 research/data/cand_n3_event_rate.json（含每則標題，供歸檔滿 60 則時的精準度稽核）。
- 共用 cand_n2_event_rate.py 的抽取／去重／彙總函式，只換規則與去重窗口（20 個交易日）。
自測：python research/cand_n3_event_rate.py --selftest
"""
from __future__ import annotations

import re
import sys

import cand_n2_event_rate as N2

OUT = N2.ROOT / "research" / "data" / "cand_n3_event_rate.json"
INCLUDE = re.compile(r"(取得|接獲|簽訂|簽署|得標|承攬).{0,20}(訂單|採購案|標案|銷售合約|供貨合約|銷售契約|供貨契約|工程承攬|承攬契約|承攬案)|得標")
EXCLUDE = ("修正", "追加", "追減", "結束日", "更正", "關係人", "資安", "外洩", "轉換公司債", "澄清", "媒體", "報導",
           "取消", "解除", "終止", "延後", "訴訟", "通知")
DEDUP_TD = 20


def main() -> int:
    N2.run(OUT, INCLUDE, EXCLUDE, DEDUP_TD, "先.一三五-1c ①", "docs/PREREG_DRAFT_ORDER_WIN_DRIFT_FORWARD.md",
           "精準度稽核（滿 60 則、只看標題）不在本步驟做；這裡的標題清單只是歸檔，未逐則判定。")
    return 0


def selftest() -> int:
    m = lambda t: N2.match_title(t, INCLUDE, EXCLUDE)  # noqa: E731
    assert m("公告本公司接獲大額訂單")
    assert m("本公司得標台電工程")
    assert m("代子公司簽訂銷售合約")
    assert not m("更正本公司接獲訂單金額")
    assert not m("公告本公司遭受資安攻擊")
    assert not m("本公司取得不動產")
    raw = [
        {"code": "2330", "date": "2026-09-07", "title": "公告接獲訂單", "source": "TWSE 重大訊息"},
        {"code": "2330", "date": "2026-09-21", "title": "公告接獲另一筆訂單", "source": "TWSE 重大訊息"},  # 20 交易日內
        {"code": "2330", "date": "2026-10-20", "title": "公告得標", "source": "TPEx 重大訊息"},  # 20 交易日後
    ]
    ev, dropped = N2.extract(raw, set(), INCLUDE, EXCLUDE, DEDUP_TD)
    assert [e["date"] for e in ev] == ["2026-09-07", "2026-10-20"] and dropped == 1, ev
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
