# -*- coding: utf-8 -*-
"""用 Deflated Sharpe 重評三軌全部 CHEAP_PASS/PASS/EXPERIMENTAL 候選，回報幾個倒下。

（2026-09-07 `PENDING_QUEUE.md` Cowork.審視1.1。裁示原話：「用 DSR 對現存所有
CHEAP_PASS/PASS 候選（TW/US/FUT 三軌）重評，回報有幾個在 DSR 下倒下。」）

**這支跟 `selection_bias_ledger.py` 的差別**：那支用「百分位 vs Bonferroni 門檻」重評，
因為帳本裡只有百分位；DSR 需要 Sharpe/T/skew/kurtosis，債務2.3 當時的結論是「算不出來，
不編數字」。這支不接受那個結論就停在那裡，照 `CLAUDE.md` 七、資料原則的回退鏈實際去找：

1. **主來源**：`TRIALS_REGISTRY.jsonl` 的 `dsr_inputs`（債務2.4 新增的欄位，只有新登記才有）。
2. **備援**：`research/data/*.csv` 裡真的有 `sharpe` 欄位的回測輸出（20 個檔案），
   用檔名 token 對回候選代碼。
3. **由已有欄位推導**：`start`/`end`（或 `n_days`）推觀測期數 T。
4. 三條都走不通才記「無法計算」，並**分類原因**，不靜默記 None。

**所有假設都刻意偏向「讓候選比較容易通過」**，這樣「連在這種寬鬆假設下都倒下」才是
穩健結論（`CLAUDE.md`「最高投資原則」：寧可誤殺，不可放行）：

- skew=0、kurtosis=3（常態）。真實策略多半左偏厚尾，那會**壓低** DSR，所以常態假設是上界。
- 試驗間 Sharpe 變異數 V 用實測樣本估，另外附一整排 V 的敏感度與**臨界 V**
  （DSR 剛好等於 0.95 的 V），讓結論不綁死在單一個 V 假設上。

用法：
    python research/dsr_reeval.py            # 重算並寫 research/DSR_REEVAL.md
    python research/dsr_reeval.py --check    # 只印摘要不寫檔
"""
from __future__ import annotations

import csv
import glob
import math
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from candidate_report import (  # noqa: E402
    DSR_MIN,
    CandidateStats,
    deflated_sharpe,
    default_n_trials,
    report_candidate,
)
from selection_bias_ledger import expected_max_sharpe  # noqa: E402
from trial_registry import registry_records, trial_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
DATA = RESEARCH / "data"
OUT_MD = RESEARCH / "DSR_REEVAL.md"
TZ = timezone(timedelta(hours=8))

CANDIDATE_VERDICTS = ("CHEAP_PASS", "PASS", "EXPERIMENTAL")
TRADING_DAYS = 252
# 這個檔是大盤基準（買進持有 TAIEX），不是我們搜尋過的試驗，不能算進試驗 Sharpe 分布。
NOT_A_TRIAL = ("benchmark_taiex_stats.csv",)
# V 敏感度網格：以「試驗間年化 Sharpe 標準差」表示，比變異數好讀。
V_GRID_ANN_SD = (0.10, 0.25, 0.50, 0.75, 1.00)


def _business_days(a: date, b: date) -> int:
    """兩個日期之間的交易日數估計（扣週末，不扣國定假日）。

    這是**估計值**，會略高於真實交易日數；T 偏高會讓 DSR 偏高，
    方向上同樣是「讓候選比較容易通過」的上界假設，跟這支的其他假設一致。
    """
    days = (b - a).days
    if days <= 0:
        return 0
    return max(2, int(round(days * 5 / 7)))


def collect_sharpe_rows() -> list[dict]:
    """掃 `research/data/*.csv`，抓所有真的有 `sharpe` 數值的回測輸出列。"""
    out = []
    for f in sorted(glob.glob(str(DATA / "*.csv"))):
        name = os.path.basename(f)
        if name in NOT_A_TRIAL:
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                head = fh.readline()
                if "sharpe" not in [c.strip() for c in head.split(",")]:
                    continue
                fh.seek(0)
                for r in csv.DictReader(fh):
                    raw = (r.get("sharpe") or "").strip()
                    if not raw:
                        continue
                    try:
                        sr = float(raw)
                    except ValueError:
                        continue
                    t = None
                    if (r.get("n_days") or "").strip():
                        try:
                            t = int(float(r["n_days"]))
                        except ValueError:
                            t = None
                    if t is None and (r.get("start") or "").strip() and (r.get("end") or "").strip():
                        try:
                            t = _business_days(
                                datetime.strptime(r["start"][:10], "%Y-%m-%d").date(),
                                datetime.strptime(r["end"][:10], "%Y-%m-%d").date())
                        except ValueError:
                            t = None
                    out.append({
                        "file": name, "label": (r.get("label") or "").strip(),
                        "cadence": (r.get("cadence") or "").strip(),
                        "sharpe_ann": sr, "n_obs": t,
                    })
        except OSError:
            continue
    return out


def name_cell(tid: int) -> str:
    """取帳本該列的「假說名稱」欄（第 4 欄）。

    **不能拿整列去比對代碼**：備註欄大量引用別筆試驗的代碼（`f52w_high_portfolio_v1`
    這種），用整列比對會把別人的 Sharpe 安到這一筆頭上——第一版就這樣把 #182
    `MI_5MINS` 對到了 `f52w_high_portfolio_v1_results.csv`，數字看起來很正常，
    但那根本不是它的績效。
    """
    from trial_registry import LEDGER, _split_cells

    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = _split_cells(line)
        if len(c) >= 5 and re.fullmatch(r"\d+", c[0]) and int(c[0]) == tid \
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", c[1]):
            # 只回「假說名稱」欄。型態欄（c[4]）常寫「同 `xxx_portfolio_v1` 手法」
            # 這種對照引用，一起拿去比對又會配到別人的績效（#85 就這樣配到
            # `dividend_yield_portfolio_v1`，但它其實是 52 週高點那條）。
            return c[3]
    return ""


def factor_tokens(blob: str) -> list[str]:
    """從帳本列抓出所有反引號代碼（`f_low_vol`、`pead_portfolio_v1`…）。

    **必須含底線且長度 ≥8**：名稱欄裡也會出現 `high`／`open`／`close` 這種泛用字，
    拿它們去比對檔名會亂配——第二版就用 `high` 把 #182（日內/隔夜報酬結構分解）
    對到了 `f52w_high_portfolio_v1_results.csv`。寧可少配、記成「無法計算」，
    也不要配錯：配錯等於把別人的績效安到這一筆頭上，比沒有數字更糟。
    """
    # 也收 `xxx_portfolio_v1.py` 這種帶副檔名的腳本名（去掉 `.py` 再比對）：
    # 候選的因子代碼常跟產生 CSV 的腳本名不同（`f_52w_high_prox` vs
    # `f52w_high_portfolio_v1.py`），只認因子代碼會漏掉本來查得到的 Sharpe。
    raw = re.findall(r"`([A-Za-z0-9_]+)(?:\.py)?`", blob)
    toks = [t for t in raw if "_" in t and len(t) >= 8]
    seen, out = set(), []
    for t in toks:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out


def match_sharpe(tokens: list[str], sharpe_rows: list[dict]) -> tuple[dict | None, str, str]:
    """把候選代碼對回有 Sharpe 的回測輸出檔。

    對到多列（TRAIN/VALIDATION、多個成本倍數）時取**最高的 Sharpe**——同樣是
    「讓候選比較容易通過」的上界方向；連最好的那一組都倒下，結論才穩。
    """
    # **只認名稱欄的第一個代碼**，也就是候選自己的代碼。名稱欄後面常寫
    # 「比照 `dividend_yield_portfolio_v1` 的手法」這種對照引用，往下找第二、第三個
    # token 就會配到別人的績效（#85 是 52 週高點那條，卻被配到股利率那支的 Sharpe）。
    # 代價是覆蓋率變低、更多筆記成「無法計算」——這個方向的錯誤是安全的，
    # 配錯把別人的績效安到這一筆頭上則不是。
    for tok in tokens[:1]:
        hits = [r for r in sharpe_rows if tok.lower() in r["file"].lower() and r["n_obs"]]
        if hits:
            best = max(hits, key=lambda r: r["sharpe_ann"])
            src = (f"`{tok}` → `research/data/{best['file']}`"
                   f"（{best['label'] or '無期別欄'}"
                   f"{'／' + best['cadence'] if best['cadence'] else ''}，同檔取最高 Sharpe）")
            return best, src, tok
    return None, "", ""


def breakeven_var(sr_ann: float, n_obs: int, n_trials: int) -> float | None:
    """求「DSR 剛好等於 0.95」的試驗間 Sharpe 變異數 V（日尺度），二分搜尋。

    V 越大 → SR0 越高 → DSR 越低，所以 DSR 對 V 單調遞減，二分法成立。
    回傳 None 代表「連 V→0 都過不了 0.95」——那是候選自己的 Sharpe 太低，
    跟搜尋次數無關。
    """
    sr_d = sr_ann / math.sqrt(TRADING_DAYS)

    def dsr_at(v_d: float) -> float:
        return deflated_sharpe(CandidateStats(sr_d, n_obs, 0.0, 3.0), n_trials, v_d)["dsr"]

    lo, hi = 1e-12, 4.0 / TRADING_DAYS  # 上界＝年化 Sharpe 標準差 2.0，遠超任何合理值
    if dsr_at(lo) < DSR_MIN:
        return None
    if dsr_at(hi) >= DSR_MIN:
        return hi
    for _ in range(80):
        mid = (lo + hi) / 2
        if dsr_at(mid) >= DSR_MIN:
            lo = mid
        else:
            hi = mid
    return lo


def main() -> int:
    check_only = "--check" in sys.argv
    sharpe_rows = collect_sharpe_rows()
    n_trials, n_src = default_n_trials()

    # ── 試驗間 Sharpe 變異數 V：用實測樣本估（年化 → 日尺度）──────────────
    ann = [r["sharpe_ann"] for r in sharpe_rows]
    if len(ann) >= 2:
        mean_ann = sum(ann) / len(ann)
        var_ann = sum((x - mean_ann) ** 2 for x in ann) / (len(ann) - 1)
    else:
        mean_ann = var_ann = float("nan")
    var_daily = var_ann / TRADING_DAYS

    # ── 逐一重評候選 ──────────────────────────────────────────────────────
    rows = [r for r in trial_rows() if r.verdict in CANDIDATE_VERDICTS]
    reg_inputs = {r["id"]: r.get("dsr_inputs") for r in registry_records()}

    results = []
    for r in rows:
        # 只用「假說名稱／型態」欄的代碼比對，備註欄引用別筆試驗的代碼不算數
        toks = factor_tokens(name_cell(r.tid))
        src = ""
        matched_tok = ""
        stats = None
        sr_ann = None
        di = reg_inputs.get(r.tid)
        if isinstance(di, dict) and di.get("sharpe") is not None:
            stats = CandidateStats(di["sharpe"], di["n_obs"], di["skew"], di["kurtosis"])
            sr_ann = di["sharpe"] * math.sqrt(TRADING_DAYS)
            src = "`TRIALS_REGISTRY.jsonl` 的 `dsr_inputs`（一手登記）"
        else:
            hit, src, matched_tok = match_sharpe(toks, sharpe_rows)
            if hit:
                sr_ann = hit["sharpe_ann"]
                stats = CandidateStats(sr_ann / math.sqrt(TRADING_DAYS), hit["n_obs"], 0.0, 3.0,
                                       freq_label="日（由年化 Sharpe 換算）")

        item = {"tid": r.tid, "track": r.track or "未分軌", "verdict": r.verdict,
                "token": matched_tok or (toks[0] if toks else "(無代碼)"),
                "src": src, "sr_ann": sr_ann}
        if stats is None:
            item["status"] = "無法計算"
            item["why"] = "帳本與 `research/data/*.csv` 都找不到這個候選的 Sharpe"
            results.append(item)
            continue

        # 用債務2.4 立的唯一出口產生判定，不自己另寫一套門檻
        rep = report_candidate(key=f"#{r.tid}", headline={"帳本判定": r.verdict},
                               stats=stats, n_trials=n_trials, var_sr_trials=var_daily,
                               track=item["track"])
        item["dsr"] = rep["dsr"]
        item["n_obs"] = stats.n_obs
        item["status"] = "撐住" if rep["admissible"] else "倒下"
        bev = breakeven_var(sr_ann, stats.n_obs, n_trials)
        item["breakeven_sd_ann"] = (math.sqrt(bev * TRADING_DAYS) if bev else None)
        results.append(item)

    computable = [x for x in results if x["status"] in ("撐住", "倒下")]
    fell = [x for x in results if x["status"] == "倒下"]
    held = [x for x in results if x["status"] == "撐住"]
    uncomputable = [x for x in results if x["status"] == "無法計算"]

    by_track = defaultdict(lambda: [0, 0, 0])
    for x in results:
        b = by_track[x["track"]]
        b[0] += 1
        if x["status"] == "倒下":
            b[1] += 1
        elif x["status"] == "撐住":
            b[2] += 1

    if check_only:
        print(f"候選 {len(results)} 筆｜可算 DSR {len(computable)}｜倒下 {len(fell)}｜"
              f"撐住 {len(held)}｜無法計算 {len(uncomputable)}")
        return 0

    now = datetime.now(TZ)
    sd_ann = math.sqrt(var_ann) if var_ann == var_ann else float("nan")
    L = []
    L.append("# DSR_REEVAL.md — 用 Deflated Sharpe 重評現存候選（Cowork.審視1.1）")
    L.append("")
    L.append(f"**自動產生**：`research/dsr_reeval.py`（{now.strftime('%Y-%m-%d %H:%M')}）。"
             "每次新增候選或新增回測輸出後重跑。")
    L.append("")
    L.append("## 0. 一句話結論")
    L.append("")
    L.append(f"帳本裡判定為 CHEAP_PASS／PASS／EXPERIMENTAL 的候選共 **{len(results)} 筆**；"
             f"其中 **{len(computable)} 筆湊得齊 DSR 的輸入**，"
             f"**倒下 {len(fell)} 筆、撐住 {len(held)} 筆**；"
             f"剩下 **{len(uncomputable)} 筆連 Sharpe 都沒有，無法計算**——"
             "**無法計算不等於通過**，這些一律不得提請審核。")
    L.append("")
    L.append("## 1. 這次是怎麼把「算不出來」變成「算得出來」的")
    L.append("")
    L.append("債務2.3 當時的結論是「帳本無 Sharpe，DSR 算不出來，不編數字」。這支照 "
             "`CLAUDE.md` 七、資料原則的回退鏈再找一次：")
    L.append("")
    L.append("1. 主來源 `TRIALS_REGISTRY.jsonl` 的 `dsr_inputs` —— 債務2.4 才新增的欄位，"
             "只有新登記才有，歷史候選一筆都沒有。")
    L.append(f"2. 備援 `research/data/*.csv` —— **{len({r['file'] for r in sharpe_rows})} 個檔案、"
             f"{len(sharpe_rows)} 列真的有 `sharpe` 數值**，用檔名 token 對回候選代碼。")
    L.append("3. 由已有欄位推導 T —— 有 `n_days` 就用，沒有就用 `start`/`end` 推交易日數。")
    L.append("")
    L.append("**全部假設都刻意偏向「讓候選容易通過」**，所以「連這樣都倒下」才是穩健結論：")
    L.append("")
    L.append("- skew=0、kurt=3（常態）。真實策略多半左偏厚尾，那會壓低 DSR。")
    L.append("- 同一個候選對到多列時取**最高**的 Sharpe。")
    L.append("- T 用扣週末不扣國定假日的估計值（偏高，DSR 偏高）。")
    L.append("")
    L.append("## 2. 分母與試驗間 Sharpe 分布")
    L.append("")
    L.append("| 項目 | 值 | 來源 |")
    L.append("|---|---|---|")
    L.append(f"| 試驗次數 N | {n_trials} | {n_src} |")
    L.append(f"| 實測試驗 Sharpe 筆數 | {len(sharpe_rows)} | `research/data/*.csv` 的 `sharpe` 欄"
             f"（已排除大盤基準 {'／'.join(NOT_A_TRIAL)}） |")
    L.append(f"| 試驗 Sharpe 平均（年化） | {mean_ann:.4f} | 同上 |")
    L.append(f"| 試驗 Sharpe 標準差（年化） | {sd_ann:.4f} | 同上 |")
    L.append(f"| V（日尺度變異數，DSR 用） | {var_daily:.6f} | 年化變異數 ÷ {TRADING_DAYS} |")
    L.append(f"| SR0＝期望最大 Sharpe（日） | {expected_max_sharpe(n_trials, var_daily):.4f} | "
             f"＝年化 {expected_max_sharpe(n_trials, var_daily) * math.sqrt(TRADING_DAYS):.3f} |")
    L.append("")
    L.append("**怎麼讀**：就算所有策略的真實 Sharpe 都是 0，搜了 "
             f"{n_trials} 次之後，最好的那一個看起來也會有年化 "
             f"{expected_max_sharpe(n_trials, var_daily) * math.sqrt(TRADING_DAYS):.2f} 的 Sharpe。"
             "候選的 Sharpe 沒有明顯超過這條線，它就只是搜尋次數的產物。")
    L.append("")
    L.append("**誠實限制**：這 "
             f"{len(sharpe_rows)} 列 Sharpe 只涵蓋有寫出 CSV 的**組合/策略層**回測；"
             "因子層 IC 測試本來就沒有 Sharpe，所以 V 是「策略層試驗」的離散度，"
             "拿它當全部 " + str(n_trials) + " 次試驗的離散度是一個近似。"
             "V 估太小會**高估** DSR（門檻變鬆），所以下面每一列都附臨界 V。")
    L.append("")
    L.append("## 3. V 敏感度：門檻對假設有多敏感")
    L.append("")
    L.append("| 試驗 Sharpe 標準差（年化） | SR0（年化） |")
    L.append("|---:|---:|")
    for sd in V_GRID_ANN_SD:
        v_d = sd * sd / TRADING_DAYS
        L.append(f"| {sd:.2f} | {expected_max_sharpe(n_trials, v_d) * math.sqrt(TRADING_DAYS):.3f} |")
    L.append("")
    L.append("## 4. 逐筆重評")
    L.append("")
    L.append("「臨界 V」＝要讓這個候選剛好通過 DSR 0.95，試驗間 Sharpe 標準差最多只能多小。"
             f"實測值是 {sd_ann:.3f}；臨界值**低於**實測值就是倒下，而且差越多倒得越徹底。")
    L.append("")
    L.append("| 帳本# | 軌 | 代碼 | 帳本判定 | 年化 Sharpe | T | DSR | 臨界 Sharpe 標準差 | 結果 | Sharpe 來源 |")
    L.append("|---:|---|---|---|---:|---:|---:|---:|:-:|---|")
    for x in sorted(results, key=lambda z: (z["status"] != "撐住", z["status"] != "倒下", -z["tid"])):
        if x["status"] == "無法計算":
            L.append(f"| {x['tid']} | {x['track']} | `{x['token']}` | {x['verdict']} | — | — | — | — | "
                     f"**無法計算** | {x['why']} |")
        else:
            bev = x["breakeven_sd_ann"]
            L.append(f"| {x['tid']} | {x['track']} | `{x['token']}` | {x['verdict']} | "
                     f"{x['sr_ann']:.3f} | {x['n_obs']} | {x['dsr']:.4f} | "
                     f"{(f'{bev:.3f}' if bev else '過不了（與搜尋次數無關）')} | "
                     f"**{x['status']}** | {x['src']} |")
    L.append("")
    L.append("## 5. 分軌統計")
    L.append("")
    L.append("| 軌 | 候選數 | 倒下 | 撐住 | 無法計算 |")
    L.append("|---|---:|---:|---:|---:|")
    for t, (tot, f_, h_) in sorted(by_track.items()):
        L.append(f"| {t} | {tot} | {f_} | {h_} | {tot - f_ - h_} |")
    L.append("")
    L.append("## 6. 誠實揭露")
    L.append("")
    L.append(f"- **{len(uncomputable)}/{len(results)} 筆算不出 DSR**，因為當初的試驗根本沒有留下 "
             "Sharpe。這不是這支程式的缺陷，是登記欄位不足的存量債務；債務2.4 已讓 "
             "`register_trial()` 能收 Sharpe/T/skew/kurtosis，往後新登記的才算得出來。")
    L.append("- 算不出來的那些**既不能算撐住、也不能算倒下**，但依債務2.4 的規則"
             "**一律不得提請審核**——算不出來不等於通過。")
    L.append("- **覆蓋率是刻意壓低的**：只認名稱欄第一個代碼去對檔名。名稱欄常寫"
             "「比照 `xxx_portfolio_v1` 手法」這種對照引用，往下多找一個 token 就會"
             "多對到 2～3 筆，但其中有把別人的績效安到這一筆頭上的（實測過：#85 是"
             "52 週高點那條，卻會被配到股利率那支的 Sharpe）。**配錯比沒有數字更糟**，"
             "所以寧可少配。要提高覆蓋率的正解是登記時就記 Sharpe，不是放寬比對。")
    L.append("- 這裡的 Sharpe 是**用檔名對回來**的，不是登記當下記下來的。"
             "對錯與否可從「Sharpe 來源」欄逐筆覆核；有疑義的以帳本原文為準。")
    L.append("- V 的口徑（策略層 vs 全部試驗）與 N 的口徑（190 vs 223）都還沒有定論，"
             "所以第 3 節的敏感度表與第 4 節的臨界值比單一個 DSR 數字更該看。")
    L.append("")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"候選 {len(results)} 筆｜可算 DSR {len(computable)}｜**倒下 {len(fell)}**｜"
          f"撐住 {len(held)}｜無法計算 {len(uncomputable)}")
    print(f"試驗 Sharpe 樣本 {len(sharpe_rows)} 列，年化平均 {mean_ann:.4f}／標準差 {sd_ann:.4f}")
    print(f"N={n_trials}｜SR0（年化）="
          f"{expected_max_sharpe(n_trials, var_daily) * math.sqrt(TRADING_DAYS):.3f}")
    print(f"→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
