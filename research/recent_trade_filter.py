# -*- coding: utf-8 -*-
"""選股榜「近期無成交」判定（2026-10-13 總司令【先.八十二】3 裁示②，2026-10-14 生效）。

規則：下列任一成立 → 排名留空（rank=null）、flags 加「近期無成交」，做法同「流動性不足」（仍留在清單供搜尋）。
  ① 近 5 個交易日（市場日曆＝0050 最近 5 個有資料的日子）沒有任何一天成交量 > 0。
  ② 不在官方最新快照：該股最後一筆日期早於最新交易日。
     只在「最新交易日的全市場檔數 ≥ 近 5 日中位數 90%」時才套用——上櫃資料偶爾整批晚一天，
     那天整個上櫃都會「不在快照」，不能因此全部剔除（判不了就不剔除，fail open）。
實例：3085（9/30 後無成交）、8183（10/01 後官方表找不到）。
只讀 price_history，不打網路。
"""
from __future__ import annotations

from statistics import median

FLAG = "近期無成交"
N_DAYS = 5
SNAPSHOT_COMPLETE_RATIO = 0.9
CALENDAR_PROXY = "0050"
EFFECTIVE_DATE = "2026-10-14"  # 裁示：picks_ledger 標生效日 2026-10-14；資料日早於此日不剔除（只回報「會剔除」幾檔）


def evaluate(prices: dict, n_days: int = N_DAYS) -> tuple[dict, dict]:
    """回傳 ({代號: 原因}, 判定資訊)。prices＝price_history 的 prices。"""
    cal = sorted({r.get("date") for r in (prices.get(CALENDAR_PROXY) or []) if r.get("date")})
    if len(cal) < n_days:
        return {}, {"applied": False, "reason": f"{CALENDAR_PROXY} 交易日不足 {n_days} 天，未套用"}
    window = cal[-n_days:]
    latest = window[-1]
    wset = set(window)
    counts = {d: 0 for d in window}
    for rows in prices.values():
        for r in rows[-(n_days + 5):]:
            d = r.get("date")
            if d in counts:
                counts[d] += 1
    med = median(counts.values()) if counts else 0
    snap_ok = bool(med) and counts[latest] >= SNAPSHOT_COMPLETE_RATIO * med
    out = {}
    for code, rows in prices.items():
        if not rows:
            continue
        traded = any((r.get("date") in wset) and (r.get("volume") or 0) > 0 for r in rows[-(n_days + 5):])
        last = rows[-1].get("date")
        if not traded:
            out[code] = f"近 {n_days} 個交易日（{window[0][5:]}～{latest[5:]}）無成交，最後成交 {last}"
        elif snap_ok and last and last < latest:
            out[code] = f"不在官方最新快照（{latest[5:]}），最後一筆 {last}"
    active = latest >= EFFECTIVE_DATE
    info = {"applied": active, "window": window, "latest": latest, "latest_count": counts[latest],
            "median_count": med, "snapshot_check": snap_ok, "excluded": len(out) if active else 0,
            "would_exclude": len(out), "effective_date": EFFECTIVE_DATE}
    return (out if active else {}), info
