# -*- coding: utf-8 -*-
"""跨輪次選擇偏誤總帳：多重比較校正後，我們的證據強度還剩多少？（2026-09-07 Cybex.債務1）

做法抄自 Cybex 的 `_r436_selection_bias_ledger.py`（含 Acklam 反常態分位數近似，
不拉進 scipy 相依）。**只抄方法，不抄任何參數**——Cybex 的閾值是在加密市場資料上
找出來的，對台股零效力。

動機（總司令裁示）：六大偽影家族與隨機控制組控制的是「**單一機制**是不是偽影」，
不是「這麼多輪裡**挑出來的這一組**整體是不是過擬合」。每輪的控制組都是局部的，
沒有全域的。這支就是那本全域總帳。

**不修改任何策略、不碰 holdout**，只產出誠實的證據強度評估。

用法：python research/selection_bias_audit.py
輸出：終端機報告 ＋ research/data/selection_bias_audit.json
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
OUT = ROOT / "research" / "data" / "selection_bias_audit.json"
TZ = timezone(timedelta(hours=8))
GAMMA = 0.5772156649015329  # Euler-Mascheroni


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Acklam 反常態分位數近似。精度足夠（|誤差| < 1.15e-9），且不需要 scipy。"""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p out of range")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return ((((( c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -((((( c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return ((((( a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """E[max SR]（Bailey & López de Prado 2014）：N 次獨立試驗中最大 Sharpe 的期望值。

    這是 DSR 的核心：就算所有策略真實 Sharpe 都是 0，只要搜得夠多，
    最好的那一個看起來也會很漂亮。這個式子算的就是「純靠運氣能漂亮到什麼程度」。
    """
    if n_trials < 2 or var_sr <= 0:
        return 0.0
    sd = math.sqrt(var_sr)
    return sd * ((1 - GAMMA) * norm_ppf(1 - 1.0 / n_trials)
                 + GAMMA * norm_ppf(1 - 1.0 / (n_trials * math.e)))


def deflated_sharpe(sr: float, n_trials: int, var_sr: float, t_obs: int,
                    skew: float = 0.0, kurt: float = 3.0) -> float:
    """DSR：扣掉「搜尋帶來的運氣」之後，這個 Sharpe 還顯著的機率。"""
    if t_obs < 2:
        return float("nan")
    e_max = expected_max_sharpe(n_trials, var_sr)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + ((kurt - 1) / 4.0) * sr * sr))
    return norm_cdf((sr - e_max) * math.sqrt(t_obs - 1) / denom)


# ── 帳本解析 ───────────────────────────────────────────────────────────────
def parse_ledger() -> list[dict]:
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| #"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 8:
            continue
        m = re.match(r"^\d+$", cells[1])
        if not m:
            continue
        verdict_raw = cells[7]
        verdict = "OTHER"
        if "CHEAP_PASS" in verdict_raw:
            verdict = "CHEAP_PASS"
        elif "PASS" in verdict_raw and "FAIL" not in verdict_raw:
            verdict = "PASS"
        elif "FAIL" in verdict_raw:
            verdict = "FAIL"
        elif "EXPERIMENTAL" in verdict_raw:
            verdict = "EXPERIMENTAL"
        pct = None
        pm = re.search(r"(\d+(?:\.\d+)?)\s*百分位", cells[6] + " " + verdict_raw)
        if pm:
            pct = float(pm.group(1))
        rows.append({"id": int(cells[1]), "date": cells[2], "track": cells[3],
                     "name": cells[4][:60], "verdict": verdict,
                     "verdict_raw": verdict_raw[:60], "percentile": pct})
    return rows


def main() -> int:
    rows = parse_ledger()
    # N 誠實給範圍，不假裝精確（Cybex 的做法）。三個口徑差很多，這件事本身就是發現。
    n_ledger_rows = len(rows)
    n_max_id = max((r["id"] for r in rows), default=0)
    n_stated = 588  # MARATHON_PROTOCOL 第 0a 節、總司令裁示所述
    candidates = {"帳本實際列數": n_ledger_rows, "帳本最大編號": n_max_id, "裁示所述試驗數": n_stated}

    passes = [r for r in rows if r["verdict"] in ("PASS", "CHEAP_PASS", "EXPERIMENTAL")]
    with_pct = [r for r in passes if r["percentile"] is not None]

    report = {
        "generated_at": datetime.now(TZ).isoformat(),
        "method": "Bonferroni + Deflated Sharpe（Bailey & López de Prado 2014），"
                  "做法抄自 Cybex _r436_selection_bias_ledger.py，未移植任何參數",
        "n_candidates": candidates,
        "ledger_rows": n_ledger_rows,
        "verdict_counts": {},
        "bonferroni": {},
        "reevaluated": [],
        "dsr": {"computable": False, "reason": ""},
        "notes": [],
    }
    for r in rows:
        report["verdict_counts"][r["verdict"]] = report["verdict_counts"].get(r["verdict"], 0) + 1

    print("=" * 74)
    print("  跨輪次選擇偏誤總帳（Cybex.債務1）")
    print("=" * 74)
    print(f"  帳本可解析列數：{n_ledger_rows}　最大編號：{n_max_id}　裁示所述：{n_stated}")
    print(f"  判定分佈：{report['verdict_counts']}")
    print()

    # ── Bonferroni ────────────────────────────────────────────────────────
    print("  【Bonferroni 門檻】單邊 α=0.05，N 越大門檻越高")
    print(f"  {'N 口徑':<16}{'N':>6}   {'需要的百分位':>14}   {'等價 p 值':>12}")
    for label, n in candidates.items():
        if n <= 0:
            continue
        alpha = 0.05 / n
        need_pct = (1 - alpha) * 100
        report["bonferroni"][label] = {"n": n, "alpha": alpha, "required_percentile": need_pct}
        print(f"  {label:<16}{n:>6}   {need_pct:>13.4f}%   {alpha:>12.2e}")
    print()

    strict_n = max(candidates.values())
    strict_pct = (1 - 0.05 / strict_n) * 100
    print(f"  用最嚴格的 N={strict_n}（門檻 {strict_pct:.4f} 百分位）重評所有 PASS／CHEAP_PASS／EXPERIMENTAL：")
    print()
    survived, fell, unknown = [], [], []
    for r in passes:
        if r["percentile"] is None:
            unknown.append(r)
            continue
        (survived if r["percentile"] >= strict_pct else fell).append(r)

    for r in fell:
        print(f"    ✗ #{r['id']:<4} {r['name'][:44]:<46} {r['percentile']:.1f} 百分位 → 倒下")
    for r in survived:
        print(f"    ✓ #{r['id']:<4} {r['name'][:44]:<46} {r['percentile']:.1f} 百分位 → 撐住")
    report["reevaluated"] = [
        {"id": r["id"], "name": r["name"], "percentile": r["percentile"],
         "verdict_before": r["verdict"],
         "verdict_after": "SURVIVED" if r in survived else "FELL"}
        for r in survived + fell]

    print()
    print(f"  結果：標記為通過的共 {len(passes)} 筆")
    print(f"        其中有百分位數字可重評的 {len(with_pct)} 筆 → 撐住 {len(survived)}、**倒下 {len(fell)}**")
    print(f"        沒有記錄百分位、無法重評的 {len(unknown)} 筆（見下方誠實揭露）")

    # ── DSR ───────────────────────────────────────────────────────────────
    print()
    print("  【Deflated Sharpe】")
    sharpe_rows = [r for r in rows if re.search(r"[Ss]harpe", r["verdict_raw"] or "")]
    if len(sharpe_rows) < 5:
        reason = (f"帳本裡只有 {len(sharpe_rows)} 筆記到 Sharpe，算不出試驗間的 Sharpe 變異數 V，"
                  "而 V 是 E[max SR] 的必要輸入。**不編一個數字**——留白比假裝精確誠實。")
        report["dsr"] = {"computable": False, "reason": reason,
                         "rows_with_sharpe": len(sharpe_rows)}
        print(f"    無法計算：{reason}")
        # 但可以示範「如果 SR 是 X，在 N 下要多少才撐得住」，這是可用的決策資訊
        print()
        print("    改為給出「在各 N 下，Sharpe 要多高才不算運氣」（假設試驗間 SR 標準差=0.5、T=750 交易日）：")
        for label, n in candidates.items():
            e_max = expected_max_sharpe(n, 0.25)
            print(f"      {label:<16} N={n:<5} E[max SR]≈{e_max:.3f} → 觀察到的 SR 必須明顯高於這個數才有意義")
            report["dsr"].setdefault("expected_max_sr_illustrative", {})[label] = round(e_max, 4)
    else:
        report["dsr"] = {"computable": True, "rows_with_sharpe": len(sharpe_rows)}

    # ── 誠實揭露 ──────────────────────────────────────────────────────────
    notes = [
        f"帳本可解析 {n_ledger_rows} 列、最大編號 {n_max_id}，但裁示所述試驗數為 {n_stated}——"
        "三個口徑不一致本身就是發現：大量試驗沒有進到結構化帳本（見 Cybex.債務3）。",
        f"用最嚴格的 N={strict_n} 是刻意的：多重比較校正只有在 N 涵蓋「所有做過的試驗」時才有意義，"
        "用偏小的 N 會讓門檻虛低，等於自己放水。",
        f"{len(unknown)} 筆標記通過但帳本沒有記錄可比較的統計量（百分位/Sharpe），"
        "無法重評。這些**不能算撐住，也不能算倒下**——它們是「當初就沒留下足以判斷的證據」。",
        "DSR 需要試驗間的 Sharpe 變異數；帳本記的是「打散對照百分位」不是 Sharpe，所以算不出來。"
        "往後的登記必須同時記 Sharpe、T、skew、kurt，否則這本總帳永遠只能算 Bonferroni。",
    ]
    report["notes"] = notes
    print()
    print("  【誠實揭露】")
    for n_ in notes:
        print(f"    · {n_}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print(f"  報告寫入 {OUT.relative_to(ROOT)}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
