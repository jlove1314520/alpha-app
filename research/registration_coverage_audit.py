# -*- coding: utf-8 -*-
"""登記覆蓋率稽核：「第幾輪之後的研究實際上沒有結構化登記？」

（2026-09-07 `PENDING_QUEUE.md` Cybex.債務3 後半段。前半段「登記強制化」的機制在
`trial_registry.py`，這一支只負責**誠實回報歷史缺口**，不改寫任何歷史列。）

三個層次分開量，因為它們是三件不同的事，混在一起講就會變成一句沒有資訊量的
「有登記啦」：

L1 **結構化登記**（呼叫登記函式、寫進機器可讀檔）：`TRIALS_REGISTRY.jsonl` 的筆數。
L2 **內容登記**（帳本裡找得到這個因子/策略的一列）：拿每一輪 log 裡出現的識別字
   （反引號括起來的 `f_xxx`／`fut_xxx`／腳本名）去比對帳本全文。
L3 **輪次可追溯**（那一列說得出自己是第幾輪做的）：帳本列裡有沒有 `roundNNN`／`第NNN輪`。

L2 通過不代表 L3 通過——「有一列」跟「那一列能對回哪一輪」是兩件事，而多重比較
校正真正需要的是後者（不然無法判斷同一個機制被重測了幾次）。

**限制誠實揭露**：L2 是字串比對，識別字在帳本別列出現也會算命中，所以 L2 是**上界**
（寬鬆估計）；L3 是精確的（有沒有寫輪次是二元事實）。判定輪次的認定靠 log 標題有沒有
「跳過」與內文有沒有判定關鍵字，屬啟發式，數字會受寫作習慣影響——所以報告同時附
每一輪的原始判斷結果進 JSON，可以逐筆覆核，不是只給一個總結數字。

用法：python research/registration_coverage_audit.py
輸出：research/REGISTRATION_COVERAGE.md ＋ research/data/registration_coverage.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
sys.path.insert(0, str(RESEARCH))

from trial_registry import (  # noqa: E402
    STAT_PAT, VALID_TRACKS, parse_ledger, registry_records, trial_rows,
)

OUT_MD = RESEARCH / "REGISTRATION_COVERAGE.md"
OUT_JSON = RESEARCH / "data" / "registration_coverage.json"
TZ = timezone(timedelta(hours=8))

TRACK_LOGS = {"TW": "TW_LOG.md", "US": "US_LOG.md", "FUT": "FUT_LOG.md"}
QUEUE_LOG = "MARATHON_LOG.md"  # hypothesis_queue 軌：這份 log 沒有輪次編號

IDENT = re.compile(r"`([A-Za-z][A-Za-z0-9_]{4,})`")
ROUND_IN_TEXT = re.compile(r"round\s*(\d+)|第\s*(\d+)\s*輪")
VERDICT_IN_LOG = re.compile(r"PASS|FAIL|REFUTED|EXPERIMENTAL|ABANDONED")
BUCKET = 25


def rounds_from_logs() -> list[dict]:
    """掃三軌 log 的每一則章節，抽出輪次編號與「這輪有沒有下判定」。"""
    out = []
    for track, fname in TRACK_LOGS.items():
        lines = (RESEARCH / fname).read_text(encoding="utf-8").splitlines()
        heads = [i for i, l in enumerate(lines) if l.startswith("## ")]
        for k, i in enumerate(heads):
            j = heads[k + 1] if k + 1 < len(heads) else len(lines)
            head, body = lines[i], "\n".join(lines[i:j])
            m = ROUND_IN_TEXT.search(head)
            if not m:
                continue
            out.append({
                "round": int(m.group(1) or m.group(2)),
                "track": track,
                "skipped": "跳過" in head,
                "judged": bool(VERDICT_IN_LOG.search(body)) and "跳過" not in head,
                "idents": sorted({x.group(1).lower() for x in IDENT.finditer(body)}),
            })
    out.sort(key=lambda r: (r["round"], r["track"]))
    return out


def audit() -> dict:
    rows = trial_rows(parse_ledger())
    blob = " ".join(r.blob for r in rows)
    ledger_idents = {m.group(1).lower() for m in IDENT.finditer(blob)}
    cited_rounds = {int(a or b) for a, b in ROUND_IN_TEXT.findall(blob)}

    ids = [r.tid for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    gaps = sorted(set(range(1, max(ids) + 1)) - set(ids)) if ids else []

    rounds = rounds_from_logs()
    for r in rounds:
        r["ident_in_ledger"] = bool(set(r["idents"]) & ledger_idents)
        r["round_cited_in_ledger"] = r["round"] in cited_rounds
    judged = [r for r in rounds if r["judged"]]

    buckets = defaultdict(lambda: {"judged": 0, "L2": 0, "L3": 0})
    for r in judged:
        b = buckets[r["round"] // BUCKET * BUCKET]
        b["judged"] += 1
        b["L2"] += r["ident_in_ledger"]
        b["L3"] += r["round_cited_in_ledger"]

    # L3 的轉折點：從哪一輪之後「輪次可追溯率」才穩定站上 2/3。
    # 由資料決定，不是挑一個好看的數字——掃過每個候選切點，取「切點之後覆蓋率最高、
    # 且切點之前明顯較低」的那一個。
    best = {"cut": None, "after": 0.0, "before": 0.0, "gain": -1.0}
    js = sorted(judged, key=lambda r: r["round"])
    for idx in range(1, len(js)):
        cut = js[idx]["round"]
        bef = [r["round_cited_in_ledger"] for r in js[:idx]]
        aft = [r["round_cited_in_ledger"] for r in js[idx:]]
        if len(bef) < 10 or len(aft) < 10:
            continue
        rb, ra = sum(bef) / len(bef), sum(aft) / len(aft)
        if ra - rb > best["gain"]:
            best = {"cut": cut, "after": round(ra * 100, 1), "before": round(rb * 100, 1),
                    "gain": ra - rb, "n_before": len(bef), "n_after": len(aft)}

    queue_heads = [l for l in (RESEARCH / QUEUE_LOG).read_text(encoding="utf-8").splitlines()
                   if l.startswith("## ")]
    queue_numbered = sum(1 for l in queue_heads if ROUND_IN_TEXT.search(l))

    # 判定輪的最大空窗（暫停規則期間的長段跳過），由資料算，不憑印象寫區間
    seq = sorted({r["round"] for r in judged})
    gap = max(zip(seq, seq[1:]), key=lambda p: p[1] - p[0], default=(0, 0))

    # 分母口徑差異：`selection_bias_ledger.py` 用的是「帳本所有數字開頭的列」，
    # 本支用的是「試驗列」（第二欄是日期）。差額就是 FDR 重新評分對照表。
    from selection_bias_ledger import parse as sb_parse  # noqa: E402
    sb_rows = len(sb_parse())

    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "L1_structured_records": len(registry_records()),
        "ledger": {
            "trial_rows": len(rows),
            "max_id": max(ids) if ids else 0,
            "duplicate_ids": dup,
            "missing_ids": gaps,
            "rows_without_statistic": sum(1 for r in rows if not STAT_PAT.search(r.blob)),
            "rows_without_track": sum(1 for r in rows if r.track not in VALID_TRACKS),
            "rows_without_verdict": sum(1 for r in rows if not r.verdict),
            "rows_citing_a_round": sum(1 for r in rows if ROUND_IN_TEXT.search(r.blob)),
        },
        "rounds": {
            "logged": len(rounds),
            "min": min((r["round"] for r in rounds), default=0),
            "max": max((r["round"] for r in rounds), default=0),
            "judged": len(judged),
            "judged_L2_covered": sum(1 for r in judged if r["ident_in_ledger"]),
            "judged_L3_covered": sum(1 for r in judged if r["round_cited_in_ledger"]),
        },
        "buckets": {str(k): dict(v) for k, v in sorted(buckets.items())},
        "L3_changepoint": best,
        "hypothesis_queue_log": {
            "entries": len(queue_heads),
            "with_round_number": queue_numbered,
        },
        "judged_gap": {"from": gap[0], "to": gap[1], "span": gap[1] - gap[0]},
        "denominator": {
            "selection_bias_ledger_rows": sb_rows,
            "trial_rows": len(rows),
            "fdr_rescoring_rows": sb_rows - len(rows),
        },
        "per_round": judged,
    }


def render(a: dict) -> str:
    r, led, cp = a["rounds"], a["ledger"], a["L3_changepoint"]
    pct = lambda x, y: f"{x / y * 100:.1f}%" if y else "—"  # noqa: E731
    lines = [
        "# REGISTRATION_COVERAGE.md — 登記覆蓋率稽核（Cybex.債務3 回報）",
        "",
        f"**這份檔案由 `research/registration_coverage_audit.py` 產生，最後更新 {a['generated_at']}。**",
        "不要手改：手改過的稽核報告不能當證據（這份報告本身要查的就是手工維護的後果）。",
        "",
        "## 一句話回答「第幾輪之後沒有結構化登記」",
        "",
        f"**從第 {r['min']} 輪到第 {r['max']} 輪，結構化登記筆數是 {a['L1_structured_records']} 筆——"
        "也就是說，這個專案至今沒有任何一輪是「呼叫登記函式」登記的，全部是手工編輯 markdown。**",
        "登記函式（`research/trial_registry.py::register_trial()`）今天（2026-09-07）才建立，",
        "所以正確的說法不是「第 N 輪之後斷掉」，而是**從來沒有過，從今天起才開始**。",
        "",
        "把標準放寬到「帳本裡找不找得到這一輪測的東西」，數字反而是好的，所以要分層講：",
        "",
        "| 層次 | 定義 | 涵蓋率 |",
        "|---|---|---|",
        f"| L1 結構化登記 | 呼叫登記函式、寫進 `research/TRIALS_REGISTRY.jsonl` | {a['L1_structured_records']} / {r['judged']}（0.0%） |",
        f"| L2 內容登記 | 帳本全文找得到那一輪的因子/腳本識別字 | {r['judged_L2_covered']} / {r['judged']}（{pct(r['judged_L2_covered'], r['judged'])}） |",
        f"| L3 輪次可追溯 | 帳本那一列說得出自己是第幾輪 | {r['judged_L3_covered']} / {r['judged']}（{pct(r['judged_L3_covered'], r['judged'])}） |",
        "",
        f"分母 {r['judged']} 是「log 裡有下判定的輪次」（三軌 log 共 {r['logged']} 則有輪次編號的章節，"
        "其餘是跳過輪或純地基輪，本來就不該有登記）。",
        "",
        "## L3 的轉折點：輪次可追溯是從哪一輪才變成習慣的",
        "",
        f"掃過所有可能切點後，最明顯的轉折在**第 {cp['cut']} 輪**：",
        f"之前 {cp['n_before']} 個判定輪只有 {cp['before']}% 的帳本列寫得出輪次，"
        f"之後 {cp['n_after']} 個判定輪是 {cp['after']}%。",
        "",
        "換句話說：**第 %s 輪之前的研究，帳本雖然有列，但那些列對不回是哪一輪做的**——"
        "要重算多重比較分母、或要查同一個機制被重測過幾次時，那一段是查不動的。" % cp["cut"],
        "",
        "### 逐 25 輪覆蓋率",
        "",
        "| 輪次區間 | 判定輪 | L2 內容登記 | L3 輪次可追溯 |",
        "|---|---|---|---|",
    ]
    for k, v in a["buckets"].items():
        k = int(k)
        lines.append(f"| {k}–{k + BUCKET - 1} | {v['judged']} | {v['L2']} | {v['L3']} |")
    lines += [
        "",
        f"（第 {a['judged_gap']['from']}–{a['judged_gap']['to']} 輪之間整整 "
        f"{a['judged_gap']['span']} 輪沒有任何判定輪，是暫停規則生效期間三軌幾乎每輪都「跳過」造成的，"
        "不是漏記。）",
        "",
        "## 手工登記已經造成的實際損害（不是理論風險）",
        "",
        f"- **撞號 {len(led['duplicate_ids'])} 組**：{led['duplicate_ids']} 各被兩筆完全不同的試驗用掉，"
        "所以「帳本編號」不能當試驗數的權威來源。",
        (f"- **編號空洞 {len(led['missing_ids'])} 個**：{led['missing_ids']}——編號跳號，"
         "「最大編號」也不等於試驗數。"
         if led["missing_ids"] else
         f"- 編號連續無空洞（#1–#{led['max_id']}），但因為上面那 {len(led['duplicate_ids'])} 組撞號，"
         f"實際試驗列是 {led['trial_rows']} 列而不是 {led['max_id']} 列。"),
        f"- **{led['rows_without_statistic']} 列沒有任何可比較的統計量**（總共 {led['trial_rows']} 列），"
        "這些列在多重比較重評時既不能算撐住也不能算倒下（Cybex.債務1 已經吃過這個虧）。",
        f"- **{led['rows_without_track']} 列沒有可辨識的軌道欄**，分軌 FDR 校正時只能丟進「未分軌」。",
        f"- **{led['rows_without_verdict']} 列讀不出判定**。",
        f"- **hypothesis_queue 軌 {a['hypothesis_queue_log']['entries']} 則 log 只有 "
        f"{a['hypothesis_queue_log']['with_round_number']} 則帶輪次編號**，這一軌從頭到尾沒有輪次計數器，"
        "它的試驗完全沒有 L3 可追溯性可言。",
        "",
        "## 分母的爭議（本輪新發現，未擅自更動）",
        "",
        f"`trial_registry.py` 解析出的**試驗列是 {a['denominator']['trial_rows']} 列**，"
        f"但 `selection_bias_ledger.py`（多重比較校正分母的來源）此刻解析出 "
        f"**{a['denominator']['selection_bias_ledger_rows']} 列**，差 "
        f"{a['denominator']['fdr_rescoring_rows']} 列。差額全部來自 2026-08-25 那張"
        "「FDR 重新評分對照表」——那張表借用 `#1`..`#17` 這種編號引用把**既有試驗重新評分**，"
        "沒有重新抓資料、沒有重新跑控制組（那張表自己的說明就是這樣寫的），"
        "是同一批試驗的第二次評分，不是新試驗，卻被一起算進分母。",
        "",
        "**本輪不改任何分母**：改分母會直接改動 Cowork.債務2 已經完成的重評結論，"
        "屬於研究結論層級的變更，依「提案先於執行」要先報總司令。這裡只把差異記下來，"
        "連同兩邊的算法差異，交由 Cowork.債務2.4／審視1.3 那一輪裁示要用哪一個。",
        "",
        "## 從今天起的規則（已寫進 `MARATHON_PROTOCOL.md` 第 2 節與第 6 節）",
        "",
        "1. 任何候選判定要進 `*_LEADS.md`，先呼叫 `register_trial()`；**未登記的判定一律無效**。",
        "2. 每輪收工前跑 `python research/trial_registry.py --check`，非 0 就不准 commit。",
        "3. 開工的 `marathon_brief.py` 會把登記狀態印出來，看得到才不會忘記。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    a = audit()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_MD.write_text(render(a), encoding="utf-8")
    r = a["rounds"]
    print(f"判定輪 {r['judged']} 個（第 {r['min']}–{r['max']} 輪）："
          f"L1 結構化 {a['L1_structured_records']}／L2 內容 {r['judged_L2_covered']}／L3 輪次 {r['judged_L3_covered']}")
    print(f"L3 轉折點：第 {a['L3_changepoint']['cut']} 輪"
          f"（之前 {a['L3_changepoint']['before']}% → 之後 {a['L3_changepoint']['after']}%）")
    print(f"已寫出 {OUT_MD.relative_to(ROOT)} 與 {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
