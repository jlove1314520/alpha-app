"""把首頁自選股用得到的三份全市場檔，依股票代號拆成 data/quote_lite/{代號}.json。

常備.開發-20（2026-10-11，先.六十七）：首頁自選股列原本為了十幾檔，每次開 App 都下載
整份 sparklines.json（gzip 約 112KB）、quotes_all_tw.json（約 51KB），FinMind 名稱清單
失敗時再加 company_info.json（約 73KB）。改成只抓自選股＋加權指數各自的小檔。
其他頁面（個股頁、市場頁、選股頁、搜尋）照舊讀整份檔，不受影響。

每檔內容（欄位短名，省傳輸量）：
    {"asof": sparklines 的 data_asof, "s": 近 20 日收盤（同 sparklines.json）,
     "sd": stale_dates 裡該代號的實際最後日期（沒有就不放）,
     "a": quotes_all_tw.json 該代號整筆原樣, "n": company_info.json 的公司名稱}
三個欄位都是原樣搬過去，沒有任何換算；某份來源沒有這一檔就不放那個欄位。

規則：
- 零外部請求，只讀 repo 內既有檔案；任一份來源讀不到就整批中止、不寫任何檔
  （避免拆出缺欄位的小檔把首頁的價格／走勢線悄悄弄不見）。
- 內容沒變的檔不重寫。
- 已不在任何來源裡的代號：刪掉舊小檔（只刪本目錄底下本腳本產生的 .json），
  首頁拿到 404 就照「查無這一檔」處理，不會顯示過期價格。
- 自身失敗只印警告、exit 0，不中斷 market.yml 的 commit 步驟（CLAUDE.md 第十二節）。
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
DATA = ROOT / "data"
OUT_DIR = DATA / "quote_lite"
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


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main() -> int:
    sp_doc = _load("sparklines.json")
    qa_doc = _load("quotes_all_tw.json")
    ci_doc = _load("company_info.json")
    sparks = sp_doc.get("sparklines")
    quotes = qa_doc.get("quotes")
    comps = ci_doc.get("companies")
    if not (isinstance(sparks, dict) and isinstance(quotes, dict) and isinstance(comps, dict)) or not sparks or not quotes:
        print("! 來源檔缺 sparklines／quotes／companies 或為空，中止（不寫出任何檔案）")
        return 0
    asof = (sp_doc.get("meta") or {}).get("data_asof")
    stale = sp_doc.get("stale_dates") or {}
    codes = {c for c in (set(sparks) | set(quotes) | set(comps)) if CODE_RE.match(str(c))}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for code in codes:
        rec = {"asof": asof}
        if code in sparks:
            rec["s"] = sparks[code]
        if code in stale:
            rec["sd"] = stale[code]
        if code in quotes:
            rec["a"] = quotes[code]
        c = comps.get(code)
        if isinstance(c, dict) and c.get("name"):
            rec["n"] = c["name"]
        written += _write_if_changed(OUT_DIR / f"{code}.json", _dump(rec))
    removed = 0
    for p in OUT_DIR.glob("*.json"):
        if p.stem not in codes:
            p.unlink()
            removed += 1
    print(f"quote_lite 拆檔：{len(codes)} 個代號（走勢線 {len(sparks)}、全市場收盤 {len(quotes)}、名稱 {len(comps)}），"
          f"重寫 {written} 檔，刪除已移除代號 {removed} 檔")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 第十二節：自身失敗只降級成警告
        print(f"! split_quote_lite 失敗（不影響後續步驟）：{type(e).__name__}: {e}")
        sys.exit(0)
