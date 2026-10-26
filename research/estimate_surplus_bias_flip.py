# -*- coding: utf-8 -*-
"""先.一三五-3②（2026-10-27，Cowork 收件匣 024）：價值／低波動／品質「可能翻轉」名單逐條估公積漏算偏誤上限。
不重跑任何試驗、不算策略報酬；只讀 research/data/adjust_surplus_fix_impact.json 與樣本宇宙定義（本機快取、零請求）。

偏誤（年化報酬低估）≈ 受影響股票占持股比例 × 受影響股票平均每年公積配息幅度。
- 受影響股票＝走 FinMind 路徑、2015～2024 有公積還原變動者（332 檔）；
- 每檔每年幅度＝Σ(1 − factor_new／factor_old)／10 年（2015～2024），再取受影響股平均與最大；
- 持股比例：沒有逐期持股紀錄，用該試驗樣本宇宙裡受影響股票的占比代替（樣本 100 檔類用 factor_ic.sample_universe_ids）；
  另給「持股全落在受影響股」的硬上限＝平均幅度本身。
輸出 research/data/surplus_bias_flip_estimate.json。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).parent
imp = json.loads((HERE / "data" / "adjust_surplus_fix_impact.json").read_text(encoding="utf-8"))
per_stock = {}
for s in imp["stocks"]:
    if s["path"] != "finmind" or not s["n_changed_events_2015_2024"]:
        continue
    tot = 0.0
    for e in s["events"]:
        if not ("2015-01-01" <= e["ex_date"] <= "2024-12-31"):
            continue
        old = e["factor_old"] if e["factor_old"] is not None else 1.0
        new = e["factor_new"] if e["factor_new"] is not None else 1.0
        tot += 1.0 - new / old
    per_stock[s["stock_id"]] = tot / 10.0
vals = sorted(per_stock.values())
mean_mag = sum(vals) / len(vals)
out = {"generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
       "n_affected_finmind": len(per_stock),
       "annual_magnitude_mean": round(mean_mag, 6),
       "annual_magnitude_median": round(vals[len(vals) // 2], 6),
       "annual_magnitude_max": round(vals[-1], 6),
       "samples": {}}
try:
    from factor_ic import sample_universe_ids
    for name, (n, seed) in {"factor_ic_300": (300, None), "sample_100": (100, None)}.items():
        ids = sample_universe_ids(n) if seed is None else sample_universe_ids(n, seed)
        hit = [x for x in ids if x in per_stock]
        share = len(hit) / len(ids)
        avg_hit = sum(per_stock[x] for x in hit) / len(hit) if hit else 0.0
        out["samples"][name] = {"n": len(ids), "n_affected": len(hit), "share": round(share, 4),
                                "affected_mean_annual_mag": round(avg_hit, 6),
                                "bias_estimate_annual": round(share * avg_hit, 6)}
except Exception as e:  # noqa: BLE001
    print(f"[warn] 樣本宇宙重建失敗：{type(e).__name__}: {e}")
    out["samples_error"] = f"{type(e).__name__}: {e}"
(HERE / "data" / "surplus_bias_flip_estimate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items()}, ensure_ascii=False, indent=1))
