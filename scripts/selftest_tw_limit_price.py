# -*- coding: utf-8 -*-
"""先.一三五-1ab 自測：上市漲跌停價計算（原 research/tw_limit_price.py，收件匣 032 起併進 research/official_limit.py）。

全部用合成數字（官方文件範例＋跨級距邊界值），不讀任何真實價格、不呼叫網路。
範例來源見 docs/DATA_SOURCE_MAP.md「上市漲跌幅與升降單位取整方向」節。
"""
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import official_limit as t  # noqa: E402  （收件匣 032：規則已併進 official_limit）

results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def lp(base, d, up, down):
    r = t.limit_prices(base, d)
    ok = r["up"] == Decimal(up) and r["down"] == Decimal(down)
    check(f"{d} 基準 {base} → 漲停 {r['up']}／跌停 {r['down']}（預期 {up}／{down}）", ok)


# ① 證期局月刊 96-04 範例（7%）：40.5 → 43.30／37.70
lp("40.5", "2010-01-04", "43.30", "37.70")
# ② 證交所交易制度頁範例（10%）：40.60 → 44.65／36.55
lp("40.60", "2020-01-02", "44.65", "36.55")
# ③ 1p-a 櫃買官方實測的跨級距例（7%，取結果級距檔位）：98.00 → 104.5；485 → 518
lp("98.00", "2010-01-04", "104.5", "91.2")
lp("485", "2010-01-04", "518", "451.5")
# ④ 10% 跨級距邊界
lp("48", "2020-01-02", "52.8", "43.2")        # 52.8 落在 50～100（0.1）
lp("9.5", "2020-01-02", "10.45", "8.55")      # 10.45 落在 10～50（0.05）
lp("9.99", "2020-01-02", "10.95", "9.00")     # 10.989→10.95；8.991→9.00
lp("920", "2020-01-02", "1010", "828")        # 1012→1010（5 元檔）
lp("1050", "2020-01-02", "1155", "945")       # 945 落在 500～1000（1 元）
lp("1100", "2020-01-02", "1210", "990")
lp("55.5", "2020-01-02", "61.0", "49.95")     # 61.05→61.0；49.95 恰為 −10% 且是 0.05 檔合法價
lp("55.4", "2020-01-02", "60.9", "49.90")     # 49.86 落在 10～50（0.05）→ 往上取 49.90
# ⑤ 2015-06-01 切換
lp("100", "2015-05-29", "107.0", "93.0")
lp("100", "2015-06-01", "110.0", "90.0")
# ⑥ 第 63 條：幅度未滿一檔按一檔計、最低到 0.01
lp("0.05", "2020-01-02", "0.06", "0.04")
lp("0.01", "2020-01-02", "0.02", "0.01")
# ⑦ 結果一定是合法檔位、漲停不超過 +幅度、跌停不低於 −幅度（掃 0.01～1,500 合成網格）
bad = 0
n = 0
for cents in list(range(1, 100000, 7)) + list(range(100000, 150000, 97)):
    b = Decimal(cents) / 100
    for d in ("2010-01-04", "2020-01-02"):
        r = t.limit_prices(b, d)
        n += 1
        up, dn, rate = r["up"], r["down"], r["rate"]
        tu, td = t.tick_size(up, d), t.tick_size(dn, d)
        wide = b * rate >= t.tick_size(b, d)
        if (up % tu != 0 or dn % td != 0
                or (wide and (up > b * (1 + rate) or dn < b * (1 - rate)))
                or up <= b or (dn >= b and b > Decimal("0.01"))):
            bad += 1
check(f"合成網格 {n} 組：檔位合法、不超過幅度、漲停>基準>跌停（違規 {bad}）", bad == 0)
# ⑧ 未驗證日期預設拒算
try:
    t.limit_prices("50", "2006-01-02")
    check("2007-04-16 前預設拒算", False)
except ValueError:
    check("2007-04-16 前預設拒算", True)
r = t.limit_prices("50", "2006-01-02", allow_unverified=True)
check("allow_unverified=True 會算並標 verified=False", r["verified"] is False)
# ⑨ 1,000 元以上新制尚未公告：仍用 5 元
check("1,000 元以上升降單位仍 5 元（新制未公告）", t.tick_size("1200", "2026-10-28") == Decimal("5"))

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} PASS")
sys.exit(1 if fails else 0)
