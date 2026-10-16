"""先.一〇三-1b-1（2026-10-16）：一次性回補 data/market_tw.json 的 institutional_history
（與 institutional）缺少的 BFI82U 金額（*_net_amt，億元）。

用法：python .github/scripts/backfill_bfi82u_amt.py
- 只補還沒有 total_net_amt 的日期，最多 10 天（history 本來就只留 10 天）→ 最多 10 次請求。
- 節流沿用 fetch_market_tw 的 twse_rwd（同源間隔 ≥3 秒、402/403/428/429 封鎖 2 小時不重試）。
- 任一天失敗就略過該天、繼續下一天，最後照實印出哪幾天沒補到。
"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import fetch_market_tw as F  # 同目錄，共用同一套節流與解析


def main() -> int:
    data = json.loads(F.OUT_PATH.read_text(encoding="utf-8"))
    hist = data.get("institutional_history") or []
    todo = [h for h in hist if "total_net_amt" not in h][-10:]
    failed = []
    for h in todo:
        try:
            amt = F.fetch_institutional_amount(h["date"])
        except Exception as e:
            print(f"{h['date']} 失敗：{e}")
            failed.append(h["date"])
            if "封鎖" in str(e):
                break
            continue
        if amt is None:
            print(f"{h['date']} 官方無資料")
            failed.append(h["date"])
            continue
        F.merge_institutional_amount(h, amt)
        print(f"{h['date']} 合計 {amt['total_net_amt']} 億（外資 {amt['foreign_net_amt']}／投信 {amt['trust_net_amt']}／自營 {amt['dealer_net_amt']}）")
    inst = data.get("institutional")
    if inst:
        same = next((h for h in hist if h.get("date") == inst.get("date") and "total_net_amt" in h), None)
        if same:
            inst.update({k: v for k, v in same.items() if k.endswith("_amt") or k.startswith("amt_")})
    F.OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"補了 {len(todo) - len(failed)}／{len(todo)} 天；未補：{failed or '無'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
