"""把 data/stock_detail.json（約 14MB、1.9 萬檔）拆成每檔獨立檔案，給 App 個股頁延遲載入。

常備.開發-20（2026-10-11）：個股頁原本第一次開就要下載整份 stock_detail.json，
手機上動輒十幾 MB。改成：
- `data/stock_detail/{代號}.json`：單檔內容與 stock_detail.json 的 `stocks[代號]` 完全相同
  （不改欄位、不加工），App 開哪一檔才抓哪一檔。
- `data/stock_detail_eps.json`：估值區間卡要「同產業所有股票」的近四季 EPS，
  只保留每檔 financials.quarters 的最後四筆 {year, quarter, eps}——
  App 的 epsTtmFromDetail() 本來就只取最後四筆，結果與讀整份檔相同。

規則：
- 零外部請求，只讀 repo 內既有的 stock_detail.json。
- 內容沒變的檔案不重寫（避免無意義的 git 異動）。
- 不刪除已不在來源裡的舊檔（刪檔屬不可逆動作；舊代號留著只是多一個用不到的檔）。
- 自身失敗只印警告、exit 0，不中斷 market.yml 後續步驟（CLAUDE.md 第十二節）。
- 原本的 data/stock_detail.json 保留不動，排程腳本／稽核／冒煙測試照舊讀它。
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
SRC = ROOT / "data" / "stock_detail.json"
OUT_DIR = ROOT / "data" / "stock_detail"
EPS_OUT = ROOT / "data" / "stock_detail_eps.json"
CODE_RE = re.compile(r"^[0-9A-Za-z]{2,10}$")  # 代號直接當檔名，只收英數字，避免路徑字元


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
    data = json.loads(SRC.read_text(encoding="utf-8"))
    stocks = data.get("stocks") or {}
    if not stocks:
        print("! stock_detail.json 沒有 stocks，中止（不寫出任何檔案）")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = bad = 0
    eps = {}
    for code, st in stocks.items():
        if not CODE_RE.match(str(code)) or not isinstance(st, dict):
            bad += 1
            continue
        if _write_if_changed(OUT_DIR / f"{code}.json", _dump(st)):
            written += 1
        else:
            skipped += 1
        qs = ((st.get("financials") or {}).get("quarters")) or []
        if qs:
            eps[code] = {"financials": {"quarters": [
                {"year": q.get("year"), "quarter": q.get("quarter"), "eps": q.get("eps")} for q in qs[-4:]
            ]}}
    meta = data.get("meta") or {}
    eps_doc = {
        "meta": {
            "generated_at": meta.get("generated_at"),
            "source": "data/stock_detail.json 的 financials.quarters 最後四筆（scripts/split_stock_detail.py 切出，零額外請求）",
            "count": len(eps),
        },
        "stocks": eps,
    }
    _write_if_changed(EPS_OUT, _dump(eps_doc))
    print(f"stock_detail 拆檔：{len(stocks)} 檔，重寫 {written}、未變 {skipped}、略過非法代號 {bad}；EPS 摘要 {len(eps)} 檔")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 第十二節：自身失敗只降級成警告
        print(f"! split_stock_detail 失敗（不影響後續步驟）：{type(e).__name__}: {e}")
        sys.exit(0)
