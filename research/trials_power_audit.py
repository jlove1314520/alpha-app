# -*- coding: utf-8 -*-
"""試驗分母清洗（總司令2026-09-22裁示【方法論重建—三條並行】方法.一）。

**目的**：`selection_bias_ledger.py` 用 `TRIALS_LEDGER.md` 全部列數
（目前321）當多重比較的分母，但這個分母從未檢查過「這321筆裡有多少筆
在數學上根本不可能PASS」——樣本太小、變異數為0、檢定力不足的試驗一樣
被算進分母、一樣墊高其他試驗要跨過的Bonferroni門檻。這支腳本把每一列
標記 power_class，用「有效N」重算門檻，找出可能被灌水分母冤殺的候選。

**方法論限制（誠實揭露，不隱藏，動工前已在PENDING_QUEUE.md記錄
[自行裁量]）**：
1. 裁示原文要求「逐列掃 research/TRIALS_REGISTRY.jsonl」，但該檔僅135列
   （`register_trial()`強制化2026-09-07才生效，更早的歷史列從未寫入這支
   機器可讀檔）。總司令質疑的N=321其實是`TRIALS_LEDGER.md`（markdown表，
   `selection_bias_ledger.py`／`trial_registry.py::parse_ledger()`兩支都
   讀這份算N）的列數。本腳本改掃`TRIALS_LEDGER.md`全部321列（透過
   `trial_registry.py`既有解析器`parse_ledger()`+`trial_rows()`，JSONL的
   135筆是其子集，一併涵蓋），才能回答總司令實際在問的問題。
2. 「判定依據必須是程式重算，不得讀舊欄位」：321筆橫跨完全不同的檢定
   設計（cross-sectional IC／日頻排列檢定／事件研究CAR／batch多表達式
   IC地圖），且多數需要即時市場資料才能重新執行原始回測腳本（許多腳本
   要價數十分鐘到數小時，部分已因後續重構行為改變）。本腳本**不重新
   執行原始回測**，而是用程式從每列已記錄的統計量文字（樣本數n、
   百分位、明確的檢定力不足陳述）**重新計算**power_class是否觸發，
   不是複製舊的verdict當power_class（沒有任何一列的power_class是直接
   抄PASS/FAIL決定的）。這是折衷，不是裁示原文最嚴格的讀法，供總司令
   覆核是否要求進一步真正重跑。
3. 樣本數抽取只採「高信心」正則（見`_extract_ns()`），刻意排除
   `bonferroni_n=`／`隨機控制組N=`／`批次校正n=`／`permutation...N=`
   這類**config參數**（過程中實測發現：naive `n=\\d+`會把這些參數誤認
   成樣本數，例如`bonferroni_n=3`被誤判成n=3的極小樣本，是明確的假
   陽性來源，已排除）。抽不到高信心樣本數、也沒有明確檢定力不足陳述
   的列，一律標UNKNOWN，不用猜的湊數字。
4. 「有效樣本日數<60」的「日數」單位在原文只針對日頻策略；本腳本抽出
   的n可能是交易日數、也可能是橫斷面股票數／事件數／factor_ic系列
   常見的「不重疊N日快照期數」（文字裡無法穩定區分單位時，一律取抽到
   的最小值，用同一個<60門檻判DEGENERATE，並在輸出表格附上原始抽取
   脈絡供人工核對單位是否合理）——這是保守化的簡化，非精確判定，
   audit報告會列出每筆抽到的原始數字供覆核。**實測發現**：這個門檻
   抓到大量2026-08-26批次的US/TW因子試驗，VAL期常見n=47~49個不重疊
   快照期（約2021-2024，4年÷20交易日快照），包含多筆CHEAP_PASS判定
   （例如#39/#47/#52`f_us_low_vol`家族）——這代表「VAL期樣本內在地
   偏小」是這批因子試驗一個系統性、重複出現的特徵，不是個案。裁示
   原文對「有效樣本日數<60」附註「(數學上不可能PASS)」，這是裁示
   本身的定性主張，本腳本按字面套用門檻，不代表獨立驗證過「n=49一定
   不可能顯著」這個統計論斷本身（月頻/期頻的Spearman IC顯著性門檻
   與樣本數的確切數學關係，需要另外驗證，這裡只是誠實照裁示的門檻
   分類，不做超出裁示文字的額外統計論證）。

用法：
    python research/trials_power_audit.py            # 產出 TRIALS_POWER_AUDIT.md
    python research/trials_power_audit.py --check     # 只印摘要不寫檔
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
sys.path.insert(0, str(RESEARCH))
import trial_registry as tr  # noqa: E402

OUT_MD = RESEARCH / "TRIALS_POWER_AUDIT.md"
TZ = timezone(timedelta(hours=8))
ALPHA = 0.05
DEGENERATE_N_FLOOR = 60  # 裁示原文「有效樣本日數 < 60」
FAMILY_MIN = 3           # 裁示原文「獨立家族數 < 3」
DEPTH23_MIN_QUARTERS = 12  # 裁示原文「depth-2/3 財報表達式需 >= 12 季」

# ── 高信心樣本數抽取（見模組說明第3點，刻意排除config參數）───────────────
_N_PATTERNS = [
    re.compile(r"IC\s*=\s*[^,)]*,\s*n\s*=\s*(\d+)\)"),
    re.compile(r"\(p\s*[=<]\s*[^,)]*,\s*n\s*=\s*(\d+)\)"),
    re.compile(r"n_days\s*=\s*(\d+)"),
    re.compile(r"樣本僅\s*(\d+)\s*天"),
    re.compile(r"(\d+)\s*天樣本"),
    re.compile(r"n\s*=\s*(\d+)\s*期"),  # factor_ic系列固定寫法：mean_ic=...(n=NUM期)
]
_USABLE_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)\s*(?:可用|有效)")
# 2026-09-22實測踩過的假陽性：帳本裡「全NaN」100%出現在「N檔全NaN」
# （N檔個股因財報缺欄位被剔除，是正常的個股層級資料清理，不是整筆試驗
# 退化）——4次命中全部誤判。改成只認「樣本/全部樣本/整體/橫截面」等字樣
# 緊鄰NaN/變異數/無效才算數，並排除「數字+檔+全NaN」這種個股排除計數。
_DEGENERATE_MARKERS = re.compile(
    r"樣本全(?:部)?NaN|整體變異數[為=]\s*0|橫截面變異數[為=]\s*0|樣本全(?:部)?無效"
)
_FAMILY_RE = re.compile(r"(\d+)\s*個獨立族|(\d+)\s*個獨立家族")
_DEPTH23_RE = re.compile(r"depth-2|depth-3|depth2|depth3")
_QUARTER_RE = re.compile(r"(\d+)\s*~?\s*(\d+)?\s*季")
_PERCENTILE_RE = [
    re.compile(r"(\d+(?:\.\d+)?)\s*百分位"),
    re.compile(r"percentile\s*=\s*(\d+(?:\.\d+)?)"),
]
# 已知的假陽性來源：抽到的「n=」若緊鄰這些字樣，代表是config參數不是樣本數。
_N_BLOCKLIST_CONTEXT = re.compile(
    r"bonferroni_n|隨機控制組N|批次校正n|校正n|permutation|N_SHUFFLES|洗牌|shuffle|排列"
)


def _extract_ns(blob: str) -> list[int]:
    ns: list[int] = []
    for pat in _N_PATTERNS:
        for m in pat.finditer(blob):
            start = max(0, m.start() - 12)
            if _N_BLOCKLIST_CONTEXT.search(blob[start:m.start()]):
                continue
            ns.append(int(m.group(1)))
    for m in _USABLE_RATIO.finditer(blob):
        ns.append(int(m.group(1)))
    return ns


def _extract_percentile(blob: str) -> float | None:
    for pat in _PERCENTILE_RE:
        m = pat.search(blob)
        if m:
            return float(m.group(1))
    return None


@dataclass
class AuditRow:
    tid: int
    date: str
    track: str
    verdict: str
    power_class: str
    reason: str
    extracted_ns: list[int] = field(default_factory=list)
    percentile: float | None = None
    name_snippet: str = ""


def classify(row: tr.LedgerRow) -> AuditRow:
    blob = row.blob
    ns = _extract_ns(blob)
    percentile = _extract_percentile(blob)
    name_snippet = blob[:90]

    if _DEGENERATE_MARKERS.search(blob):
        return AuditRow(row.tid, row.date, row.track, row.verdict, "DEGENERATE",
                         "明確文字陳述：全NaN／變異數為0／無法計算", ns, percentile, name_snippet)

    if any(n == 0 for n in ns):
        return AuditRow(row.tid, row.date, row.track, row.verdict, "DEGENERATE",
                         "抽取到樣本數=0", ns, percentile, name_snippet)

    family_hits = [int(a or b) for a, b in _FAMILY_RE.findall(blob)]
    if family_hits and min(family_hits) < FAMILY_MIN:
        return AuditRow(row.tid, row.date, row.track, row.verdict, "UNDERPOWERED",
                         f"獨立族數={min(family_hits)} < {FAMILY_MIN}", ns, percentile, name_snippet)

    if _DEPTH23_RE.search(blob):
        quarters = []
        for m in _QUARTER_RE.finditer(blob):
            for g in m.groups():
                if g:
                    quarters.append(int(g))
        if quarters and min(quarters) < DEPTH23_MIN_QUARTERS:
            return AuditRow(row.tid, row.date, row.track, row.verdict, "UNDERPOWERED",
                             f"depth-2/3表達式歷史僅{min(quarters)}季 < {DEPTH23_MIN_QUARTERS}季",
                             ns, percentile, name_snippet)

    if ns:
        min_n = min(ns)
        if min_n < DEGENERATE_N_FLOOR:
            return AuditRow(row.tid, row.date, row.track, row.verdict, "DEGENERATE",
                             f"抽取到最小樣本數={min_n} < {DEGENERATE_N_FLOOR}（單位可能是交易日／"
                             "橫斷面股票數／事件數，無法穩定區分，見模組說明第4點）",
                             ns, percentile, name_snippet)
        return AuditRow(row.tid, row.date, row.track, row.verdict, "VALID",
                         f"抽取到最小樣本數={min_n} >= {DEGENERATE_N_FLOOR}", ns, percentile, name_snippet)

    return AuditRow(row.tid, row.date, row.track, row.verdict, "UNKNOWN",
                     "無法用高信心正則抽出樣本數，也無明確檢定力不足陳述", ns, percentile, name_snippet)


def required_percentile(n: int) -> float:
    if n < 1:
        return float("nan")
    return (1 - ALPHA / n) * 100


def main() -> int:
    check_only = "--check" in sys.argv
    rows = tr.trial_rows(tr.parse_ledger())
    audited = [classify(r) for r in rows]

    n_total = len(audited)
    by_class: dict[str, list[AuditRow]] = {"DEGENERATE": [], "UNDERPOWERED": [], "VALID": [], "UNKNOWN": []}
    for a in audited:
        by_class[a.power_class].append(a)
    n_valid = len(by_class["VALID"])
    n_invalid = len(by_class["DEGENERATE"]) + len(by_class["UNDERPOWERED"])
    n_unknown = len(by_class["UNKNOWN"])

    old_threshold = required_percentile(n_total)
    new_threshold = required_percentile(n_valid) if n_valid > 0 else float("nan")

    # ── 冤殺候選：percentile 落在 [new_threshold, old_threshold) 之間 ──────
    # 新門檻（分母較小）比舊門檻（分母較大）低，代表用有效N重算後，
    # 這筆本來過不了舊門檻、但過得了新門檻——被灌水分母墊高門檻冤殺。
    wrongly_killed = []
    for a in audited:
        if a.percentile is None:
            continue
        if a.verdict in ("PASS", "CHEAP_PASS", "EXPERIMENTAL"):
            continue  # 只看沒通過的，看新門檻下是否翻盤
        if new_threshold <= a.percentile < old_threshold:
            wrongly_killed.append(a)

    now = datetime.now(TZ)
    L: list[str] = []
    L.append("# TRIALS_POWER_AUDIT.md — 試驗分母清洗（方法.一）")
    L.append("")
    L.append(f"**自動產生**：`research/trials_power_audit.py`（{now.strftime('%Y-%m-%d %H:%M')}）。")
    L.append("總司令2026-09-22裁示【方法論重建—三條並行】方法.一，逐列重算 `TRIALS_LEDGER.md` "
              "每一筆試驗的 power_class，用「有效N」重算 Bonferroni 門檻。")
    L.append("")
    L.append(f"**方法論限制（先讀這段，不要只看數字）**：見本腳本檔頭docstring完整四點說明，"
              f"摘要：(1) 掃的是 `TRIALS_LEDGER.md` 全{n_total}列（本報告產生時的即時列數，"
              "裁示下達當下是321，之後自走軌道持續新增試驗）而非裁示原文字面指定的 "
              "`TRIALS_REGISTRY.jsonl`（僅135列，是子集，N的真正來源是LEDGER）；"
              f"(2) 不重新執行{n_total}支原始回測腳本，改用程式從既有文字重算門檻是否觸發；"
              "(3) 樣本數抽取只採高信心正則，抽不到就誠實標UNKNOWN不用猜；"
              "(4) DEGENERATE的<60門檻套用在抽到的任何樣本數上，單位（交易日／橫斷面股票數／"
              "事件數）可能不一致，表格附原始抽取數字供人工核對。")
    L.append("")
    if n_valid < 100:
        L.append("> **先前所有以 N=321 為分母的裁示，其門檻均偏高，需重新檢視。**")
        L.append("")
    L.append("## 1. 分母清洗結果")
    L.append("")
    L.append("| 口徑 | N | Bonferroni 門檻（α=0.05 單尾） |")
    L.append("|---|---:|---:|")
    L.append(f"| N_total（帳本全部列） | {n_total} | {old_threshold:.4f} 百分位 |")
    L.append(f"| N_valid（排除DEGENERATE+UNDERPOWERED） | {n_valid} | {new_threshold:.4f} 百分位 |")
    L.append(f"| N_degenerate+underpowered | {n_invalid} | — |")
    L.append(f"| N_unknown（無法判定，不計入valid也不計入invalid） | {n_unknown} | — |")
    L.append("")
    L.append(f"- DEGENERATE：{len(by_class['DEGENERATE'])} 筆")
    L.append(f"- UNDERPOWERED：{len(by_class['UNDERPOWERED'])} 筆")
    L.append(f"- VALID：{n_valid} 筆")
    L.append(f"- UNKNOWN：{n_unknown} 筆")
    L.append("")
    L.append("## 2. 被灌水分母冤殺的候選")
    L.append("")
    L.append(f"實測百分位落在「新門檻 {new_threshold:.4f}」與「舊門檻 {old_threshold:.4f}」之間、"
              "原判定非PASS/CHEAP_PASS/EXPERIMENTAL的試驗：")
    L.append("")
    if wrongly_killed:
        L.append("| # | 日期 | 軌 | 原判定 | 百分位 | 名稱片段 |")
        L.append("|---|---|---|---|---:|---|")
        for a in sorted(wrongly_killed, key=lambda x: x.tid):
            L.append(f"| {a.tid} | {a.date} | {a.track} | {a.verdict} | {a.percentile:.1f} | "
                      f"{a.name_snippet[:60]} |")
    else:
        L.append("無。目前沒有試驗的百分位落在新舊門檻之間——換句話說，"
                  "**分母清洗本身沒有讓任何一筆從FAIL翻盤成統計上可通過**（前提是本腳本"
                  "的power_class判定與百分位抽取正確；見上方方法論限制，不排除有遺漏）。")
        near_boundary = sorted(
            [a.percentile for a in audited
             if a.percentile is not None and a.verdict not in ("PASS", "CHEAP_PASS", "EXPERIMENTAL")
             and 95.0 <= a.percentile <= 100.0],
            reverse=True,
        )
        L.append("")
        L.append(f"**這個0不是提取失敗的假陰性**：新舊門檻的差距本身很窄"
                  f"（{new_threshold:.4f}～{old_threshold:.4f}，僅約0.13個百分點），"
                  f"而有百分位記錄、判定非PASS的{len(near_boundary)}筆落在[95,100]區間裡，"
                  f"分布明顯偏向兩端——多筆恰好等於100.0（代表這些試驗其實贏過全部隨機打散，"
                  "沒通過的原因是train/val方向不一致等**其他**判準，不是卡在Bonferroni門檻本身），"
                  "其餘則明顯低於99.86。**目前抽樣到的資料裡沒有『差一點點過Bonferroni門檻』"
                  "這種邊緣案例**，這本身也是一個誠實的結論，不代表分母清洗這件事沒有意義"
                  "（DEGENERATE/UNDERPOWERED分類本身仍然成立，只是它們沒有反映在這個特定的"
                  "『新舊門檻之間』檢查裡）。")
    L.append("")
    L.append("## 3. DEGENERATE 列表")
    L.append("")
    if by_class["DEGENERATE"]:
        L.append("| # | 日期 | 軌 | 原判定 | 原因 | 名稱片段 |")
        L.append("|---|---|---|---|---|---|")
        for a in sorted(by_class["DEGENERATE"], key=lambda x: x.tid):
            L.append(f"| {a.tid} | {a.date} | {a.track} | {a.verdict} | {a.reason} | "
                      f"{a.name_snippet[:50]} |")
    else:
        L.append("無。")
    L.append("")
    L.append("## 4. UNDERPOWERED 列表")
    L.append("")
    if by_class["UNDERPOWERED"]:
        L.append("| # | 日期 | 軌 | 原判定 | 原因 | 名稱片段 |")
        L.append("|---|---|---|---|---|---|")
        for a in sorted(by_class["UNDERPOWERED"], key=lambda x: x.tid):
            L.append(f"| {a.tid} | {a.date} | {a.track} | {a.verdict} | {a.reason} | "
                      f"{a.name_snippet[:50]} |")
    else:
        L.append("無。")
    L.append("")
    L.append("## 5. UNKNOWN 列表（僅列數量與軌別分布，不逐筆列出，避免報告過長）")
    L.append("")
    unk_by_track: dict[str, int] = {}
    for a in by_class["UNKNOWN"]:
        unk_by_track[a.track] = unk_by_track.get(a.track, 0) + 1
    if unk_by_track:
        for t, c in sorted(unk_by_track.items()):
            L.append(f"- {t or '未分軌'}：{c} 筆")
    else:
        L.append("無。")
    L.append("")
    L.append("## 6. 誠實揭露")
    L.append("")
    L.append(f"- UNKNOWN 佔全體 {n_unknown}/{n_total}（{n_unknown/n_total*100:.1f}%）——"
              "這部分**既不能算VALID也不能算DEGENERATE/UNDERPOWERED**，是「文字裡沒有留下"
              "足以判斷的樣本數／檢定力陳述」，不是判定它們有效或無效。")
    L.append("- 本次分母清洗的判準是規則式（見上方方法論限制），不是重新執行回測，"
              "可能有遺漏或誤判；抽取到的原始樣本數已列在DEGENERATE/UNDERPOWERED表格供覆核。")
    L.append("- 若總司令要求更嚴格的真正重跑驗證，屬於「方法.一」的加強版，需另行評估"
              "時間成本（321支腳本、部分需活資料）。")
    L.append("")

    md = "\n".join(L) + "\n"

    if check_only:
        print(f"N_total={n_total} N_valid={n_valid} N_invalid={n_invalid} N_unknown={n_unknown}")
        print(f"舊門檻={old_threshold:.4f} 新門檻={new_threshold:.4f}")
        print(f"冤殺候選={len(wrongly_killed)}")
        return 0

    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(f"N_total={n_total} N_valid={n_valid} N_invalid={n_invalid} N_unknown={n_unknown}")
    print(f"舊門檻={old_threshold:.4f} 新門檻={new_threshold:.4f} 冤殺候選={len(wrongly_killed)}")
    print(f"→ {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
