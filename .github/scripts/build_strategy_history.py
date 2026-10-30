"""先.七十六（2026-10-11）：「跟 0050 比」卡的歷史段 → data/strategy_history.json（只讀既有結果檔，不重算、不重跑、不新開試驗）。

每條策略線分三段：
  回測段（2003-07～2024-12）：用來挑策略的資料。摘要數字（年化、最大跌幅）一律以原結果檔為準；
      逐月序列取自 data/strategy_monthly_returns.json（先.七十七-5），年化與原結果檔一致才附上序列、App 才畫虛線曲線。
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
# 先.七十七-5：回測段逐月序列改讀既有 data/strategy_monthly_returns.json（先.五十九-B4 產出，2003-07～2024-12），不重跑回測。
# 年化／最大跌幅都要跟原結果檔一致（±0.05pp）才算可重現；不一致標 IRREPRODUCIBLE。年化一致才畫曲線
# （年化不一致＝序列不是同一個策略版本，例如閘門延後一日的變體）；最大跌幅月資料一定比日資料淺，所以另外註明。
MONTHLY = ROOT / "data" / "strategy_monthly_returns.json"
BT_SERIES = {"live_bb90": "Bb-90", "paper_1b": "Bb-90", "paper_3": "S3-C6", "paper_4": "R1-C"}
BENCH_SERIES = "0050"
TOL_PP = 0.05
PAPER_START = "2026-10-08"

# 線 id → 各段來源（檔名、JSON 路徑、事前登記／結果試驗編號、附註）
SPEC = {
    "live_bb90": {
        "backtest": ("core_allocation_result_unioncal.json", ["grid", "Bb-90"], "#417／#418", "核心配置 24 格點的 Bb-90（45% 0050＋45% VTI＋10% IEF）；美股腿聯集日曆更正值（先.八十一-6）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "Bb-90"], "#423／#425", "美股腿用 VTI／IEF；真錢版改用 00646／00697B"),
    },
    "paper_1": {
        "backtest": ("core_allocation_result_unioncal.json", ["grid", "Aa-70"], "#417／#418", "70% 0050＋30% 定存（核心配置基準 Aa-70）；聯集日曆重跑（先.八十一-6）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "paper1_70_30"], "#423／#425", ""),
    },
    "paper_3": {
        # 先.八十-7（2026-10-12）：改用「訊號延後一個交易日」版（與紙.三實際執行一致；12.13%／−25.85%），
        # 舊的同日訊號版（12.30%／−24.66%）在紙上追蹤裡做不到，不再當作模擬 B 的回測數字。
        "backtest": ("crisis_gate_timing_sensitivity_unioncal.json", ["trials", "S3-C6"], "#424／#426", "訊號延後一個交易日（與紙上追蹤實際執行一致）；美股腿聯集日曆更正值（先.八十一-6）",
                     "crisis_gate_leveraged_bb90_result_unioncal.json"),
        "oos": ("s3c6_oos_2025_result.json", ["results", "S3-C6_real"], "#427／#428", "槓桿腿用 00631L／00647L 真實價"),
    },
    "paper_4": {
        "backtest": ("r1_0050_credit_gate_result_unioncal.json", ["trials", "R1-C", "stats"], "#429／#430", "看過 2025–26 結果後才設計；R1 沒有做樣本外單發，只有回測段；聯集日曆重跑（先.八十一-6）"),
    },
    "paper_1b": {
        "backtest": ("core_allocation_result_unioncal.json", ["grid", "Bb-90"], "#417／#418", "同族 Bb-90（回測美股腿用 VTI／IEF）；聯集日曆更正值（先.八十一-6）"),
        "oos": ("bb90_oos_2025_result.json", ["results", "Bb-90"], "#423／#425", "同族 Bb-90（美股腿用 VTI／IEF）"),
    },
}
BENCH = {
    "backtest": ("r1_0050_credit_gate_result_unioncal.json", ["benchmark_0050_buy_hold"], "#429／#430", "0050 買進持有（還原息）"),
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
    # spec＝(檔名, JSON 路徑, 試驗編號, 附註[, 期間來源檔])；第 5 欄給「本檔沒記期間、沿用原單發結果檔期間」的重跑變體用
    fname, path, trials, note = spec[:4]
    doc = json.loads((RD / fname).read_text(encoding="utf-8"))
    node = _get(doc, path)
    period = _period(doc)
    if period == [None, None] and len(spec) > 4:
        period = _period(json.loads((RD / spec[4]).read_text(encoding="utf-8")))
    seg = {"kind": kind, "label": LABELS[kind], "source": f"research/data/{fname}", "path": path, "trials": trials, "note": note,
           "period": period, "cagr": node.get("cagr"), "mdd": node.get("mdd")}
    if kind == "oos":
        seg["monthly"] = node.get("monthly") or {}
        seg["cum_return"] = node.get("cum_return")
    return seg


def _series_stats(rs):
    v, peak, mdd = 1.0, 1.0, 0.0
    for r in rs:
        v *= 1 + r
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return v ** (12 / len(rs)) - 1, mdd


def _attach_monthly(seg, key, mdoc):
    if not mdoc or key not in (mdoc.get("returns") or {}):
        seg["repro"] = {"status": "NO_SERIES", "why": "strategy_monthly_returns.json 沒有這條策略的逐月序列"}
        return
    months, rs = mdoc["months"], mdoc["returns"][key]
    c, m = _series_stats(rs)
    cagr_ok = seg.get("cagr") is not None and abs(c - seg["cagr"]) * 100 <= TOL_PP
    mdd_ok = seg.get("mdd") is not None and abs(m - seg["mdd"]) * 100 <= TOL_PP
    why = []
    if not cagr_ok:
        why.append(f"年化：月序列 {c * 100:.2f}% ≠ 原結果檔 {seg['cagr'] * 100:.2f}%（{(mdoc.get('sources') or {}).get(key, '')}）")
    if not mdd_ok:
        why.append(f"最大跌幅：月序列 {m * 100:.2f}% ≠ 原結果檔（日資料）{seg['mdd'] * 100:.2f}%；月底資料看不到月中跌幅，必然較淺")
    # 先.八十-7：年化一致、只有最大跌幅對不上（月資料看不到月中跌幅，必然較淺）→ 標「月頻近似」（MONTHLY_APPROX），
    # 不再標 IRREPRODUCIBLE；年化也對不上才是 IRREPRODUCIBLE（序列不是同一個策略版本）。
    status = "OK" if (cagr_ok and mdd_ok) else ("MONTHLY_APPROX" if cagr_ok else "IRREPRODUCIBLE")
    seg["repro"] = {"status": status, "label": {"OK": "可重現", "MONTHLY_APPROX": "月頻近似", "IRREPRODUCIBLE": "無法重現"}[status], "series_key": key,
                    "cagr_series": round(c, 6), "mdd_series": round(m, 6), "cagr_ok": cagr_ok, "mdd_ok": mdd_ok,
                    "draw_curve": cagr_ok, "why": "；".join(why), "source": "data/strategy_monthly_returns.json"}
    if cagr_ok:
        seg["monthly"] = dict(zip(months, rs))


def build() -> dict:
    try:
        mdoc = json.loads(MONTHLY.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 讀不到 strategy_monthly_returns.json：{type(e).__name__}")
        mdoc = None
    lines = {}
    for lid, spec in SPEC.items():
        segs = {}
        for kind, sp in spec.items():
            try:
                segs[kind] = _seg(kind, sp)
                if kind == "backtest":
                    _attach_monthly(segs[kind], BT_SERIES.get(lid, ""), mdoc)
            except Exception as e:  # noqa: BLE001 -- 單一來源壞掉只少那一段（十二節）
                print(f"[warn] {lid}/{kind} 讀取失敗：{type(e).__name__}: {e}")
        lines[lid] = segs
    bench = {}
    for kind, sp in BENCH.items():
        try:
            bench[kind] = _seg(kind, sp)
            if kind == "backtest":
                _attach_monthly(bench[kind], BENCH_SERIES, mdoc)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 0050/{kind} 讀取失敗：{type(e).__name__}: {e}")
    return {"meta": {"generated_at": datetime.now(TZ).isoformat(timespec="seconds"), "source": ".github/scripts/build_strategy_history.py",
                     "labels": LABELS, "paper_start": PAPER_START,
                     "note": "只讀既有結果檔，不重算、不重跑樣本外、不新開試驗；回測結果檔沒有逐月序列，只提供摘要數字"},
            "bench_0050": bench, "lines": lines}


def main() -> int:
    doc = build()
    if not any(doc["lines"].values()) and not doc["bench_0050"]:
        # 先.一三五-1cm：結果檔全讀不到時原本用全空的 lines 覆寫既有檔；照十二節只警告、不寫檔
        print("WARN build_strategy_history：所有結果檔都讀不到，本輪不寫檔（保留上一版）")
        return 0
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
    for lid, segs in list(doc["lines"].items()) + [("0050", doc["bench_0050"])]:
        print(lid, {k: (round(v["cagr"] * 100, 2) if v.get("cagr") is not None else None, len(v.get("monthly") or {}),
                        (v.get("repro") or {}).get("status")) for k, v in segs.items()})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"WARN build_strategy_history 失敗（{type(e).__name__}: {e}），只降級")
        sys.exit(0)
