"""由 research/TRIALS_LEDGER.md 產生 data/trials_index.json（App 研究透明度頁讀取）。
只做唯讀解析：編號、日期、軌道、名稱、判定。不改帳本本身。

2026-10-12 先.八十-3 修正：
- 列的認定與 research/selection_bias_ledger.py parse() 完全相同（第一欄純數字、第二欄恰為 YYYY-MM-DD）——
  舊版只看第一欄是數字，把帳本裡 FDR 重新評分對照表（第一欄是「排名」1～33、第二欄是 #編號）也收進來，
  編號重複、總列數 465 ≠ 帳本總 N。現在 count 必須等於 selection_bias_ledger 的總 N（不等就不寫檔、非零退出）。
- 欄位以「未跳脫的 |」切分，`\\|` 還原成 |——舊版直接 split('|')，備註或名稱裡的 `\\|` 會把後面欄位整排截斷位移。
- 判定欄從右往左（不含最後一欄備註）找含判定關鍵字的欄（帳本各區塊欄數 7～10 不一），找不到才退回第 7 欄。
- 帳本裡真的有兩組不同試驗共用編號（#94、#149），兩列都保留並標 dup_id=true，不擅自改帳本編號。
"""
import json, re, sys, datetime, pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
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
        verdict = next((c for c in reversed(cells[4:-1]) if any(k in c for k in VERDICT_KEYS)), cells[6] if len(cells) > 6 else "")
        rows.append({
            "id": int(cells[0]),
            "date": cells[1],
            "track": clean(cells[2]),
            "name": clean(cells[3])[:80],
            "verdict": clean(verdict)[:40],
        })
    return rows


def ledger_total():
    sys.path.insert(0, str(ROOT / "research"))
    import selection_bias_ledger as S
    return len(S.parse())


def main():
    rows = parse_rows()
    n_ref = ledger_total()
    if len(rows) != n_ref:
        print(f"[ERROR] trials_index 列數 {len(rows)} ≠ selection_bias_ledger 總 N {n_ref}，不寫檔")
        return 1
    dup = {k for k, v in Counter(r["id"] for r in rows).items() if v > 1}
    for r in rows:
        if r["id"] in dup:
            r["dup_id"] = True
    rows.sort(key=lambda r: (-r["id"], r["date"]))
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source": "research/TRIALS_LEDGER.md",
        "disclaimer": "研究紀錄，非投資建議",
        "count": len(rows),
        "count_rule": "與 research/selection_bias_ledger.py 總 N 同一套列認定（第一欄編號、第二欄日期）",
        "dup_ids": sorted(dup),
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"trials_index: {len(rows)} rows（＝總 N {n_ref}；共用編號 {sorted(dup)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
