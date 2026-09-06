# -*- coding: utf-8 -*-
"""撐住的候選 vs 純運氣期望上限，以及全體分母對 US 軌的影響。

（2026-09-07 總司令裁示第 3、5 點）

第 3 點：三個在 Bonferroni N=219 下撐住的候選（f_eps_growth／f_eps_surprise／
f_low_vol），把它們作為策略的實際 Sharpe 跟 E[max SR] 並列——**通過多重比較校正
只代表「不是純運氣挑出來的」，不代表「賺得比純運氣挑出來的最好那個多」**，
這是兩個不同的問題，必須分開看。

並且依裁示改用**帳本裡實際可得的試驗 Sharpe 分布**重算 V，不再用假設的 0.5；
若可得樣本太少，就誠實標「V 為假設值，結論僅供參考」。

第 5 點：若廢除分軌獨立分母、改用全體分母，US 軌現存的 CHEAP_PASS 是否仍成立。
**只給數字，不預設結論。**

用法：python research/survivor_sharpe_check.py
"""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
OUT = ROOT / "research" / "data" / "survivor_sharpe_check.json"
TZ = timezone(timedelta(hours=8))

import sys
sys.path.insert(0, str(ROOT / "research"))
from selection_bias_ledger import (  # noqa: E402
    expected_max_sharpe, required_percentile, parse,
)

SURVIVORS = ["f_eps_growth", "f_eps_surprise", "f_low_vol"]
# 兩種寫法都要抓：`Sharpe0.558`、`sharpe+0.691`、`Sharpe=0.502`、`Sharpe 1.28`
SHARPE_RE = re.compile(r"[Ss]harpe\s*[=:＝]?\s*([+-]?\d+\.\d+)")


def all_trial_sharpes() -> list[float]:
    """掃整份帳本原文抓 Sharpe。

    上一版只掃解析後被截斷的欄位，結果只抓到 1 筆就下結論「算不出 V」——
    那是我的取數錯誤，不是資料真的沒有。這一版掃原始文字。
    """
    txt = LEDGER.read_text(encoding="utf-8")
    vals = [float(m.group(1)) for m in SHARPE_RE.finditer(txt)]
    # 明顯不合理的值剔掉（Sharpe 超過 5 幾乎必然是別的東西被誤抓）
    return [v for v in vals if -5.0 <= v <= 5.0]


def main() -> int:
    rows = parse()
    n_all = len(rows)
    sharpes = all_trial_sharpes()

    print("=" * 76)
    print("  撐住的候選 vs 純運氣期望上限（總司令裁示第 3 點）")
    print("=" * 76)
    print(f"  帳本試驗總數 N = {n_all}")
    print(f"  帳本可抓到的試驗 Sharpe 樣本數 = {len(sharpes)}")

    if len(sharpes) >= 5:
        var_sr = statistics.variance(sharpes)
        v_source = f"實際樣本（n={len(sharpes)}，標準差 {statistics.stdev(sharpes):.3f}）"
        v_is_assumed = False
    else:
        var_sr = 0.25
        v_source = "假設值 0.5²（帳本可得樣本不足 5 筆）"
        v_is_assumed = True

    e_max = expected_max_sharpe(n_all, var_sr)
    print(f"  試驗間 Sharpe 變異數 V = {var_sr:.4f}　來源：{v_source}")
    print(f"  E[max SR]（N={n_all}）= {e_max:.3f}")
    if v_is_assumed:
        print("  ⚠ V 為假設值，以下結論僅供參考，不得當成定論")
    else:
        print(f"  （帳本 Sharpe 樣本範圍 {min(sharpes):.3f} ~ {max(sharpes):.3f}）")
    print()

    print("  三個撐住的候選：")
    survivors_out = []
    for name in SURVIVORS:
        # 從帳本原文找這個因子附近的 Sharpe
        txt = LEDGER.read_text(encoding="utf-8")
        found = []
        for line in txt.splitlines():
            if name in line:
                found += [float(m.group(1)) for m in SHARPE_RE.finditer(line)]
        sr = max(found) if found else None
        if sr is None:
            verdict = "帳本沒有記錄這個候選的 Sharpe → **無法比較**"
        elif sr > e_max:
            verdict = f"Sharpe {sr:.3f} > E[max SR] {e_max:.3f} → 高於純運氣期望上限"
        else:
            verdict = f"Sharpe {sr:.3f} ≤ E[max SR] {e_max:.3f} → **未超過純運氣期望上限**"
        print(f"    {name:<22} {verdict}")
        survivors_out.append({"factor": name, "sharpe": sr, "e_max_sr": round(e_max, 4),
                              "exceeds": (sr > e_max) if sr is not None else None,
                              "v_is_assumed": v_is_assumed})
    print()

    # ── 第 5 點：US 軌在全體分母下 ──────────────────────────────────────
    print("=" * 76)
    print("  US 軌：分軌分母 vs 全體分母（總司令裁示第 5 點）")
    print("=" * 76)
    us_rows = [r for r in rows if r["track"] == "US"]
    n_us = len(us_rows)
    thr_track = required_percentile(n_us)
    thr_all = required_percentile(n_all)
    print(f"  US 軌 N={n_us} → 門檻 {thr_track:.4f} 百分位")
    print(f"  全體  N={n_all} → 門檻 {thr_all:.4f} 百分位")
    print()
    us_pass = [r for r in us_rows if r["verdict"] in ("PASS", "CHEAP_PASS", "EXPERIMENTAL")]
    with_pct = [r for r in us_pass if r["percentile"] is not None]
    print(f"  US 軌標記通過的 {len(us_pass)} 筆，其中有百分位可比的 {len(with_pct)} 筆：")
    us_out = []
    for r in sorted(with_pct, key=lambda x: x["id"]):
        ok_t = r["percentile"] >= thr_track
        ok_a = r["percentile"] >= thr_all
        flag = "維持" if (ok_t and ok_a) else ("**改用全體分母後倒下**" if ok_t else "兩種分母都不過")
        print(f"    #{r['id']:<4} {r['factor'][:34]:<36} {r['percentile']:>5.1f} 百分位  "
              f"分軌{'✓' if ok_t else '✗'} 全體{'✓' if ok_a else '✗'}  {flag}")
        us_out.append({"id": r["id"], "factor": r["factor"], "percentile": r["percentile"],
                       "holds_track": ok_t, "holds_all": ok_a})
    if not with_pct:
        print("    （US 軌標記通過的項目都沒有留下百分位數字，無法比較——這本身是登記品質問題）")
    print()
    print("  **只給數字，不預設結論**：是否廢除分軌獨立分母由總司令裁示。")

    payload = {
        "generated_at": datetime.now(TZ).isoformat(),
        "n_all": n_all, "n_us": n_us,
        "trial_sharpe_samples": len(sharpes), "var_sr": var_sr,
        "var_sr_is_assumed": v_is_assumed, "v_source": v_source,
        "e_max_sr": round(e_max, 4),
        "survivors": survivors_out,
        "us_threshold_track": thr_track, "us_threshold_all": thr_all,
        "us_candidates": us_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
