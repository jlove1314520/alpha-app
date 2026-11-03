# -*- coding: utf-8 -*-
"""0050 含息日序列持續累積（先.一三五-1ib 甲，[預設放行] 2026-11-04，Cowork 可推翻）。

為什麼：14 支前向模擬判定都要比「同期 0050 含息」，但 repo 沒有一條會持續更新到判定日（2027-11～2030-01）的序列
（官方淨值 csv 停 2024-12-31、data/price_history 只留 90 日、紙.一帳本每月原始收盤不含息）。

做法：每班讀 data/price_history 的 0050，用「同一版內」今天 adj_close ÷ 前一交易日 adj_close 得當日含息報酬，
append-only 累乘寫進 research/data/bench_0050_tr.jsonl（每個交易日一列）。
- 同一版內相除：price_history 除息時會回溯改寫舊 adj_close，跨版本相除會錯；同版相鄰兩天比值才是含息報酬
  （2026-07-21 除息日查證：adj/close 比值由 0.993952 跳到 1.0）。
- 同日只寫一次：只處理帳本最後日期之後的交易日；漏跑的日子只要還在 90 日視窗內就依序補。
- 斷檔不硬接：帳本最後日期已滾出視窗（或視窗內找不到）→ 不寫、印警告、摘要寫 last_error，不猜。
- 壞檔不覆蓋：既有帳本任何一行讀不出 JSON → 整支不寫、告警（十二節：自身失敗只警告、exit 0）。
- adj_close 為 0（零成交）或缺值 → 補到那天之前為止，不跳過不猜。
零外部請求；只讀 repo 既有檔。自測：scripts/selftest_bench_0050_tr.py。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

TW = timezone(timedelta(hours=8))
CODE = "0050"
LEDGER = ROOT / "research" / "data" / "bench_0050_tr.jsonl"
SOURCE = "data/price_history adj_close 同版相鄰日比值"


def read_ledger(path: Path) -> list:
    """讀帳本；任何一行壞掉就拋錯（呼叫端不覆蓋）。"""
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as e:
            raise RuntimeError(f"{path.name} 第 {i} 行不是合法 JSON，不覆蓋：{e}") from e
    return rows


def _valid(r) -> bool:
    try:
        return float(r.get("adj_close") or 0) > 0
    except (TypeError, ValueError):
        return False


def plan(rows: list, ledger: list) -> tuple[list, str | None]:
    """回傳（要 append 的新列, 警告）。rows＝price_history 0050 同一版的列。"""
    rows = sorted((r for r in rows if r.get("date")), key=lambda r: r["date"])
    if not rows:
        return [], "price_history 沒有 0050"
    new = []
    if not ledger:
        first = next((r for r in rows if _valid(r)), None)
        if first is None:
            return [], "price_history 0050 沒有有效 adj_close"
        rec = {"date": first["date"], "kind": "inception", "tr_index": 1.0,
               "adj_close": float(first["adj_close"]), "close": first.get("close"), "source": SOURCE}
        new.append(rec)
        last_date, last_tr = rec["date"], 1.0
    else:
        last = ledger[-1]
        last_date, last_tr = last["date"], float(last["tr_index"])
    idx = next((i for i, r in enumerate(rows) if r["date"] == last_date), None)
    if idx is None:
        if rows[-1]["date"] <= last_date:
            return new, None
        return new, f"帳本最後日期 {last_date} 不在 price_history 0050 視窗（{rows[0]['date']}～{rows[-1]['date']}），斷檔不硬接"
    prev = rows[idx]
    if not _valid(prev):
        return new, f"{last_date} adj_close 無效，無法接續"
    warn = None
    for r in rows[idx + 1:]:
        if not _valid(r):
            warn = f"{r['date']} adj_close 無效（零成交或缺值），補到前一天為止"
            break
        ret = float(r["adj_close"]) / float(prev["adj_close"])
        last_tr = last_tr * ret
        new.append({"date": r["date"], "kind": "day", "prev_date": prev["date"],
                    "ret": round(ret - 1.0, 10), "tr_index": round(last_tr, 10),
                    "adj_close": float(r["adj_close"]), "close": r.get("close"), "source": SOURCE})
        prev = r
    return new, warn


def append_atomic(path: Path, existing_text: str, new: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = existing_text
    if body and not body.endswith("\n"):
        body += "\n"
    body += "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def run(rows: list, path: Path) -> dict:
    ledger = read_ledger(path)  # 壞檔在這裡拋錯
    new, warn = plan(rows, ledger)
    if new:
        append_atomic(path, path.read_text(encoding="utf-8") if path.exists() else "", new)
    return {"appended": len(new), "last_date": (new or ledger or [{}])[-1].get("date"), "warning": warn}


def main() -> int:
    try:
        import price_history_store as PHS
        prices = PHS.load(ROOT / "data" / "price_history.json").get("prices") or {}
        res = run(prices.get(CODE) or [], LEDGER)
        print(f"[bench_0050_tr] {datetime.now(TW):%Y-%m-%d %H:%M} 新增 {res['appended']} 列，最後日期 {res['last_date']}")
        if res["warning"]:
            print(f"::warning::bench_0050_tr {res['warning']}")
    except Exception as e:  # noqa: BLE001 — 十二節：自身失敗只警告，不擋 market.yml 後續步驟
        print(f"::warning::bench_0050_tr 失敗（未寫檔）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
