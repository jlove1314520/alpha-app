# -*- coding: utf-8 -*-
"""閘門.二（2026-09-24總司令裁示【閘門.二（存活者偏差強檢）＋結果檔入庫＋
維運C/D/E】）：存活者偏差強檢，取代原本「2007-2008下市股>0」這條過弱
（Cowork所訂）的門檻。**只讀既有快取，零新增API呼叫。**

分組邏輯（普通股only，用`universe.py::classify_security()`過濾）：
- **期間下市組**：`TaiwanStockDelisting`（權威來源，`universe.delisted_
  stock_ids()`）記錄delist_date落在2007-01-01~2014-12-31。
- **存活組**：2014-12-31仍上市（不在delisted名單，或delist_date在2014
  年底之後）**且**2007年前已上市。**「已上市」判準的資料侷限誠實揭露**：
  FinMind TaiwanStockInfo沒有上市日期欄位（`universe.py`模組docstring
  已載明這個限制），本腳本沿用`universe.py`自己訂的原則——「價格列存在
  視為當天可交易的ground truth」——用「2007-01-01之前有至少一筆價格列」
  當「已上市」的代理判準（資料來源：`資料.一`已抓取的2006-01-01起價格
  快取，前一年緩衝正是為了這個判斷才刻意抓的，見`f52w_2007_extension.py`
  docstring）。這不是完美判準（可能有極少數2006年才上市、緊貼緩衝邊界
  的個案被誤判），但是這批資料能給出的最誠實推論，非另外杜撰一個上市
  日期資料源。
- 兩組之外（2007年之前就已下市、或2007年之後才上市）的樣本不計入任何
  一組分母——不是「這裡有偏差」，是「這兩組定義本來就不涵蓋它們」。

用法：python research/exam_2007_2014_data_gate2_survivorship.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import pandas as pd

from adjust import adjusted_price_series
from factor_ic import SAMPLE_SEED, SAMPLE_SIZE, sample_universe_ids
from finmind_client import _fetch
from universe import delisted_stock_ids, classify_security, universe as build_universe

CHECKPOINT_PATH = Path(__file__).parent / "data" / "f52w_2007_extension_checkpoint.json"
OOS_START, OOS_END = "2007-01-01", "2014-12-31"
EXTENDED_START = "2006-01-01"
OUT_JSON = Path(__file__).parent / "data" / "exam_2007_2014_data_gate.json"

COVERAGE_FLOOR_PERIOD_DELISTED = 80.0  # 期間下市組覆蓋率下限（%）
MAX_GAP_PP = 10.0  # 兩組覆蓋率相差上限（百分點）


def _load_info_lookup() -> dict[str, dict]:
    info = _fetch("TaiwanStockInfo", "", "2000-01-01")
    info = info.drop_duplicates(subset="stock_id", keep="last")
    lookup = info.set_index("stock_id")[["stock_name", "industry_category"]].to_dict("index")
    combined = build_universe()
    for _, row in combined.iterrows():
        sid = row["stock_id"]
        if sid not in lookup:
            lookup[sid] = {"stock_name": row["stock_name"], "industry_category": row.get("industry_category")}
    return lookup


def _has_price_before_2007(sid: str) -> bool:
    px = adjusted_price_series(sid, EXTENDED_START)
    if px.empty:
        return False
    dates = pd.to_datetime(px["date"])
    before = px.loc[dates < pd.Timestamp(OOS_START), "adj_close"]
    return bool(before.notna().any())


def _has_price_in_window(sid: str) -> bool:
    px = adjusted_price_series(sid, EXTENDED_START)
    if px.empty:
        return False
    dates = pd.to_datetime(px["date"])
    w = px.loc[(dates >= pd.Timestamp(OOS_START)) & (dates <= pd.Timestamp(OOS_END)), "adj_close"]
    return bool(w.notna().any())


def main():
    print("=== 閘門.二：存活者偏差強檢（期間下市組 vs 存活組覆蓋率，零新增API呼叫）===", flush=True)
    sample_ids = sample_universe_ids(SAMPLE_SIZE, SAMPLE_SEED)
    ckpt = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    failed_ids: dict = ckpt.get("failed_ids", {})
    info_lookup = _load_info_lookup()
    delisted = delisted_stock_ids()
    delisted_lookup = delisted.set_index("stock_id")["delist_date"].to_dict()

    common_ids = [sid for sid in sample_ids
                  if classify_security(sid, (info_lookup.get(sid) or {}).get("stock_name"),
                                        (info_lookup.get(sid) or {}).get("industry_category")) == "普通股"]
    print(f"300檔樣本中普通股={len(common_ids)}檔", flush=True)

    period_delisted, survivors, excluded = [], [], []
    for sid in common_ids:
        dd = delisted_lookup.get(sid)
        if dd is not None and OOS_START <= str(dd) <= OOS_END:
            period_delisted.append(sid)
        elif dd is not None and str(dd) < OOS_START:
            excluded.append((sid, f"2007年前已下市(delist_date={dd})，不屬本閘門任一組"))
        else:
            # dd is None（現在仍上市）或 dd > OOS_END（2014年底後才下市）→「2014-12-31仍上市」成立
            if _has_price_before_2007(sid):
                survivors.append(sid)
            else:
                excluded.append((sid, "2014-12-31仍上市，但2007-01-01前無價格資料(推論為2007年後才上市)，不屬存活組"))

    print(f"期間下市組(普通股)={len(period_delisted)}檔  存活組(普通股)={len(survivors)}檔  "
          f"排除(不屬任一組)={len(excluded)}檔", flush=True)

    def _coverage(ids: list[str]) -> tuple[float, int, int]:
        n = len(ids)
        if n == 0:
            return float("nan"), 0, 0
        n_covered = sum(1 for sid in ids if _has_price_in_window(sid))
        return round(n_covered / n * 100, 2), n_covered, n

    cov_period_pct, n_covered_period, n_period = _coverage(period_delisted)
    cov_survivor_pct, n_covered_survivor, n_survivor = _coverage(survivors)
    gap_pp = abs(cov_period_pct - cov_survivor_pct) if (n_period and n_survivor) else float("nan")

    print(f"\n期間下市組覆蓋率 = {n_covered_period}/{n_period} = {cov_period_pct}%", flush=True)
    print(f"存活組覆蓋率     = {n_covered_survivor}/{n_survivor} = {cov_survivor_pct}%", flush=True)
    print(f"兩組差距 = {gap_pp}個百分點", flush=True)

    gate2a_pass = (not pd.isna(cov_period_pct)) and cov_period_pct >= COVERAGE_FLOOR_PERIOD_DELISTED
    gate2b_pass = (not pd.isna(gap_pp)) and gap_pp <= MAX_GAP_PP
    gate2_pass = gate2a_pass and gate2b_pass
    print(f"\n判準①期間下市組>={COVERAGE_FLOOR_PERIOD_DELISTED}% : {'PASS' if gate2a_pass else 'FAIL'}", flush=True)
    print(f"判準②兩組相差<={MAX_GAP_PP}pp : {'PASS' if gate2b_pass else 'FAIL'}", flush=True)
    print(f"閘門.二綜合判定：{'PASS' if gate2_pass else 'FAIL'}", flush=True)

    print("\n--- 55檔失敗明細 ---", flush=True)
    failed_detail = []
    for sid, reason in failed_ids.items():
        row_info = info_lookup.get(sid) or {}
        dd = delisted_lookup.get(sid)
        in_period_delisted_group = bool(dd is not None and OOS_START <= str(dd) <= OOS_END)
        failed_detail.append({
            "stock_id": sid, "stock_name": row_info.get("stock_name"),
            "in_period_delisted_group": in_period_delisted_group,
            "delist_date": dd, "failure_reason": reason,
        })
    for row in failed_detail:
        print(f"  {row['stock_id']} ({row['stock_name']}) 期間下市組={row['in_period_delisted_group']} "
              f"delist_date={row['delist_date']} 原因={row['failure_reason']}", flush=True)

    gate2 = {
        "definition_caveat": "存活組的「2007年前已上市」判準用2007-01-01前有價格列當代理指標"
                              "（FinMind TaiwanStockInfo無上市日期欄位，universe.py自身即以價格列"
                              "存在為tradeable的ground truth，此處沿用同一原則），非官方上市日期資料。",
        "n_common_stock_in_300_sample": len(common_ids),
        "n_period_delisted_group": n_period, "n_survivor_group": n_survivor,
        "n_excluded_neither_group": len(excluded),
        "excluded_reasons_sample": [{"stock_id": sid, "reason": r} for sid, r in excluded[:20]],
        "period_delisted_group_ids": sorted(period_delisted),
        "survivor_group_ids_count_only": n_survivor,  # 存活組通常很大，只記數量避免JSON過肥
        "coverage_period_delisted_pct": cov_period_pct, "n_covered_period_delisted": n_covered_period,
        "coverage_survivor_pct": cov_survivor_pct, "n_covered_survivor": n_covered_survivor,
        "gap_pp": round(gap_pp, 2) if not pd.isna(gap_pp) else None,
        "criteria": {"coverage_floor_period_delisted_pct": COVERAGE_FLOOR_PERIOD_DELISTED,
                     "max_gap_pp": MAX_GAP_PP},
        "gate2a_pass_coverage_floor": gate2a_pass,
        "gate2b_pass_gap_within_limit": gate2b_pass,
        "gate2_pass": gate2_pass,
        "n_failed_total": len(failed_ids),
        "failed_detail": failed_detail,
    }

    existing = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {}
    existing["gate_2"] = gate2
    if "gate_verdicts" in existing:
        existing["gate_verdicts"]["gate2_pass"] = gate2_pass
        existing["gate_verdicts"]["all_pass_including_gate2"] = bool(existing["gate_verdicts"].get("all_pass")) and gate2_pass
    OUT_JSON.write_text(json.dumps(existing, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n已將gate_2併入 {OUT_JSON}", flush=True)
    return gate2


if __name__ == "__main__":
    main()
