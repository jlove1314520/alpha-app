"""把 data/events.json（約 3.4MB、1.2 萬筆）依股票代號拆成 data/events_by_code/{代號}.json。

常備.開發-20（2026-10-11）：首頁「我的持股事件」卡原本為了自選股＋持倉十幾檔，
每次開 App 都下載整份 events.json（gzip 約 347KB）。改成只抓用得到的代號。
其他頁面（全域搜尋、今日事件、個股頁）照舊讀整份 events.json，不受影響。

規則：
- 零外部請求，只讀 repo 內既有的 events.json；每檔內容 = 整份檔裡 code 相同的事件，原樣保留順序與欄位。
- 內容沒變的檔不重寫。
- 已不在 events.json 裡的代號（事件過了保留天數被移除）：不刪檔，改寫成空清單，
  否則首頁會一直顯示整份檔早已移除的舊事件。
- 自身失敗只印警告、exit 0，不中斷 news_events.yml 的 commit 步驟（CLAUDE.md 第十二節）。
"""
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "events.json"
OUT_DIR = ROOT / "data" / "events_by_code"
CODE_RE = re.compile(r"^[0-9A-Za-z]{2,10}$")


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _write_if_changed(path: Path, text: str) -> bool:
    try:
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
    except Exception:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return True


def main() -> int:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    events = doc.get("events")
    if not isinstance(events, list):
        print("! events.json 沒有 events 清單，中止（不寫出任何檔案）")
        return 0
    by_code: dict[str, list] = {}
    for e in events:
        code = str((e or {}).get("code") or "")
        if CODE_RE.match(code):
            by_code.setdefault(code, []).append(e)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = "data/events.json 依 code 切出（scripts/split_events_by_code.py，零額外請求）"
    written = emptied = 0
    for code, evs in by_code.items():
        text = _dump({"fetched_at": doc.get("fetched_at"), "source": source, "code": code, "events": evs})
        written += _write_if_changed(OUT_DIR / f"{code}.json", text)
    for p in OUT_DIR.glob("*.json"):
        if p.stem not in by_code:
            text = _dump({"fetched_at": doc.get("fetched_at"), "source": source, "code": p.stem, "events": []})
            emptied += _write_if_changed(p, text)
    print(f"events 拆檔：{len(events)} 筆、{len(by_code)} 個代號，重寫 {written} 檔，清空已移除代號 {emptied} 檔")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 第十二節：自身失敗只降級成警告
        print(f"! split_events_by_code 失敗（不影響後續步驟）：{type(e).__name__}: {e}")
        sys.exit(0)
