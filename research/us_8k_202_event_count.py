# -*- coding: utf-8 -*-
"""先.八十三-3b-1：B2 #52-US 8-K Item 2.02 新樣本事件數盤點（只數 SEC 事件，不抓價格、不算報酬、不登記試驗）。

做法：
  1. 原試驗樣本＝us_8k_pead_gate52.sample_ids(25, seed)（22 檔可用）→ 25 檔全部排除（取超集，寧可多排）。
  2. 候選＝data/us_screener.json 253 檔，依 20 日平均成交金額由大到小（253 檔都有這欄；市值估計只有 184 檔有）
     [自行裁量]，排除原 25 檔後取前 200 檔。這是今天還在市的名單＝存活者偏誤，結論附美股但書。
  3. 以 CIK 定義樣本：代號→CIK 用 SEC company_tickers.json（現況對照），之後一律用 CIK。
  4. 每檔抓 data.sec.gov submissions；分頁檔只抓 filingTo ≥ 2004-08-01 的（Item 2.02 自 2004-08 才有）。
     硬性請求預算 1,000 次、每次請求後 sleep 0.25 秒（約 4 次/秒，低於 SEC 10 次/秒上限）。
  5. 只數 ≤ 2024-12-31 的事件（TRAIN ≤2020、VAL 2021～2024）；2025 以後不數。
  6. 逐檔 CIK 核對紀錄：SEC 名稱 vs 篩選表名稱、formerNames 筆數、最早 8-K 日、最早 2.02 日；
     最早 8-K 晚於 2010 的標「可能 CIK 換號／控股重組」（XOM 2115436 那種）。

輸出：research/data/us_8k_202_event_count.json（research/data 已 gitignore），並印出摘要。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sec_edgar_client as sec  # noqa: E402

REQUEST_BUDGET = 1000
SLEEP_SEC = 0.25
N_TARGET = 200
ITEM_START = "2004-08-01"
TRAIN_END = "2020-12-31"
VAL_END = "2024-12-31"
OUT = HERE / "data" / "us_8k_202_event_count.json"
_n_req = 0


class BudgetExceeded(RuntimeError):
    pass


def _get(fn, *args, cache_name: str):
    """呼叫 sec_edgar_client 的快取函式；沒命中快取才算一次請求並 sleep。"""
    global _n_req
    p = sec._cache_path(cache_name)
    cached = p.exists() and (time.time() - p.stat().st_mtime) < sec._CACHE_MAX_AGE_SECONDS
    if not cached:
        if _n_req >= REQUEST_BUDGET:
            raise BudgetExceeded(f"請求預算 {REQUEST_BUDGET} 用完")
        _n_req += 1
    out = fn(*args)
    if not cached:
        time.sleep(SLEEP_SEC)
    return out


def _original_tickers() -> list[str]:
    from us_8k_pead_gate52 import SAMPLE_SEED, SAMPLE_SIZE, sample_ids
    return sample_ids(SAMPLE_SIZE, SAMPLE_SEED)


def _extract(block: dict) -> list[dict]:
    n = len(block.get("form", []))
    return [{"filingDate": block["filingDate"][i], "items": (block.get("items") or [""] * n)[i] or ""}
            for i in range(n) if block["form"][i] == "8-K"]


def main() -> None:
    global REQUEST_BUDGET
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=REQUEST_BUDGET, help="本次可用的新請求數（跨次執行要自己扣掉前次用掉的）")
    ap.add_argument("--max-minutes", type=float, default=0, help="時間到就停、照樣寫出已處理的部分")
    a = ap.parse_args()
    REQUEST_BUDGET = a.budget
    t0 = time.time()
    orig = _original_tickers()
    print(f"原試驗樣本 {len(orig)} 檔（排除）：{orig}")
    scr = json.loads((HERE.parent / "data" / "us_screener.json").read_text(encoding="utf-8"))
    stocks = sorted(scr["stocks"], key=lambda s: -(s.get("avg_dollar_volume_20d") or 0))
    cik_map = _get(sec.get_cik_map, cache_name="cik_map")
    cands = [s for s in stocks if s["code"] not in set(orig)][:N_TARGET]
    print(f"候選 {len(cands)} 檔（篩選表資料日 {scr['meta'].get('date') or stocks[0].get('date')}）")

    rows, stopped = [], None
    for s in cands:
        if a.max_minutes and time.time() - t0 > a.max_minutes * 60:
            stopped = f"時間到（{a.max_minutes} 分鐘）"
            break
        t = s["code"]
        cik = cik_map.get(t) or cik_map.get(t.replace(".", "-"))
        row = {"ticker": t, "screener_name": s.get("name"), "cik": cik}
        if not cik:
            row["status"] = "代號在 SEC 現況對照表找不到"
            rows.append(row)
            continue
        try:
            sub = _get(sec.get_submissions, cik, cache_name=f"submissions_{str(cik).zfill(10)}")
            ev = _extract(sub.get("filings", {}).get("recent", {}))
            for f in sub.get("filings", {}).get("files", []):
                if (f.get("filingTo") or "9999") < ITEM_START:
                    continue
                arc = _get(sec.get_archive_filings, cik, f["name"],
                           cache_name=f"archive_{f['name'].replace('.json', '')}")
                ev.extend(_extract(arc))
        except BudgetExceeded as e:
            stopped = str(e)
            break
        except Exception as e:
            row["status"] = f"抓取失敗：{type(e).__name__}"
            rows.append(row)
            continue
        e202 = sorted(x["filingDate"] for x in ev if "2.02" in x["items"].split(","))
        all8k = sorted(x["filingDate"] for x in ev)
        row.update({
            "status": "ok",
            "sec_name": sub.get("name"),
            "former_names": len(sub.get("formerNames") or []),
            "first_8k": all8k[0] if all8k else None,
            "first_202": e202[0] if e202 else None,
            "n202_train": sum(1 for d in e202 if ITEM_START <= d <= TRAIN_END),
            "n202_val": sum(1 for d in e202 if TRAIN_END < d <= VAL_END),
            "flag_cik_change": bool(all8k) and all8k[0] > "2010-12-31",
        })
        rows.append(row)

    ok = [r for r in rows if r.get("status") == "ok"]
    summary = {
        "n_candidates": len(cands), "n_processed": len(rows), "n_ok": len(ok),
        "n_requests": _n_req, "stopped": stopped,
        "n202_train": sum(r["n202_train"] for r in ok),
        "n202_val": sum(r["n202_val"] for r in ok),
        "n_with_any_202": sum(1 for r in ok if r["n202_train"] + r["n202_val"] > 0),
        "n_flag_cik_change": sum(1 for r in ok if r["flag_cik_change"]),
        "n_not_found": sum(1 for r in rows if r.get("status") != "ok"),
    }
    summary["n202_train_val"] = summary["n202_train"] + summary["n202_val"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "excluded_original": orig,
                               "summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    for r in rows:
        if r.get("status") != "ok" or r.get("flag_cik_change") or (r.get("n202_train", 0) + r.get("n202_val", 0)) == 0:
            print("  注意：", {k: r.get(k) for k in ("ticker", "cik", "status", "sec_name", "first_8k", "first_202", "n202_train", "n202_val")})
    print(f"已寫入 {OUT}")


if __name__ == "__main__":
    main()
