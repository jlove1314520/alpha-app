# -*- coding: utf-8 -*-
"""上市股票官方漲跌停價計算（先.一三五-1ab，只建不接）。

規則來源（全部抄自 `docs/DATA_SOURCE_MAP.md`「上市漲跌幅與升降單位取整方向」節，
先.一三五-1p／1p-a／1p-b 查證，2026-10-28）：

1. 升降單位（營業細則第 62 條，115.09.24 版）：未滿 10 元 0.01／10～未滿 50 元 0.05／
   50～未滿 100 元 0.1／100～未滿 500 元 0.5／500～未滿 1,000 元 1／1,000 元以上 5。
   2026-08-25 董事會通過的「1,000 元以上改 1 元」**官方尚未公告生效日**（1p-b），
   這裡一律用 5 元；公告後在 `TICK_1000_TO_1_EFFECTIVE` 填日期即可分段。
2. 漲跌幅（第 63 條＋櫃買中心頁）：2015-06-01 前 7%、當日起 10%。
3. 取整方向（證期局月刊 96-04 範例、證交所交易制度頁 40.60 範例）：
   漲停向下取、跌停向上取，都不超過幅度。
4. 跨級距（1p-a，用櫃買 2007H2 官方「次日漲停價／次日跌停價」實測 5,841／5,886 列）：
   取整用「計算出的漲跌停價所在級距」的檔位，不是基準價的級距。
   ⚠️ 這條是上櫃 7% 時期實測，上市與 10% 時期未另行實測（條文兩市場相同，[自行裁量] 視為同一規則）。
5. 第 63 條：幅度未滿最小升降單位者按最小升降單位計；價格以跌至最小升降單位為限。

不涵蓋（呼叫端自己處理）：
- 基準價：一般是前一日收盤；除權息日要用第 67 條參考價（本函式只吃「基準價」，不幫你換）。
- 初次上市普通股前五個交易日無漲跌幅、ETF／權證等其他商品的檔位。
- 上櫃：官方日檔已有「次日漲停價／次日跌停價」（先.一三五-1m-a），直接用官方值。

升降單位六級的最早適用日：已驗證來源最早是 2007-04-16 的證期局月刊，更早的檔位表未查證，
`VERIFIED_FROM` 之前的日期預設拒算（`allow_unverified=True` 才算，結果自行標「未驗證」）。

純函式、不讀檔、不打網路。非投資建議。
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

# 2015-06-01 起漲跌幅 7% → 10%（第 63 條、櫃買中心「漲跌幅度」頁）
LIMIT_10PCT_FROM = date(2015, 6, 1)
# 六級升降單位已驗證的最早日期（證期局《證券暨期貨月刊》第 25 卷第 4 期，96-04-16）
VERIFIED_FROM = date(2007, 4, 16)
# 第 62 條 1,000 元以上 5 元→1 元：官方尚未公告生效日（1p-b，2026-10-28 查證）
TICK_1000_TO_1_EFFECTIVE: date | None = None

_TIERS = (  # (未滿此價, 升降單位)
    (Decimal("10"), Decimal("0.01")),
    (Decimal("50"), Decimal("0.05")),
    (Decimal("100"), Decimal("0.1")),
    (Decimal("500"), Decimal("0.5")),
    (Decimal("1000"), Decimal("1")),
)
MIN_TICK = Decimal("0.01")


def _to_date(d) -> date:
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def tick_size(price, on_date) -> Decimal:
    """第 62 條升降單位；price 是「該價位本身」，跨級距時要傳計算出的漲跌停價。"""
    p = Decimal(str(price))
    for upper, tick in _TIERS:
        if p < upper:
            return tick
    d = _to_date(on_date)
    if TICK_1000_TO_1_EFFECTIVE is not None and d >= TICK_1000_TO_1_EFFECTIVE:
        return Decimal("1")
    return Decimal("5")


def limit_rate(on_date) -> Decimal:
    return Decimal("0.10") if _to_date(on_date) >= LIMIT_10PCT_FROM else Decimal("0.07")


def _snap(raw: Decimal, on_date, rounding) -> Decimal:
    tick = tick_size(raw, on_date)
    return (raw / tick).to_integral_value(rounding=rounding) * tick


def limit_prices(base, on_date, *, allow_unverified: bool = False) -> dict:
    """回傳 {'up': Decimal, 'down': Decimal, 'rate': Decimal, 'verified': bool}。

    base：開盤競價基準（一般為前收；除權息日請傳參考價）。on_date：交易日（date 或 'YYYY-MM-DD'）。
    """
    d = _to_date(on_date)
    verified = d >= VERIFIED_FROM
    if not verified and not allow_unverified:
        raise ValueError(f"{d} 早於已驗證的檔位表起點 {VERIFIED_FROM}，需 allow_unverified=True")
    b = Decimal(str(base))
    if b <= 0:
        raise ValueError(f"基準價必須 > 0：{base}")
    rate = limit_rate(d)
    base_tick = tick_size(b, d)
    if b * rate < base_tick:
        # 第 63 條：幅度未滿最小升降單位者，按最小升降單位計
        up = b + base_tick
        down = b - base_tick
    else:
        up = _snap(b * (1 + rate), d, ROUND_FLOOR)
        down = _snap(b * (1 - rate), d, ROUND_CEILING)
    # 第 63 條：價格以跌至最小升降單位為限
    if down < MIN_TICK:
        down = MIN_TICK
    return {"up": up, "down": down, "rate": rate, "verified": verified}
