# -*- coding: utf-8 -*-
"""V 的敏感度分析與撐住候選的運氣上限比較（2026-09-07 總司令裁示第 1 點）。

**為什麼 V 比 N 更關鍵**：E[max SR] = sqrt(V)·[...]，V 直接乘在前面。
Cybex 實測 V 從 0.634 換成 0.441，DSR 就從 0.042 跳到 0.499——同一份資料，
換一個 V 的估計方式，結論從「幾乎確定是運氣」變成「一半一半」。
所以 V 的來源與樣本數必須跟數字一起報，不能只報一個 E[max SR]。

**這支修正了前一版兩個取數錯誤**（都是實測抓到的，記在這裡免得再犯）：
  1. `all_trial_sharpes()` 掃整份檔案的文字，把**表格外正文**裡的 Sharpe 也算進去，
     報成「14 筆試驗」。實際上只有 **4 個試驗列**有 Sharpe（那 4 列裡各記了
     train/val/控制組等多個數字，合計 14 個數）。
  2. 找某個因子的 Sharpe 時用「該列文字包含因子名」比對，結果把第 107 列
     （`equal_weight_rebalance_sanity`）的 Sharpe 1.379 誤植給 `f_low_vol`，
     還據此宣稱它「高於運氣上限」。**那個結論是錯的**。

用法：python research/survivor_sharpe_check.py
"""
from __future__ import annotations

import io
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
OUT = ROOT / "research" / "data" / "survivor_sharpe_check.json"
TZ = timezone(timedelta(hours=8))

sys.path.insert(0, str(ROOT / "research"))
from selection_bias_ledger import expected_max_sharpe, required_percentile, parse  # noqa: E402

SURVIVORS = ["f_eps_growth", "f_eps_surprise", "f_low_vol"]
SHARPE_RE = re.compile(r"[Ss]harpe\s*[=:＝]?\s*([+-]?\d+\.\d+)")
FACTOR_TICK = re.compile(r"`([^`]+)`")
# Cybex 實測的 V 區間（總司令裁示指定當上界參考）。
# **這是 Cybex 在加密市場資料上量到的，不是台股的值**——依「拿方法不拿參數」原則，
# 只當敏感度分析的參考點，不當成我們的估計。
CYBEX_SD_LOW, CYBEX_SD_HIGH = 0.441, 0.634


def table_rows_with_sharpe() -> list[dict]:
    """只掃**表格列**。正文裡的 Sharpe 不是試驗登記，不能算進 V。"""
    out = []
    for i, line in enumerate(LEDGER.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        vals = [float(m.group(1)) for m in SHARPE_RE.finditer(line)]
        vals = [v for v in vals if -5.0 <= v <= 5.0]
        if not vals:
            continue
        c = [x.strip() for x in line.split("|")]
        name = next((x for x in c[3:7] if len(x) > 6), "")
        out.append({"line": i, "id": c[1] if len(c) > 1 else "?", "name": name[:70],
                    "sharpes": vals, "has_percentile": bool(re.search(r"百分位", line))})
    return out


def survivor_sharpe(factor: str) -> tuple[float | None, str]:
    """找這個因子**自己那一列**的 Sharpe。

    比對條件收緊成「因子名出現在該列的反引號標的欄位裡」——前一版用「整列文字包含
    因子名」，結果別的候選在備註裡提到它就被誤採。
    """
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.split("|")]
        name_cell = " ".join(c[3:7])
        ticks = [t for t in FACTOR_TICK.findall(name_cell)]
        if not any(t == factor or t.startswith(factor) for t in ticks):
            continue
        vals = [float(m.group(1)) for m in SHARPE_RE.finditer(line)]
        vals = [v for v in vals if -5.0 <= v <= 5.0]
        if vals:
            return max(vals), f"第 {c[1]} 列"
    return None, "帳本該因子的列沒有記錄 Sharpe"


def main() -> int:
    rows = parse()
    n_all = len(rows)
    sh_rows = table_rows_with_sharpe()
    flat = [v for r in sh_rows for v in r["sharpes"]]

    print("=" * 78)
    print("  V 的敏感度分析（總司令裁示第 1 點）")
    print("=" * 78)
    print(f"  帳本試驗總數 N = {n_all}")
    print()
    print("  (a) 那些 Sharpe 是怎麼被選中的")
    print(f"      有 Sharpe 記錄的**試驗列**只有 {len(sh_rows)} 個（不是我上一輪說的 14 個；")
    print(f"      14 是那幾列裡的數字總數，且我當時還誤把表格外正文的數字算了進去）：")
    for r in sh_rows:
        print(f"        #{r['id']:<5} {r['name'][:52]:<54} {len(r['sharpes'])} 個數字")
    print()
    print("      這幾筆的共同點：**全部是已經走到「策略層／組合層」才需要算 Sharpe 的候選**")
    print("      （52週高點策略層構造、等權重再平衡、借券使用率組合、regime overlay）。")
    print("      因子層的 IC 檢定不產生 Sharpe，所以停在因子層就 FAIL 的試驗一律沒有數字。")
    print(f"      ⇒ **V 是「走得夠遠者之間的離散度」，不是全體試驗的離散度，必然低估。**")
    print()
    both = [r for r in sh_rows if r["has_percentile"]]
    print(f"  (b) 百分位反推 Sharpe：**做不到**——同時有 Sharpe 與百分位的列有 {len(both)} 個。")
    print("      沒有共同樣本就無法擬合換算關係，硬換等於自己編一個係數。改用 Cybex 實測區間當上界。")
    print()

    # ── 三組 V ────────────────────────────────────────────────────────────
    v_ours = statistics.variance(flat) if len(flat) >= 2 else None
    scenarios = []
    if v_ours is not None:
        scenarios.append(("A. 我們自己的（僅走得遠者）",
                          v_ours, f"{len(sh_rows)} 個試驗列、{len(flat)} 個數字，標準差 {statistics.stdev(flat):.3f}",
                          "**低估**：只含走到策略層的候選"))
    scenarios.append(("B. Cybex 實測下界 0.441", CYBEX_SD_LOW ** 2,
                      "Cybex 加密市場實測", "外部參考，非台股實測值"))
    scenarios.append(("C. Cybex 實測上界 0.634", CYBEX_SD_HIGH ** 2,
                      "Cybex 加密市場實測", "外部參考，非台股實測值"))

    print("  三組 V 的 E[max SR] 並列：")
    print(f"    {'情境':<28}{'V':>8}{'E[max SR]':>12}   來源")
    results = []
    for label, v, src, caveat in scenarios:
        e = expected_max_sharpe(n_all, v)
        print(f"    {label:<28}{v:>8.4f}{e:>12.3f}   {src}")
        results.append({"scenario": label, "V": round(v, 4), "e_max_sr": round(e, 4),
                        "source": src, "caveat": caveat})
    print()

    # ── (c) 三個撐住的候選 ────────────────────────────────────────────────
    print("  (c) 三個撐住的候選在三組 V 下的比較：")
    surv_out = []
    for f in SURVIVORS:
        sr, where = survivor_sharpe(f)
        if sr is None:
            print(f"    {f:<20} **帳本沒有這個因子自己的 Sharpe 記錄 → 三組都無法比較**")
            surv_out.append({"factor": f, "sharpe": None, "where": where,
                             "verdict": "無法比較（帳本無該因子的 Sharpe）"})
            continue
        passes = [sr > r["e_max_sr"] for r in results]
        verdict = ("通過運氣上限（三組 V 全部高於）" if all(passes)
                   else "**暫定，V 估計不穩健**（並非三組都高於）")
        print(f"    {f:<20} Sharpe {sr:.3f}（{where}） → {verdict}")
        surv_out.append({"factor": f, "sharpe": sr, "where": where, "verdict": verdict})
    print()
    print("  ⚠ **更正前一輪的錯誤結論**：上一輪報「f_low_vol Sharpe 1.379 高於運氣上限」是錯的。")
    print("    那個 1.379 屬於第 107 列 `equal_weight_rebalance_sanity`，不是 f_low_vol。")
    print("    三個撐住的候選**都沒有**自己的 Sharpe 記錄，全部無法與 E[max SR] 比較。")
    print()
    print("  (d) 往後所有 DSR／E[max SR] 報告一律附 V 的來源與樣本數——已寫進 CLAUDE.md。")

    payload = {
        "generated_at": datetime.now(TZ).isoformat(),
        "n_all": n_all,
        "sharpe_trial_rows": len(sh_rows),
        "sharpe_numbers": len(flat),
        "rows_with_both_sharpe_and_percentile": len(both),
        "v_scenarios": results,
        "survivors": surv_out,
        "correction": "前一輪誤把第107列 equal_weight_rebalance_sanity 的 Sharpe 1.379 "
                      "當成 f_low_vol 的，並據此宣稱它高於運氣上限。該結論已撤回。",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
