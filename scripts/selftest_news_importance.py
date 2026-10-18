# -*- coding: utf-8 -*-
"""先.一一〇-9 新聞／官方事件重要度 v0 自測（不連網）：權重表照草案、範圍、上限。"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".github" / "scripts"))
from news_importance import event_importance, news_importance  # noqa: E402

fails: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        fails.append(label)


check(news_importance({"title": "台股收盤", "codes": []}) == 2, "新聞基礎 2 分")
check(news_importance({"title": "台積電法說", "codes": ["2330"]}) == 5, "有代號 +1、法說 +2")
check(news_importance({"title": "某公司併購案並上修財測", "codes": ["1234"]}) == 7, "關鍵字只取最高一項（併購 4）")
check(news_importance({"title": "接獲大訂單", "codes": []}) == 5, "訂單 +3")
check(event_importance({"type": "重大訂單"}) == 9 and event_importance({"type": "併購"}) == 9, "官方 重大訂單／併購 9 分")
check(event_importance({"type": "財務"}) == 8 and event_importance({"type": "停復牌"}) == 8, "官方 財務／停復牌 8 分")
check(all(event_importance({"type": t}) == 7 for t in ("增減資", "訴訟", "處分資產", "法說會")), "官方 增減資／訴訟／處分資產／法說會 7 分")
check(event_importance({"type": "月營收"}) == 6, "官方 月營收 6 分")
check(all(event_importance({"type": t}) == 5 for t in ("除權息", "人事", "其他", "沒見過的類型", None)), "官方 除權息／人事／其他（含未知）5 分")
check(all(5 <= event_importance({"type": t}) <= 9 for t in ("重大訂單", "月營收", "其他")), "官方事件落在 5～9")
print(f"\n{'全部通過' if not fails else f'失敗 {len(fails)} 項'}")
sys.exit(1 if fails else 0)
