# -*- coding: utf-8 -*-
"""前向追蹤共用：某檔某日的官方漲跌停價（先.一四一-1，模擬 J／N PREREG 修訂 R1）。

查價順序（零外部請求，只讀本機檔）：
1. 上櫃：前一交易日 TPEx 公告的「次日漲跌停價」——`research/data/tpex_limit_next/<data_date>.json`
   （`scripts/archive_tpex_limit_next.py` 從 git 歷史展開）＋工作目錄 `data/tpex_limit_next.json`；
   data_date 必須等於「前一交易日」才採用（價格適用於 data_date 的下一個交易日）。src＝`tpex_official`。
2. 其他（上市，或上櫃缺當天公告檔）：本檔下半的 `limit_prices(基準價, 當日)`（原 `tw_limit_price.py`，見文末規則段）。
   基準價：當日是除權息日 → 原始前收 × `data/ex_dividend_events.json` 的 factor_applied（＝參考價 ÷ 前收）；
   當日是減資恢復買賣日 → 該筆 ref_price；都沒有 → 原始前收。基準來源記在 `base_src`。
   src＝`calc`；該代號出現在任何一份上櫃公告檔、但當天那份缺 → `calc_tpex_missing`（照 PREREG 記來源）。

已知限制（照實寫）：初次上市前五日無漲跌幅、ETF／權證檔位不在本檔檔位表範圍；兩支追蹤只做普通股。
自身失敗（檔案讀不到、算不出）回 None，呼叫端視為「不是漲跌停」並照常繼續（十二節）。非投資建議。

收件匣 032（2026-10-30，先.一三五-1ar-a 採甲）：原 `research/tw_limit_price.py`（純規則）併進本檔，前向追蹤（模擬 I／J／N／Q／R）與自測一律 `import official_limit`；`tw_limit_price.py` 只剩轉接殼（舊 PREREG 文字引用的名稱仍可用），**改規則／填 `TICK_1000_TO_1_EFFECTIVE` 只改本檔**。

── 以下為原 tw_limit_price.py 規則說明（純函式、不讀檔、不打網路） ──

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

import json
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

# ── 官方漲跌停價規則（原 tw_limit_price.py，先.一三五-1ab） ──
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


# ── 前向追蹤查價（上櫃公告優先、基準價換算） ──
ROOT = Path(__file__).resolve().parent.parent
TPEX_CUR = ROOT / "data" / "tpex_limit_next.json"
TPEX_ARCHIVE = ROOT / "research" / "data" / "tpex_limit_next"
EXDIV = ROOT / "data" / "ex_dividend_events.json"
EPS = 1e-9


def _load(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        if Path(p).exists():
            print(f"[warn] official_limit 讀不到 {p}：{e!r}")
        return None


class OfficialLimits:
    def __init__(self, tpex_docs: list | None = None, exdiv: dict | None = None):
        if tpex_docs is None:
            tpex_docs = []
            if TPEX_ARCHIVE.is_dir():
                tpex_docs += [d for d in (_load(p) for p in sorted(TPEX_ARCHIVE.glob("*.json"))) if d]
            cur = _load(TPEX_CUR)
            if cur:
                tpex_docs.append(cur)
        self.tpex: dict[str, dict] = {}
        for d in tpex_docs:
            if isinstance(d, dict) and d.get("data_date") and isinstance(d.get("rows"), dict):
                self.tpex.setdefault(d["data_date"], d["rows"])  # 同日先到先用（歸檔檔排在工作目錄那份前）
        self.tpex_codes = {c for rows in self.tpex.values() for c in rows}
        if exdiv is None:
            exdiv = _load(EXDIV) or {}
        self.ex_factor: dict[tuple, float] = {}
        for c, lst in (exdiv.get("events") or {}).items():
            for e in lst or []:
                if e.get("ex_date") and e.get("factor_applied"):
                    self.ex_factor[(str(c), e["ex_date"])] = float(e["factor_applied"])
        self.red_ref: dict[tuple, float] = {}
        for c, lst in (exdiv.get("reductions") or {}).items():
            for e in lst or []:
                if e.get("resume_date") and e.get("ref_price"):
                    self.red_ref[(str(c), e["resume_date"])] = float(e["ref_price"])

    def limits(self, code: str, day: str, prev_day: str | None, raw_prev_close) -> dict | None:
        """回傳 {'up','down','src','base','base_src'}（float）；算不出回 None。prev_day＝前一交易日。"""
        code = str(code)
        try:
            rows = self.tpex.get(prev_day) if prev_day else None
            v = (rows or {}).get(code)
            if v and len(v) >= 2 and v[0] and v[1]:
                return {"up": float(v[0]), "down": float(v[1]), "src": "tpex_official", "base": None,
                        "base_src": f"tpex_limit_next@{prev_day}"}
            if not raw_prev_close or float(raw_prev_close) <= 0:
                return None
            pc = float(raw_prev_close)
            if (code, day) in self.red_ref:
                base, base_src = self.red_ref[(code, day)], "reduction_ref"
            elif (code, day) in self.ex_factor:
                base, base_src = round(pc * self.ex_factor[(code, day)], 4), "exdiv_ref"
            else:
                base, base_src = pc, "raw_prev_close"
            lp = limit_prices(base, day)
            return {"up": float(lp["up"]), "down": float(lp["down"]),
                    "src": "calc_tpex_missing" if code in self.tpex_codes else "calc", "base": base, "base_src": base_src}
        except Exception as e:  # noqa: BLE001 —— 十二節：守門員自身失敗只警告
            print(f"[warn] official_limit {code} {day} 算不出漲跌停價：{e!r}")
            return None


def lock_status(lim: dict | None, o, h, l, c) -> tuple[bool, bool]:
    """原始開高低收全在漲停價（含）以上＝鎖漲停；全在跌停價（含）以下＝鎖跌停。lim 為 None → 都不算。"""
    if not lim or any(x is None for x in (o, h, l, c)):
        return False, False
    vals = [float(x) for x in (o, h, l, c)]
    return all(x >= lim["up"] - EPS for x in vals), all(x <= lim["down"] + EPS for x in vals)
