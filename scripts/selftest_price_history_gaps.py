"""先.五十七-A2：Bb-90 白名單三檔（0050、00646、00697B）在 data/price_history.json 最近 60 個交易日不得有缺日（官方休市日除外）。
休市日以本機官方日曆快取為準；讀不到日曆時 SKIP 並警告（不可用猜的）。"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
import auto_rebalance_bb90 as A  # noqa: E402

fails = []
px = json.loads((ROOT / "data" / "price_history.json").read_text(encoding="utf-8"))["prices"]
last = max(px[c][-1]["date"] for c in A.WEIGHTS)
y = int(last[:4])
cals = {yy: A.load_calendar(yy, A.DEFAULT_DIR) for yy in (y, y - 1)}
if any(c is None for c in cals.values()):
    print("SKIP 讀不到官方日曆快取，無法判斷交易日——[警告] 本項未驗證")
    sys.exit(0)
closed = set(cals[y]["closed"]) | set(cals[y - 1]["closed"])
days, x = [], date.fromisoformat(last)
while len(days) < 60:
    if x.weekday() < 5 and x.isoformat() not in closed:
        days.append(x.isoformat())
    x -= timedelta(days=1)
for c in A.WEIGHTS:
    have = {r["date"] for r in px.get(c, [])}
    miss = [d for d in days if d not in have]
    ok = not miss
    print(("PASS " if ok else "FAIL ") + f"{c} 最近 60 個交易日（{days[-1]}～{days[0]}）無缺日" + ("" if ok else f"：缺 {len(miss)} 天 {miss[:8]}"))
    if not ok:
        fails.append(c)
print("失敗：", fails if fails else "無")
sys.exit(1 if fails else 0)
