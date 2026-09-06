# -*- coding: utf-8 -*-
"""選擇偏誤總帳：三軌各自與全體的 Bonferroni 門檻、DSR、分母自查、跨軌重複檢查。

（2026-09-07 Cowork 裁示 債務二.3／審視一。做法比照 Cybex `_r436_selection_bias_ledger.py`，
含 Acklam 反常態分位數近似，不需 scipy。**只抄方法，不抄任何參數**。）

這支取代先前的 `selection_bias_audit.py`（那支只算全體、不分軌、不做分母自查）。
舊那支保留不刪，因為它產出的 `data/selection_bias_audit.json` 是 2026-09-07 當下的
快照證據；新的候選一律用這支。

**這支解決的核心問題**：`TRIALS_LEDGER.md` 開頭寫「目前累積總數：37」，那個數字
自 2026-08-23 就沒再更新過，但帳本實際已經長到 179+ 筆。多重比較校正的分母錯了，
後面所有「通過校正」的判定就都要重算——**分母死了，結論就是死的**。

用法：
    python research/selection_bias_ledger.py            # 重算並更新 SELECTION_BIAS_LEDGER.md
    python research/selection_bias_ledger.py --check    # 只檢查不寫檔（給 CI/冒煙用）
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
OUT_MD = ROOT / "research" / "SELECTION_BIAS_LEDGER.md"
OUT_JSON = ROOT / "research" / "data" / "selection_bias_ledger.json"
TZ = timezone(timedelta(hours=8))
GAMMA = 0.5772156649015329
ALPHA = 0.05


# ── 統計工具（Acklam 近似，不需 scipy）────────────────────────────────────
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
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
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def expected_max_sharpe(n: int, var_sr: float) -> float:
    if n < 2 or var_sr <= 0:
        return 0.0
    return math.sqrt(var_sr) * ((1 - GAMMA) * norm_ppf(1 - 1.0 / n)
                                + GAMMA * norm_ppf(1 - 1.0 / (n * math.e)))


def required_percentile(n: int) -> float:
    return (1 - ALPHA / max(1, n)) * 100


# ── 帳本解析 ───────────────────────────────────────────────────────────────
FACTOR_RE = re.compile(r"`([^`]+)`")


TRACK_RE = re.compile(r"^(TW|US|FUT)$")


def parse() -> list[dict]:
    """解析帳本。

    **不用固定欄位索引**：這份帳本橫跨多次改版，欄數與欄序在不同區塊並不一致
    （第一版實作用 c[3] 當軌別，結果把因子名稱解析成 36 個「軌」，數字整個不能看）。
    改成掃整列文字找特徵，只有「軌別」這種有封閉值域的才用欄位定位並驗證值域。
    """
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.split("|")]
        if len(c) < 6 or not re.match(r"^\d+$", c[1]):
            continue
        blob = " ".join(c)
        # 軌別：只認 TW/US/FUT，在前幾欄裡找；找不到就標「未分軌」而不是硬取某一欄
        track = "未分軌"
        for cell in c[2:6]:
            if TRACK_RE.match(cell):
                track = cell
                break
        if track == "未分軌" and re.search(r"fut_", blob):
            track = "FUT"
        elif track == "未分軌" and re.search(r"f_us_|美股", blob):
            track = "US"
        # 判定：**從右往左找**含判定關鍵字的那一欄。
        # 不能掃整列——第二版就是這樣寫，結果備註裡提到別筆的 FAIL 就把這一筆也判成
        # FAIL，害「撐住」數字從 4 掉到 0。判定欄通常是倒數第二欄（最後一欄是備註），
        # 但欄數不固定，所以從右往左找第一個含關鍵字的欄最穩。
        verdict = "OTHER"
        for cell in reversed(c[2:]):
            if "CHEAP_PASS" in cell:
                verdict = "CHEAP_PASS"; break
            if "EXPERIMENTAL" in cell:
                verdict = "EXPERIMENTAL"; break
            if "FAIL" in cell:
                verdict = "FAIL"; break
            if "PASS" in cell:
                verdict = "PASS"; break
        pm = re.search(r"(\d+(?:\.\d+)?)\s*百分位", blob)
        nm = re.search(r"n=(\d+)", blob)
        fm = FACTOR_RE.search(blob)
        date = next((x for x in c[2:5] if re.match(r"^\d{4}-\d{2}-\d{2}$", x)), "")
        name = next((x for x in c[3:7] if len(x) > 6 and not TRACK_RE.match(x)), c[-2][:70])
        rows.append({
            "id": int(c[1]), "date": date, "track": track,
            "name": name[:70], "factor": fm.group(1) if fm else name[:40],
            "verdict": verdict, "verdict_raw": blob[-90:],
            "percentile": float(pm.group(1)) if pm else None,
            "claimed_n": int(nm.group(1)) if nm else None,
            "claims_correction": bool(re.search(r"校正|Bonferroni|FDR", blob)),
        })
    return rows


def factor_concept(name: str) -> str:
    """把 f_low_vol / fut_low_vol / us_low_vol 之類正規化成同一個概念，用來抓跨軌重複。"""
    n = name.lower()
    # 反覆剝前綴：`f_us_low_vol` 只剝一層會變成 `us_low_vol`，就跟 TW 的 `f_low_vol`
    # 對不起來，跨軌重複永遠偵測不到——總司令舉的 low_vol 例子就是這樣被漏掉的。
    while True:
        n2 = re.sub(r"^(f_|fut_|us_|tw_)", "", n)
        if n2 == n:
            break
        n = n2
    n = re.sub(r"_v\d+$", "", n)
    n = re.sub(r"[（(].*", "", n)
    return n.strip("_")


def main() -> int:
    rows = parse()
    check_only = "--check" in sys.argv

    # ── N 口徑：全體與分軌 ────────────────────────────────────────────────
    n_all = len(rows)
    by_track = defaultdict(list)
    for r in rows:
        by_track[r["track"]].append(r)
    n_track = {t: len(v) for t, v in sorted(by_track.items())}

    # ── 分母自查（債務二.2）──────────────────────────────────────────────
    # 每一筆宣稱做過校正的列：當時用的分母 vs 現在的正確分母，結論是否還站得住
    denom_rows = []
    for r in rows:
        if not r["claims_correction"] or r["percentile"] is None:
            continue
        claimed = r["claimed_n"]
        correct_track = n_track.get(r["track"], n_all)
        correct_all = n_all
        holds_claimed = (r["percentile"] >= required_percentile(claimed)) if claimed else None
        holds_track = r["percentile"] >= required_percentile(correct_track)
        holds_all = r["percentile"] >= required_percentile(correct_all)
        denom_rows.append({**r, "claimed_n": claimed, "n_track": correct_track,
                           "n_all": correct_all, "holds_claimed": holds_claimed,
                           "holds_track": holds_track, "holds_all": holds_all})

    passes = [r for r in rows if r["verdict"] in ("PASS", "CHEAP_PASS", "EXPERIMENTAL")]
    degraded = [r for r in denom_rows
                if r["verdict"] in ("PASS", "CHEAP_PASS", "EXPERIMENTAL") and not r["holds_all"]]
    survived = [r for r in denom_rows
                if r["verdict"] in ("PASS", "CHEAP_PASS", "EXPERIMENTAL") and r["holds_all"]]

    # ── 跨軌重複（審視一.2）──────────────────────────────────────────────
    # 只認 TW/US/FUT 之間的重複。把「未分軌」算進去會製造大量假陽性——
    # 同一個 TW 因子只要有幾列解析不到軌別，就會被算成「TW 與未分軌都測過」，
    # 看起來像跨軌重複其實不是。第一版就是這樣跑出 29 個假的。
    REAL_TRACKS = {"TW", "US", "FUT"}
    concept_tracks = defaultdict(set)
    for r in rows:
        if r["track"] in REAL_TRACKS:
            concept_tracks[factor_concept(r["factor"])].add(r["track"])
    cross = {k: sorted(v) for k, v in concept_tracks.items() if len(v) > 1}

    # ── DSR ───────────────────────────────────────────────────────────────
    sharpe_rows = [r for r in rows if re.search(r"[Ss]harpe", r["verdict_raw"])]
    dsr_note = (f"帳本中僅 {len(sharpe_rows)} 筆記錄 Sharpe，算不出試驗間 Sharpe 變異數 V"
                "（E[max SR] 的必要輸入）。**不編數字**；改列各 N 下的 E[max SR] 作決策參考。")

    # ── 輸出 ──────────────────────────────────────────────────────────────
    now = datetime.now(TZ)
    L = []
    L.append("# SELECTION_BIAS_LEDGER.md — 跨輪次選擇偏誤總帳")
    L.append("")
    L.append(f"**自動產生**：`research/selection_bias_ledger.py`（{now.strftime('%Y-%m-%d %H:%M')}）。")
    L.append("每新增候選就重跑一次。做法比照 Cybex `_r436_selection_bias_ledger.py`，")
    L.append("**只抄方法不抄參數**（Cybex 的閾值來自加密市場，對台股零效力）。")
    L.append("")
    L.append("> 這份檔案存在的理由：每輪的隨機控制組控制的是「**單一機制**是不是偽影」，")
    L.append("> 不是「這麼多輪裡**挑出來的這一組**整體是不是過擬合」。這裡是那本全域總帳。")
    L.append("")
    L.append("## 1. 試驗總數（分母）")
    L.append("")
    L.append("| 口徑 | N | Bonferroni 門檻（α=0.05 單邊） |")
    L.append("|---|---:|---:|")
    L.append(f"| **全體** | {n_all} | {required_percentile(n_all):.4f} 百分位 |")
    for t, n in n_track.items():
        L.append(f"| 分軌 {t} | {n} | {required_percentile(n):.4f} 百分位 |")
    L.append("")
    L.append("## 2. 分母自查（債務二.2）")
    L.append("")
    L.append("每一筆宣稱「通過多重比較校正」的判定，當時實際用的分母是多少、")
    L.append("改用正確分母後是否仍成立。**不成立者一律降級**。")
    L.append("")
    L.append("| # | 日期 | 軌 | 名稱 | 百分位 | 當時分母 | 當時成立 | 分軌分母 | 全體分母 | 全體下成立 |")
    L.append("|---|---|---|---|---:|---:|:-:|---:|---:|:-:|")
    for r in sorted(denom_rows, key=lambda x: x["id"]):
        mark = lambda b: "✓" if b else ("✗" if b is False else "—")
        L.append(f"| {r['id']} | {r['date']} | {r['track']} | {r['name'][:38]} | "
                 f"{r['percentile']:.1f} | {r['claimed_n'] or '未記'} | {mark(r['holds_claimed'])} | "
                 f"{r['n_track']} | {r['n_all']} | {mark(r['holds_all'])} |")
    L.append("")
    L.append(f"**結論**：宣稱通過校正且有百分位數字的共 {len(denom_rows)} 筆；")
    L.append(f"其中判定為 PASS／CHEAP_PASS／EXPERIMENTAL 的，在正確的全體分母 N={n_all} 下")
    L.append(f"**撐住 {len(survived)} 筆、倒下 {len(degraded)} 筆**。")
    L.append("")
    if degraded:
        L.append("倒下的（應降級）：")
        for r in sorted(degraded, key=lambda x: x["id"]):
            L.append(f"- #{r['id']} `{r['factor']}`（{r['percentile']:.1f} 百分位，"
                     f"當時分母 {r['claimed_n'] or '未記'}，正確分母 {n_all}）")
        L.append("")
    L.append("## 3. Deflated Sharpe")
    L.append("")
    L.append(dsr_note)
    L.append("")
    L.append("| 口徑 | N | E[max SR]（示意，假設試驗間 SR 標準差 0.5） |")
    L.append("|---|---:|---:|")
    L.append(f"| 全體 | {n_all} | {expected_max_sharpe(n_all, 0.25):.3f} |")
    for t, n in n_track.items():
        L.append(f"| {t} | {n} | {expected_max_sharpe(n, 0.25):.3f} |")
    L.append("")
    L.append("**解讀**：就算所有策略的真實 Sharpe 都是 0，只要搜得夠多，最好的那一個")
    L.append("看起來也會有這麼高的 Sharpe。觀察到的 Sharpe 沒有明顯超過這個數，就沒有意義。")
    L.append("")
    L.append("## 4. 跨軌重複因子（審視一.2）")
    L.append("")
    L.append("「分軌獨立分母」的前提是三軌為獨立假設家族。同一個因子概念在多軌測過，")
    L.append("那就不是獨立——分軌分母會系統性低估真實的搜尋次數。")
    L.append("")
    if cross:
        L.append(f"**跨軌重複的因子概念共 {len(cross)} 個**：")
        L.append("")
        L.append("| 因子概念 | 出現在哪些軌 |")
        L.append("|---|---|")
        for k, v in sorted(cross.items()):
            L.append(f"| `{k}` | {'、'.join(v)} |")
    else:
        L.append("目前沒有偵測到跨軌重複的因子概念。")
    L.append("")
    L.append("## 5. 誠實揭露")
    L.append("")
    L.append(f"- 帳本共 {n_all} 列；標記為通過（PASS/CHEAP_PASS/EXPERIMENTAL）的 {len(passes)} 筆，")
    L.append(f"  但其中只有 {len(denom_rows)} 筆留下可比較的統計量，其餘無法重評——")
    L.append("  **既不能算撐住，也不能算倒下**，它們是「當初沒留下足以判斷的證據」。")
    L.append("- DSR 目前算不出來的根因是登記欄位不足。往後登記必須同時記 Sharpe、T、skew、kurt。")
    L.append("- 分軌 vs 全體分母該用哪個，本檔只給數字，**不預設結論**，由總司令裁示。")
    L.append("")

    md = "\n".join(L) + "\n"
    payload = {
        "generated_at": now.isoformat(), "n_all": n_all, "n_track": n_track,
        "claims_checked": len(denom_rows), "survived": len(survived), "degraded": len(degraded),
        "degraded_items": [{"id": r["id"], "factor": r["factor"], "percentile": r["percentile"],
                            "claimed_n": r["claimed_n"]} for r in degraded],
        "cross_track_factors": cross, "dsr_computable": False, "dsr_note": dsr_note,
    }

    if check_only:
        print(f"N={n_all}｜宣稱校正 {len(denom_rows)} 筆｜撐住 {len(survived)}｜倒下 {len(degraded)}"
              f"｜跨軌重複 {len(cross)} 個")
        return 0

    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 順手把 TRIALS_LEDGER 開頭那個死掉的數字修好（債務二.1）────────────
    txt = LEDGER.read_text(encoding="utf-8")
    new_line = (f"**目前累積總數（可統計檢定的試驗）：{n_all}**"
                f"（{now.strftime('%Y-%m-%d')} 由 `research/selection_bias_ledger.py` 自動計算並回寫；"
                "**不要手動改這個數字**——它自 2026-08-23 起被手動寫死成 37 而實際已成長數倍，"
                "害後續所有多重比較校正用了錯的分母。分軌分母見 `SELECTION_BIAS_LEDGER.md`。）")
    txt2 = re.sub(r"\*\*目前累積總數（可統計檢定的試驗）：\d+\*\*（[^）]*）", new_line, txt, count=1)
    if txt2 != txt:
        LEDGER.write_text(txt2, encoding="utf-8", newline="\n")
        print(f"已回寫 TRIALS_LEDGER 累積總數：{n_all}")

    print(f"N（全體）={n_all}　分軌={n_track}")
    print(f"宣稱校正 {len(denom_rows)} 筆 → 撐住 {len(survived)}、**倒下 {len(degraded)}**")
    print(f"跨軌重複因子概念 {len(cross)} 個")
    print(f"→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
