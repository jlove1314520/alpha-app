# -*- coding: utf-8 -*-
"""前向模擬看板欄位（先.一四七-0，Cowork 收件匣 036 A）。

各前向追蹤程式（paper_5～18）寫 data/paper_N.json 時呼叫 `board(series, ...)`，把 App「前向模擬」看板要的
數字一起寫進 json 的 `board` 欄，前端只讀、不寫死任何數字：
- nav_series：近 30 個交易日淨值 [[日期, 淨值], ...]（帳本每日 nav，或追蹤程式自己算的每日淨值）
- bench_0050：同一批日期的 0050 含息指數 [[日期, tr_index], ...]（research/data/bench_0050_tr.jsonl，先.一三五-1ib 甲）
- bench_0050_tr_pct：起跑日收盤到 as_of（取 ≤ as_of 最近一筆）的同期 0050 含息報酬（%）
- max_drawdown_pct：整段 series 的最大回撤（%，負數）
- n_holdings：目前持有檔數（呼叫端給）

零外部請求。自身任何失敗只回傳 {"error": ...}，呼叫端照樣寫檔（十二節：看板欄位壞了不准拖垮追蹤程式）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "research" / "data" / "bench_0050_tr.jsonl"
WINDOW = 30


def bench_index(path: Path | None = None) -> dict:
    """{日期: tr_index}；檔案不存在或壞行就略過（回空 dict 或部分）。"""
    out = {}
    try:
        for line in Path(path or BENCH).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("date") and isinstance(r.get("tr_index"), (int, float)):
                out[r["date"]] = float(r["tr_index"])
    except OSError:
        pass
    return out


def _le(idx: dict, dates: list, d: str):
    """≤ d 最近一筆 (日期, 值)；沒有回 (None, None)。dates 為已排序的 idx 鍵。"""
    best = None
    for x in dates:
        if x <= d:
            best = x
        else:
            break
    return (best, idx[best]) if best else (None, None)


def board(series, n_holdings: int | None = None, start: str | None = None, bench_path: Path | None = None) -> dict:
    """series：[(日期, 淨值), ...]（可亂序、同日多筆取最後一筆）。start：起跑日（預設＝series 第一天）。"""
    try:
        by_day = {}
        for d, v in series or []:
            if d and isinstance(v, (int, float)) and v > 0:
                by_day[str(d)] = float(v)
        days = sorted(by_day)
        if not days:
            return {"nav_series": [], "bench_0050": [], "bench_0050_tr_pct": None, "max_drawdown_pct": None,
                    "n_holdings": n_holdings, "note": "帳本還沒有淨值"}
        peak, mdd = 0.0, 0.0
        for d in days:
            v = by_day[d]
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)
        tail = days[-WINDOW:]
        idx = bench_index(bench_path)
        bdates = sorted(idx)
        bench_series = [[d, round(idx[d], 8)] for d in tail if d in idx]
        s0 = start or days[0]
        b0d, b0 = (s0, idx[s0]) if s0 in idx else (None, None)
        b1d, b1 = _le(idx, bdates, days[-1])
        pct = round((b1 / b0 - 1) * 100, 2) if b0 and b1 and b1d >= b0d else None
        return {"as_of": days[-1], "start": s0, "nav_start": round(by_day[days[0]], 4), "nav_series": [[d, round(by_day[d], 4)] for d in tail],
                "bench_0050": bench_series, "bench_0050_tr_pct": pct, "bench_from": b0d, "bench_to": b1d,
                "bench_source": "research/data/bench_0050_tr.jsonl（price_history 0050 還原收盤相鄰日比值累乘）",
                "max_drawdown_pct": round(mdd * 100, 2), "n_holdings": n_holdings,
                "nav_rebased_return_pct": round((by_day[days[-1]] / by_day[days[0]] - 1) * 100, 2)}
    except Exception as e:  # noqa: BLE001 — 十二節：看板欄位失敗只降級
        return {"error": f"{type(e).__name__}: {e}"}


def safe_board(*a, **kw) -> dict:
    try:
        return board(*a, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"[forward_board] 警告：看板欄位產生失敗（{type(e).__name__}: {e}）")
        return {"error": f"{type(e).__name__}: {e}"}
