"""由 research/TRIALS_LEDGER.md 產生 data/trials_index.json（App 研究透明度頁讀取）。
只做唯讀解析：編號、日期、軌道、名稱、判定。不改帳本本身。"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "research" / "TRIALS_LEDGER.md"
OUT = ROOT / "data" / "trials_index.json"


def clean(s):
    return re.sub(r"[`*]", "", s).strip()


def main():
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|(.*)$", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        rows.append({
            "id": int(cells[0]),
            "date": cells[1],
            "track": cells[2],
            "name": clean(cells[3])[:80],
            "verdict": clean(cells[6])[:40],
        })
    rows.sort(key=lambda r: -r["id"])
    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source": "research/TRIALS_LEDGER.md",
        "disclaimer": "研究紀錄，非投資建議",
        "count": len(rows),
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"trials_index: {len(rows)} rows")


if __name__ == "__main__":
    sys.exit(main())
