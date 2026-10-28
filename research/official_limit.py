# -*- coding: utf-8 -*-
"""前向追蹤共用：某檔某日的官方漲跌停價（先.一四一-1，模擬 J／N PREREG 修訂 R1）。

查價順序（零外部請求，只讀本機檔）：
1. 上櫃：前一交易日 TPEx 公告的「次日漲跌停價」——`research/data/tpex_limit_next/<data_date>.json`
   （`scripts/archive_tpex_limit_next.py` 從 git 歷史展開）＋工作目錄 `data/tpex_limit_next.json`；
   data_date 必須等於「前一交易日」才採用（價格適用於 data_date 的下一個交易日）。src＝`tpex_official`。
2. 其他（上市，或上櫃缺當天公告檔）：`tw_limit_price.limit_prices(基準價, 當日)`。
   基準價：當日是除權息日 → 原始前收 × `data/ex_dividend_events.json` 的 factor_applied（＝參考價 ÷ 前收）；
   當日是減資恢復買賣日 → 該筆 ref_price；都沒有 → 原始前收。基準來源記在 `base_src`。
   src＝`calc`；該代號出現在任何一份上櫃公告檔、但當天那份缺 → `calc_tpex_missing`（照 PREREG 記來源）。

已知限制（照實寫）：初次上市前五日無漲跌幅、ETF／權證檔位不在 `tw_limit_price` 範圍；兩支追蹤只做普通股。
自身失敗（檔案讀不到、算不出）回 None，呼叫端視為「不是漲跌停」並照常繼續（十二節）。非投資建議。
"""
from __future__ import annotations

import json
from pathlib import Path

import tw_limit_price

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
            lp = tw_limit_price.limit_prices(base, day)
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
