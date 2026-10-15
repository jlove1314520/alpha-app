"""先.一〇三-8（2026-10-16）：融資維持率缺日補抓（一次性手動）。

用 update_margin_maintenance.py 既有的 _fetch_margin_money_for_date()（www.twse.com.tw/rwd MI_MARGN，
共用 data/rate_limit_state.json 來源名 twse_margn_rwd，同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時不重試），
分子收盤價用 price_history 同一天收盤（closes_from_price_history），覆蓋 <99% 就標資料不完整、不相除。
用法：python scripts/backfill_margin_maintenance.py 2026-09-01 2026-09-07 ...  [--deadline HH:MM]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import update_margin_maintenance as M  # noqa: E402


def main(argv: list[str]) -> int:
    deadline = None
    if "--deadline" in argv:
        i = argv.index("--deadline")
        deadline = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    days = argv
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AlphaAppMarketFetcher/1.0)"}  # 與每日排程同一個識別 UA；不帶 Referer
    history = json.loads(M.OUT_PATH.read_text(encoding="utf-8"))
    have = {h.get("date") for h in history}
    added = []
    for day in days:
        if deadline and datetime.now(M.TW_TZ).strftime("%H:%M") >= deadline:
            print(f"到 {deadline}，停止送新請求；剩 {days[days.index(day):]}")
            break
        if day in have:
            print(f"{day} 已有，略過")
            continue
        try:
            res = M._fetch_margin_money_for_date(day.replace("-", ""), headers)
        except Exception as e:  # noqa: BLE001 — 封鎖／錯誤即停，不重試
            print(f"{day} 取得失敗，停止：{e}")
            break
        if res is None:
            print(f"{day} 官方查無資料（休市或未發布）")
            continue
        money_date, margin_money, lots = res
        closes = M.closes_from_price_history(money_date)
        coll, matched, missing = 0.0, 0, 0.0
        for code, n in lots.items():
            if n <= 0:
                continue
            px = closes.get(code)
            if px is None:
                missing += n
                continue
            coll += n * 1000 * px
            matched += 1
        total = sum(v for v in lots.values() if v > 0)
        cov = (1 - missing / total) if total else 0.0
        incomplete = not lots or cov < 0.99
        ratio = round(coll / margin_money * 100, 2) if (margin_money and not incomplete) else None
        rec = {
            "date": money_date,
            "margin_money_date": money_date,
            "numerator_margin_date": money_date if lots else None,
            "numerator_close_date": money_date,
            "numerator_close_source": "price_history（補抓）",
            "collateral_value": round(coll) if coll else None,
            "margin_money": margin_money,
            "matched_stocks": matched,
            "ratio_pct": ratio,
            "data_incomplete": incomplete,
            "incomplete_reason": (f"同日收盤價只涵蓋 {cov:.1%} 的融資張數（<99%），不相除" if incomplete else None),
            "generated_at": datetime.now(M.TW_TZ).isoformat(),
            "recorded_on": datetime.now(M.TW_TZ).date().isoformat(),
            "source": "先.一〇三-8 補抓：TWSE www.twse.com.tw/rwd MI_MARGN 指定日期（分子分母同一回應）×price_history 同日收盤",
        }
        if ratio is not None:
            try:
                sys.path.insert(0, str(ROOT / "research"))
                import build_margin_calibration as bmc
                cal = json.loads((ROOT / "data" / "margin_ratio_calibration.json").read_text(encoding="utf-8"))
                ck = bmc.ck_value(ratio, cal)
                if ck is not None:
                    rec["ratio_pct_ck"] = ck
            except Exception as e:  # noqa: BLE001 — 校準失敗只略過 ck
                print(f"::warning::{day} 校準失敗，不寫 ratio_pct_ck：{type(e).__name__}")
        print(f"{day} → 資料日 {money_date} 維持率 {ratio}（覆蓋 {cov:.2%}，{matched} 檔）")
        history.append(rec)
        have.add(money_date)
        added.append(money_date)
    history = M.normalize_history(history)[-M.HISTORY_DAYS_KEEP:]
    M.OUT_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"補入 {len(added)} 天：{added}；檔案共 {len(history)} 列")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
