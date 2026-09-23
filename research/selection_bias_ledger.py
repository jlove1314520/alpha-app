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
# hypothesis_queue 馬拉松輪次的「登記來源」備註固定含這幾個反引號詞
# （`trial_registry.register_trial()`、`HYPOTHESIS_QUEUE.md`、`evaluate_factor()`…），
# 這些是工具/文件名不是因子名。FACTOR_RE 若原樣取「第一個反引號詞」會把它們誤判成
# 因子概念，害多筆彼此無關的列被判成「跨軌重複因子」（實測：曾誤報
# `hypothesis_queue.md`／`trial_registry.register_trial` 為跨軌重複，2026-09-10 查出）。
FACTOR_JUNK_RE = re.compile(r"\.md$|register_trial|evaluate_factor|is_holdout_consumed", re.IGNORECASE)
TRACK_RE = re.compile(r"^(TW|US|FUT)$")


def _pick_factor(blob: str, fallback: str) -> str:
    """挑反引號詞當因子名，跳過檔名/函式呼叫這類工具字串（見 FACTOR_JUNK_RE）。"""
    for m in FACTOR_RE.finditer(blob):
        cand = m.group(1)
        if FACTOR_JUNK_RE.search(cand) or "(" in cand or ")" in cand:
            continue
        return cand
    return fallback


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
        # 2026-08-25 FDR重新評分對照表（見 TRIALS_LEDGER.md 該節）第二欄是
        # `#2` 這種試驗編號引用、不是日期——它是把「上面已登記試驗」重算一次
        # 判定，不是新試驗。之前沒濾掉它：那 33 列的第一欄剛好也是 1~33 的
        # 連續整數（表格的「排名」欄，不是試驗編號），會通過 `c[1]` 的數字檢查、
        # 混進試驗列一起算 N，且跟真正的試驗 #1~#33 撞號。
        # 判準比照 `trial_registry.py parse_ledger()`：真試驗列的日期欄必須是
        # YYYY-MM-DD；FDR 對照表列不是，直接跳過，不算進 N。
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", c[2]):
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
        # 2026-09-20總司令裁示【depth-1閘門設計缺陷要修；p=0.053作廢要
        # 正式處理】二後修好的既有bug：這個清單原本只認CHEAP_PASS/
        # EXPERIMENTAL/FAIL/PASS四種，`trial_registry.py::VALID_VERDICTS`
        # 其實還有IRREPRODUCIBLE/VIOLATES_SURVIVAL/ABANDONED/REFUTED/
        # 未結案五種完全沒被辨識——實測發現：新登記的IRREPRODUCIBLE列
        # （#319）因為「備註」欄裡剛好用散文提到另一筆的「FAIL」判定，
        # 從右往左掃到備註欄就先比對到FAIL、根本沒掃到再往左一欄真正的
        # 判定欄，被誤判成FAIL。往後任何VIOLATES_SURVIVAL（天條一）等
        # 列都有同樣風險，一併修好，不只修IRREPRODUCIBLE這一個。
        verdict = "OTHER"
        for cell in reversed(c[2:]):
            # FRAMEWORK_CHECK_FAILED必須排在FRAMEWORK_CHECK前面檢查——後者是
            # 前者的字串子集，順序顛倒會把FRAMEWORK_CHECK_FAILED誤判成FRAMEWORK_CHECK。
            if "FRAMEWORK_CHECK_FAILED" in cell:
                verdict = "FRAMEWORK_CHECK_FAILED"; break
            if "FRAMEWORK_CHECK" in cell:
                verdict = "FRAMEWORK_CHECK"; break
            if "CHEAP_PASS" in cell:
                verdict = "CHEAP_PASS"; break
            if "EXPERIMENTAL" in cell:
                verdict = "EXPERIMENTAL"; break
            if "IRREPRODUCIBLE" in cell:
                verdict = "IRREPRODUCIBLE"; break
            if "VIOLATES_SURVIVAL" in cell:
                verdict = "VIOLATES_SURVIVAL"; break
            if "ABANDONED" in cell:
                verdict = "ABANDONED"; break
            if "REFUTED" in cell:
                verdict = "REFUTED"; break
            if "未結案" in cell:
                verdict = "未結案"; break
            if "FAIL" in cell:
                verdict = "FAIL"; break
            if "PASS" in cell:
                verdict = "PASS"; break
        pm = re.search(r"(\d+(?:\.\d+)?)\s*百分位", blob)
        nm = re.search(r"n=(\d+)", blob)
        date = next((x for x in c[2:5] if re.match(r"^\d{4}-\d{2}-\d{2}$", x)), "")
        # "hypothesis_queue" 是馬拉松輪次拿來標記軌別欄位的固定字面值（非因子名），
        # 排除它才不會讓一堆彼此無關的候選都以同一個假因子名「撞名」。
        name = next((x for x in c[3:7]
                     if len(x) > 6 and not TRACK_RE.match(x)
                     and x.strip().lower() != "hypothesis_queue"), c[-2][:70])
        rows.append({
            "id": int(c[1]), "date": date, "track": track,
            "name": name[:70], "factor": _pick_factor(blob, name[:40]),
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

    # 2026-09-23總司令裁示【修正兩個系統性錯誤＋兩件待審閱結案】結案.二
    # 第3點：FRAMEWORK_CHECK列（隨機選股佔位訊號驗證回測框架本身，不是
    # alpha檢定）從一開始就不計入N（連總N都不算，跟IRREPRODUCIBLE/
    # DUPLICATE/INVALID_BUG「仍計入總N、排除出有效N」不同——那些是
    # 「檢定過但有問題」，這個是「從頭到尾就不是要檢定alpha」）。
    # FRAMEWORK_CHECK_FAILED（驗.一新增）同一種語意處理：#358原本以為
    # 框架驗證通過，後來發現連框架驗證本身都因複利bug而不成立，一樣
    # 不計入N（不是「alpha試驗失敗」，是「這次執行從頭到尾就沒有檢定
    # alpha的資格」）。
    framework_check_rows = [r for r in rows if r["verdict"] in ("FRAMEWORK_CHECK", "FRAMEWORK_CHECK_FAILED")]
    rows = [r for r in rows if r["verdict"] not in ("FRAMEWORK_CHECK", "FRAMEWORK_CHECK_FAILED")]

    # ── N 口徑：全體與分軌 ────────────────────────────────────────────────
    n_all = len(rows)
    by_track = defaultdict(list)
    for r in rows:
        by_track[r["track"]].append(r)
    n_track = {t: len(v) for t, v in sorted(by_track.items())}

    # ── 有效N vs 總N（2026-09-20總司令裁示【depth-1閘門設計缺陷要修；
    # p=0.053作廢要正式處理】二）：IRREPRODUCIBLE的列（登記過的數值結果，
    # 用現有程式碼/資料重跑對不上，見`trial_registry.py::VALID_VERDICTS`
    # 註解）**仍計入總N**（`n_all`，Bonferroni門檻分母不變——它確實佔用過
    # 一次試驗名額，把它從分母拿掉等於讓其他候選的門檻變鬆，方向錯誤）；
    # 但不得被算進「有多少筆撐得住/佐證了什麼」這類**評估證據可信度**的
    # 統計——`n_valid`是給這類用途的分母，本檔案目前只在第1節報告這兩個
    # 數字讓使用者自己看差異，不強改下面既有的`survived`/`degraded`邏輯
    # （那本來就已經是逐列核對，不是靠N做粗略篩選）。
    irreproducible_rows = [r for r in rows if r["verdict"] == "IRREPRODUCIBLE"]

    # 2026-09-23實測發現的真實bug（不是假設性的）：自走軌道與互動視窗CC
    # 近乎同時各自重判「方法.三續.E1重判」，自走軌道未查既有帳本就重跑，
    # 產生跟CC的#332/#333/#334完全重複的三筆登記#335/#336/#337（同一批
    # 分析、同一組數字）。自走軌道事後在TRIALS_LEDGER.md notes欄加了
    # 「已排除於任何N/Bonferroni/DSR計算之外」的更正說明，**但這句話只是
    # 散文，`parse()`的N計數完全不會讀notes欄的語意去排除任何列**——
    # 光寫更正說明不會真的把它排除掉，這正是INCIDENTS.md事件002「聲稱
    # 做了但沒做」同一種失敗形狀，這裡在造成實際偏誤之前先抓到並修正。
    # `trial_registry.py`的append-only設計不允許回頭改寫#335~#337本身
    # 的判定欄（那會毀掉「當時發生過重複登記」這個稽核證據），所以用
    # 跟IRREPRODUCIBLE同一種「仍計入總N，但排除出有效N」處理方式，
    # 差別是靠這裡明確列出試驗編號（而不是掃verdict文字），因為
    # DUPLICATE不是一種verdict語意（每筆本身的PASS/FAIL判定仍然真實
    # 有效，問題不在判定對不對，在於這3筆判定的是跟另外3筆完全相同的
    # 分析，不是3個獨立的統計檢定）。
    KNOWN_DUPLICATE_IDS = {335, 336, 337}  # 見TRIALS_LEDGER.md #337後方更正說明
    duplicate_rows = [r for r in rows if r["id"] in KNOWN_DUPLICATE_IDS]

    # 2026-09-23總司令裁示【修正兩個系統性錯誤＋兩件待審閱結案】修.一：
    # exit_rule_lab.py的重入邏輯bug（未持倉時enter_today=True無條件成立，
    # ma_regime分支只有pass，「站上均線才進場」從未實作）讓#338~#344全部
    # 7筆數字失真（E-d交易數1357筆、MDD比買進持有本身還差，是bug的直接
    # 證據）。跟KNOWN_DUPLICATE_IDS同一種處理：append-only設計不允許
    # 回頭改寫這7筆本身的判定欄，改用明確列出編號排除出有效N，仍計入
    # 總N（確實佔用過試驗名額）。見TRIALS_LEDGER.md #344前方INVALID_BUG
    # 說明。修正版7筆已重新登記為新編號，不受此排除影響。
    KNOWN_INVALID_BUG_IDS = {338, 339, 340, 341, 342, 343, 344}
    invalid_bug_rows = [r for r in rows if r["id"] in KNOWN_INVALID_BUG_IDS]
    n_valid = n_all - len(irreproducible_rows) - len(duplicate_rows) - len(invalid_bug_rows)

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
    L.append(f"| **全體（總N，含IRREPRODUCIBLE／已知重複登記／已知因bug失真）** | {n_all} | "
             f"{required_percentile(n_all):.4f} 百分位 |")
    L.append(f"| **有效N（排除IRREPRODUCIBLE{len(irreproducible_rows)}筆＋已知重複登記"
             f"{len(duplicate_rows)}筆＋已知因bug失真{len(invalid_bug_rows)}筆）** | {n_valid} | "
             f"{required_percentile(n_valid):.4f} 百分位 |")
    for t, n in n_track.items():
        L.append(f"| 分軌 {t} | {n} | {required_percentile(n):.4f} 百分位 |")
    L.append("")
    if irreproducible_rows:
        L.append("**IRREPRODUCIBLE列表**（登記過的數值結果，用現有程式碼/資料重跑對不上，"
                  "仍計入總N但不作為任何評估的可信證據）：")
        for r in sorted(irreproducible_rows, key=lambda x: x["id"]):
            L.append(f"- #{r['id']}（{r['date']}，{r['track']}）{r['name'][:60]}")
        L.append("")
    if duplicate_rows:
        L.append("**已知重複登記列表**（2026-09-23實測發現：自走軌道與互動視窗CC近乎"
                  "同時各自重判同一個PENDING_QUEUE條目，自走軌道未先查既有帳本就重跑，"
                  "跟CC的#332/#333/#334登記了完全相同的分析。自走軌道事後在notes欄加了"
                  "更正說明但那只是散文，`parse()`不會讀notes語意排除任何列——這裡改用"
                  "`KNOWN_DUPLICATE_IDS`明確列出試驗編號才是真的把它們排除出有效N，"
                  "散文本身不會自動生效，這是動工中自我糾錯，不是總司令發現才修）：")
        for r in sorted(duplicate_rows, key=lambda x: x["id"]):
            L.append(f"- #{r['id']}（{r['date']}，{r['track']}）{r['name'][:60]}——與"
                     f"#332/#333/#334重複，見TRIALS_LEDGER.md對應位置更正說明")
        L.append("")
    if invalid_bug_rows:
        L.append("**已知因程式bug失真列表**（2026-09-23修.一：`exit_rule_lab.py`重入邏輯"
                  "bug讓這7筆數字全部失真，E-d交易數1357筆、MDD比買進持有本身還差是bug的"
                  "直接證據，仍計入總N但不作為任何評估的可信證據，修正版已重新登記新編號）：")
        for r in sorted(invalid_bug_rows, key=lambda x: x["id"]):
            L.append(f"- #{r['id']}（{r['date']}，{r['track']}）{r['name'][:60]}")
        L.append("")
    if framework_check_rows:
        L.append(f"**FRAMEWORK_CHECK／FRAMEWORK_CHECK_FAILED列表（{len(framework_check_rows)}筆，"
                  "完全不計入N，僅供追蹤）**：隨機選股佔位訊號驗證回測框架本身正確性，不是"
                  "alpha檢定（FAILED代表連框架驗證本身都因為別的bug而不成立，見#358）：")
        for r in sorted(framework_check_rows, key=lambda x: x["id"]):
            L.append(f"- #{r['id']}（{r['date']}，{r['track']}，{r['verdict']}）{r['name'][:60]}")
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
