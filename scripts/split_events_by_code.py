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
- 先.八十一-11（2026-10-13）：另寫 data/events_by_code/_index.json（目前有事件的代號清單），App 只對清單內
  的代號發請求——從沒有事件的代號（例如 8054、6693）不再每次開 App 打出 404。
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
        if p.stem.startswith("_"):
            continue  # _index.json 等索引檔，不是代號
        if p.stem not in by_code:
            text = _dump({"fetched_at": doc.get("fetched_at"), "source": source, "code": p.stem, "events": []})
            emptied += _write_if_changed(p, text)
    # 先.八十一-20：法說會列表（市場頁「近期法說會」卡用）＝ events.json 裡 type＝法說會、近 60 天公告的列，新到舊。
    # 來源是 TWSE／TPEx 重大訊息（官方）；MOPS 法說會一覽表沒有開放 API、mopsov robots.txt 全站 Disallow，不爬簡報 PDF，
    # App 只給「MOPS 簡報」連結讓使用者自己點開。
    from datetime import date, timedelta
    cut = (date.today() - timedelta(days=60)).isoformat()
    ir = sorted((e for e in events if (e or {}).get("type") == "法說會" and str(e.get("date") or "") >= cut),
                key=lambda e: (str(e.get("date") or ""), str(e.get("code") or "")), reverse=True)
    _write_if_changed(ROOT / "data" / "ir_events.json", _dump({
        "fetched_at": doc.get("fetched_at"), "source": "data/events.json（TWSE／TPEx 重大訊息）type＝法說會、近 60 天；scripts/split_events_by_code.py",
        "note": "日期是重大訊息公告日，不一定是法說會舉行日；簡報 PDF 請點 MOPS 連結自行開啟（MOPS 不開放程式抓取）",
        "count": len(ir), "events": [{k: e.get(k) for k in ("code", "name", "date", "title", "source", "url")} for e in ir]}))
    _write_if_changed(OUT_DIR / "_index.json", _dump({"fetched_at": doc.get("fetched_at"), "source": source,
                                                      "note": "目前有事件的代號（不在清單內＝沒有事件，App 不發請求）",
                                                      "codes": sorted(by_code)}))
    print(f"events 拆檔：{len(events)} 筆、{len(by_code)} 個代號，重寫 {written} 檔，清空已移除代號 {emptied} 檔；索引 _index.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 第十二節：自身失敗只降級成警告
        print(f"! split_events_by_code 失敗（不影響後續步驟）：{type(e).__name__}: {e}")
        sys.exit(0)
