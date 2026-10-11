"""先.七十六（2026-10-11）：「跟 0050 比」卡的歷史段 → data/strategy_history.json（只讀既有結果檔，不重算、不重跑、不新開試驗）。

每條策略線分三段：
  回測段（2003-07～2024-12）：用來挑策略的資料。來源結果檔**只存年化／最大跌幅等摘要數字，沒有逐月序列**，
      所以本檔只搬摘要數字；App 不畫回測曲線（沒有資料就不畫，也不拿年化去畫一條假的直線）。
  樣本外段（2025-01～2026-09-30）：只考過一次。#423／#425（Bb-90、70/30、0050）、#427／#428（S3-C6）的逐月報酬原樣搬過來。
  紙上段（2026-10-08 起）：今天起才算數——由 data/strategy_curves.json 提供（本檔不碰）。
0050 全程灰線：回測段摘要（R1 結果檔的 0050 buy-hold）＋樣本外逐月（#425 的 0050_hold）。

所有數字都標來源檔＋JSON 路徑，冒煙 96 會回頭比對原檔（年化 ±0.05pp）。零外部請求；自身失敗只警告（十二節）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RD = ROOT / "research" / "data"
OUT = ROOT / "data" / "strategy_history.json"
TZ = timezone(timedelta(hours=8))

LABELS = {"backtest": "回測＝用來挑策略的資料", "oos": "樣本外＝只考過一次", "paper": "紙上＝今天起才算數"}
PAPER_START = "2026-10-08"

# 線 id → 各段來源（檔名、JSON 路徑、事前登記／結果試驗編號、附註）
SPEC = {
    "live_bb90": {
        "backtest": ("core_allocation_result.json", ["grid", "Bb-90"], "#417／#418", "核心配置 24 格點的 Bb-90（45% 0050＋45% VTI＋10% IEF）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "Bb-90"], "#423／#425", "美股腿用 VTI／IEF；真錢版改用 00646／00697B"),
    },
    "paper_1": {
        "backtest": ("core_allocation_result.json", ["grid", "Aa-70"], "#417／#418", "70% 0050＋30% 定存（核心配置基準 Aa-70）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "paper1_70_30"], "#423／#425", ""),
    },
    "paper_3": {
        "backtest": ("crisis_gate_leveraged_bb90_result.json", ["trials", "S3-C6", "stats"], "#424／#426", ""),
        "oos": ("s3c6_oos_2025_result.json", ["results", "S3-C6_real"], "#427／#428", "槓桿腿用 00631L／00647L 真實價"),
    },
    "paper_4": {
        "backtest": ("r1_0050_credit_gate_result.json", ["trials", "R1-C", "stats"], "#429／#430", "R1 沒有做樣本外單發，只有回測段"),
    },
    "paper_1b": {
        "backtest": ("core_allocation_result.json", ["grid", "Bb-90"], "#417／#418", "同族 Bb-90（回測美股腿用 VTI／IEF）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "Bb-90"], "#423／#425", "同族 Bb-90（美股腿用 VTI／IEF）"),
    },
}
BENCH = {
    "backtest": ("r1_0050_credit_gate_result.json", ["benchmark_0050_buy_hold"], "#429／#430", "0050 買進持有（還原息）"),
    "oos": ("bb90_oos_2025_result.json", ["results", "0050_hold"], "#423／#425", ""),
}


def _get(doc, path):
    for k in path:
        doc = doc[k]
    return doc


def _period(doc):
    p = doc.get("period")
    if isinstance(p, dict):
        return [p.get("start"), p.get("end")]
    if isinstance(p, list):
        return p[:2]
    return [None, None]


def _seg(kind, spec):
    fname, path, trials, note = spec
    doc = json.loads((RD / fname).read_text(encoding="utf-8"))
    node = _get(doc, path)
    seg = {"kind": kind, "label": LABELS[kind], "source": f"research/data/{fname}", "path": path, "trials": trials, "note": note,
           "period": _period(doc), "cagr": node.get("cagr"), "mdd": node.get("mdd")}
    if kind == "oos":
        seg["monthly"] = node.get("monthly") or {}
        seg["cum_return"] = node.get("cum_return")
    return seg


def build() -> dict:
    lines = {}
    for lid, spec in SPEC.items():
        segs = {}
        for kind, sp in spec.items():
            try:
                segs[kind] = _seg(kind, sp)
            except Exception as e:  # noqa: BLE001 -- 單一來源壞掉只少那一段（十二節）
                print(f"[warn] {lid}/{kind} 讀取失敗：{type(e).__name__}: {e}")
        lines[lid] = segs
    bench = {}
    for kind, sp in BENCH.items():
        try:
            bench[kind] = _seg(kind, sp)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 0050/{kind} 讀取失敗：{type(e).__name__}: {e}")
    return {"meta": {"generated_at": datetime.now(TZ).isoformat(timespec="seconds"), "source": ".github/scripts/build_strategy_history.py",
                     "labels": LABELS, "paper_start": PAPER_START,
                     "note": "只讀既有結果檔，不重算、不重跑樣本外、不新開試驗；回測結果檔沒有逐月序列，只提供摘要數字"},
            "bench_0050": bench, "lines": lines}


def main() -> int:
    doc = build()
    old = None
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if old and old.get("lines") == doc["lines"] and old.get("bench_0050") == doc["bench_0050"]:
        print("strategy_history.json 內容未變，不重寫")
        return 0
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for lid, segs in doc["lines"].items():
        print(lid, {k: (round(v["cagr"] * 100, 2) if v.get("cagr") is not None else None, len(v.get("monthly") or {})) for k, v in segs.items()})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"WARN build_strategy_history 失敗（{type(e).__name__}: {e}），只降級")
        sys.exit(0)
