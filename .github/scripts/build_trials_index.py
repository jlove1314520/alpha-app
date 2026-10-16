"""由 research/TRIALS_LEDGER.md 產生 data/trials_index.json（App 研究透明度頁讀取）。
只做唯讀解析：編號、日期、軌道、名稱、判定。不改帳本本身。

2026-10-12 先.八十-3 修正：
- 列的認定與 research/selection_bias_ledger.py parse() 完全相同（第一欄純數字、第二欄恰為 YYYY-MM-DD）——
  舊版只看第一欄是數字，把帳本裡 FDR 重新評分對照表（第一欄是「排名」1～33、第二欄是 #編號）也收進來，
  編號重複、總列數 465 ≠ 帳本總 N。現在 count 必須等於 selection_bias_ledger 的總 N（不等就不寫檔、非零退出）。
- 欄位以「未跳脫的 |」切分，`\\|` 還原成 |——舊版直接 split('|')，備註或名稱裡的 `\\|` 會把後面欄位整排截斷位移。
- 判定欄從右往左（不含最後一欄備註）找含判定關鍵字的欄（帳本各區塊欄數 7～10 不一），找不到才退回第 7 欄。
- 帳本裡真的有兩組不同試驗共用編號（#94、#149），兩列都保留並標 dup_id=true，不擅自改帳本編號。

2026-10-16 先.一〇三-15 修正：
- 判定欄改用 research/ledger_verdict.py（與 selection_bias_ledger 同一套：以判定字「開頭」的欄才是判定欄）。
  舊規則「從右往左找含關鍵字的欄」把 96／448 列判錯（例 #445 事前登記「未結案」被讀成 PASS、#426 PASS 被讀成 FAIL）。
- 事前登記＋結果算 1 筆：被結果列以「事前登記 #編號」引用的事前登記列，列出但 counted=false、merged_into=結果列編號。
- 共用編號（#94、#149）：帳本編號不改（其他文件有引用），每列加唯一的 uid（例 94-1、94-2），App 用 uid 當鍵、顯示 #94-1。
"""
import json, re, sys, datetime, pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
sys.path.insert(0, str(ROOT / "research"))
import ledger_verdict as _LV  # noqa: E402  先.一〇三-15 判定欄共用解析
OUT = ROOT / "data" / "trials_index.json"
SPLIT = re.compile(r"(?<!\\)\|")
VERDICT_KEYS = ("VIOLATES_SURVIVAL", "IRREPRODUCIBLE", "INVALID", "CHEAP_PASS", "未結案", "不確定", "FAIL", "PASS")


def clean(s):
    return re.sub(r"[`*]", "", s.replace("\\|", "|")).strip()


def parse_rows():
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in SPLIT.split(line.strip().strip("|"))]
        if len(cells) < 6 or not re.match(r"^\d+$", cells[0]) or not re.match(r"^\d{4}-\d{2}-\d{2}$", cells[1]):
            continue
        sv = _LV.strict_verdict(cells)  # 先.一〇三-15：判定欄＝以判定字開頭的欄；找不到才退回舊規則
        verdict = sv if sv is not None else next((c for c in reversed(cells[4:-1]) if any(k in c for k in VERDICT_KEYS)), cells[6] if len(cells) > 6 else "")
        rows.append({
            "id": int(cells[0]),
            "date": cells[1],
            "track": clean(cells[2]),
            "name": clean(cells[3])[:80],
            "verdict": clean(verdict)[:40],
        })
    return rows


NOT_COUNTED = ("FRAMEWORK_CHECK", "FRAMEWORK_CHECK_FAILED")  # 與 selection_bias_ledger.main() 同：框架驗證列不計入總 N


def ledger_total():
    """回傳 (帳本試驗列數, 總 N, {事前登記編號: 結果列編號})。總 N 與 selection_bias_ledger.main() 同一條規則
    （排除框架驗證列；先.一〇三-15 起事前登記＋結果算 1 筆），也就是 TRIALS_LEDGER.md 開頭「目前累積總數」那個數字。"""
    import selection_bias_ledger as S
    rows = S.parse()
    counted = [r for r in rows if r["verdict"] not in NOT_COUNTED]
    merged = S.merged_prereg_pairs(counted)
    return len(rows), len(counted) - len(merged), merged


def main():
    rows = parse_rows()
    n_rows, n_ref, merged = ledger_total()
    if len(rows) != n_rows:
        print(f"[ERROR] trials_index 列數 {len(rows)} ≠ 帳本試驗列數 {n_rows}，不寫檔")
        return 1
    for r in rows:
        if any(k in r["verdict"] for k in NOT_COUNTED):
            r["counted"] = False
        if r["id"] in merged:  # 先.一〇三-15：事前登記與結果算 1 筆
            r["counted"] = False
            r["merged_into"] = merged[r["id"]]
    dup = {k for k, v in Counter(r["id"] for r in rows).items() if v > 1}
    seen = Counter()
    for r in rows:  # 帳本順序（舊→新）給共用編號編 -1、-2
        if r["id"] in dup:
            r["dup_id"] = True
            seen[r["id"]] += 1
            r["uid"] = f"{r['id']}-{seen[r['id']]}"
        else:
            r["uid"] = str(r["id"])
    n_listed_counted = sum(1 for r in rows if r.get("counted", True))
    if n_listed_counted != n_ref:
        print(f"[ERROR] 計入列數 {n_listed_counted} ≠ 總 N {n_ref}，不寫檔")
        return 1
    rows.sort(key=lambda r: (-r["id"], r["date"]))
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source": "research/TRIALS_LEDGER.md",
        "disclaimer": "研究紀錄，非投資建議",
        "count": n_ref,
        "rows_listed": len(rows),
        "count_rule": "count＝總 N（與 TRIALS_LEDGER.md 開頭「目前累積總數」、SELECTION_BIAS_LEDGER.md 同一個數字；框架驗證列列出但不計入；事前登記被結果列引用時兩列算 1 筆，事前登記列 counted=false、merged_into=結果列）",
        "dup_ids": sorted(dup),
        "merged_prereg": {str(k): v for k, v in sorted(merged.items())},
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n_fw = sum(1 for r in rows if any(k in r["verdict"] for k in NOT_COUNTED))
    print(f"trials_index: 列出 {len(rows)} 列、總 N {n_ref}（框架驗證列 {n_fw} 列、事前登記併入結果列 {len(merged)} 列不計入；共用編號 {sorted(dup)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
