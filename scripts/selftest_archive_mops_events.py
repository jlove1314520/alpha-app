"""自測：重大訊息長期歸檔 `scripts/archive_mops_events.py`（先.一三五-1be）。

模擬 P／Q 與候選 N1～N3／N11 共用；之前只有 forward_source_gap_watch 間接讀它。全在暫存目錄、零外部請求。
1. 只收 source 含「重大訊息」；缺代號或日期不收；（代號、日期、標題）去重（含同批重複）。
2. 只留 KEEP_FIELDS＋archived_at；重跑新增 0。
3. 歸檔有壞行 → 略過該行、原檔前段位元組不變。
4. load_events：檔案不存在／不是 JSON／沒有 events 陣列 → None，不拋錯。
5. 半截行（檔尾無換行）後再追加：照實記錄行為。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import archive_mops_events as A  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, detail: object = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name} {detail}")


def ev(code, date, title, source="TWSE 重大訊息", **kw):
    return {"code": code, "date": date, "title": title, "source": source, "extra": "不該留", **kw}


EVENTS = [
    ev("2330", "2026-10-28", "董事會決議現金減資"),
    ev("2330", "2026-10-28", "董事會決議現金減資"),            # 同批重複
    ev("2330", "2026-10-28", "公告取得設備"),                  # 同日不同標題 → 收
    ev("2317", "2026-10-28", "法說會", source="TWSE 法說會"),  # 非重大訊息 → 不收
    ev("", "2026-10-28", "缺代號"),
    ev("1101", "", "缺日期"),
    "不是物件",
    ev("6488", "2026-10-27", "得標公告", source="TPEx 重大訊息"),
]


def lines(p: Path) -> list[str]:
    return [x for x in p.read_text(encoding="utf-8").split("\n") if x.strip()]


with tempfile.TemporaryDirectory() as td:
    arc = Path(td) / "sub" / "mops_events_archive.jsonl"

    print("1／2. 收錄規則與去重")
    n = A.archive_events(EVENTS, archive=arc)
    rows = [json.loads(x) for x in lines(arc)]
    check("新增 3 筆", n == 3 and len(rows) == 3, (n, len(rows)))
    check("只收重大訊息", all("重大訊息" in r["source"] for r in rows))
    check("同批重複只收一次", sum(r["title"] == "董事會決議現金減資" for r in rows) == 1)
    check("只留 KEEP_FIELDS＋archived_at", set(rows[0]) == set(A.KEEP_FIELDS) | {"archived_at"}, set(rows[0]))
    check("檔尾有換行", arc.read_text(encoding="utf-8").endswith("\n"))
    before = arc.read_bytes()
    n = A.archive_events(EVENTS, archive=arc)
    check("重跑新增 0、檔案不變", n == 0 and arc.read_bytes() == before)

    print("3. 壞行")
    with arc.open("a", encoding="utf-8") as f:
        f.write("{壞行\n")
    before = arc.read_bytes()
    n = A.archive_events([ev("2454", "2026-10-29", "新公告")], archive=arc)
    check("有壞行仍可追加 1 筆", n == 1)
    check("原檔前段位元組不變", arc.read_bytes().startswith(before))
    check("existing_keys 略過壞行", len(A.existing_keys(arc)) == 4, len(A.existing_keys(arc)))

    print("4. load_events")
    check("不存在 → None", A.load_events(path=Path(td) / "nope.json") is None)
    bad = Path(td) / "bad.json"
    bad.write_text("{不是 JSON", encoding="utf-8")
    check("不是 JSON → None", A.load_events(path=bad) is None)
    bad.write_text('{"items": []}', encoding="utf-8")
    check("沒有 events 陣列 → None", A.load_events(path=bad) is None)
    bad.write_text('{"events": [{"code": "2330"}]}', encoding="utf-8")
    check("正常 → list", A.load_events(path=bad) == [{"code": "2330"}])

    print("5. 半截行（檔尾無換行）")
    arc2 = Path(td) / "half.jsonl"
    arc2.write_text(json.dumps({"code": "1101", "date": "2026-10-20", "title": "甲"}, ensure_ascii=False)
                    + '\n{"code": "1102", "da', encoding="utf-8")
    n1 = A.archive_events([ev("1301", "2026-10-21", "乙")], archive=arc2)
    keys1 = A.existing_keys(arc2)
    n2 = A.archive_events([ev("1301", "2026-10-21", "乙")], archive=arc2)
    keys2 = A.existing_keys(arc2)
    lost_first = ("1301", "2026-10-21", "乙") not in keys1
    check("第二次執行後該筆一定在（自癒）", ("1301", "2026-10-21", "乙") in keys2, keys2)
    print(f"  KNOWN_BEHAVIOR：檔尾無換行時，第一次追加的列{'會黏在半截行後面、變成壞行（第二次執行才補回）' if lost_first else '沒有被黏住'}；"
          f"n1={n1} n2={n2}。只記錄不改（歸檔是 append-only，半截行只在寫入中斷時出現）。")

print(f"\n{ok} 通過，{fail} 失敗")
sys.exit(1 if fail else 0)
